from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dessert_ad_studio.evaluation import (  # noqa: E402
    evaluate_marketing_context_retrieval,
    summarize_marketing_context_eval_results,
)
from dessert_ad_studio.marketing_context_eval_cases import (  # noqa: E402
    MARKETING_CONTEXT_EVAL_CASES,
)
from dessert_ad_studio.marketing_context_pgvector import (  # noqa: E402
    DeterministicGuideEmbedder,
    PgvectorGuideRow,
    build_pgvector_query_texts,
    build_pgvector_guide_rows,
    evaluate_offline_pgvector_candidate,
    rank_hybrid_rows,
    to_pgvector_literal,
)
from dessert_ad_studio.product_analysis import MockProductAnalyzer  # noqa: E402
from dessert_ad_studio.schemas import MarketingContext  # noqa: E402


def run_database_eval(dsn: str, threshold: float, top_k: int):
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit(
            "psycopg is required for --dsn database mode. Install project dependencies first."
        ) from exc

    schema_path = ROOT / "deploy" / "pgvector" / "init" / "001_marketing_context.sql"
    embedder = DeterministicGuideEmbedder()
    rows = build_pgvector_guide_rows(embedder)
    analyzer = MockProductAnalyzer()
    results = []
    with psycopg.connect(dsn) as conn:
        conn.execute(schema_path.read_text(encoding="utf-8"))
        with conn.cursor() as cursor:
            for row in rows:
                cursor.execute(
                    """
                    INSERT INTO marketing_guide_embeddings
                      (doc_id, category, content, keywords, embedding)
                    VALUES (%s, %s, %s, %s, %s::vector)
                    ON CONFLICT (doc_id) DO UPDATE SET
                      category = EXCLUDED.category,
                      content = EXCLUDED.content,
                      keywords = EXCLUDED.keywords,
                      embedding = EXCLUDED.embedding,
                      updated_at = now()
                    """,
                    (
                        row.doc_id,
                        row.category,
                        row.content,
                        list(row.keywords),
                        to_pgvector_literal(row.embedding),
                    ),
                )
        conn.commit()

        row_by_id = {row.doc_id: row for row in rows}
        for case in MARKETING_CONTEXT_EVAL_CASES:
            analysis = analyzer.analyze(case.request)
            query_texts = build_pgvector_query_texts(case.request, analysis)
            query_embedding = embedder.embed(query_texts.semantic_text)
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT doc_id
                    FROM marketing_guide_embeddings
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (to_pgvector_literal(query_embedding), max(top_k, len(rows))),
                )
                candidate_rows = [row_by_id[doc_id] for (doc_id,) in cursor.fetchall()]
            selected_rows = rank_hybrid_rows(
                query_embedding=query_embedding,
                rows=candidate_rows,
                top_k=top_k,
                rerank_text=query_texts.rerank_text,
            )
            context_rows = _dedupe_rows(
                [
                    *selected_rows,
                    *[row for row in rows if row.category == "prohibited_claims"],
                ]
            )
            context = MarketingContext(
                retriever_backend="pgvector_database",
                guide_categories=_unique(row.category for row in context_rows),
                source_doc_ids=[row.doc_id for row in context_rows],
                retrieved_docs_count=len(context_rows),
            )
            results.append(
                evaluate_marketing_context_retrieval(
                    sample_label=case.label,
                    context=context,
                    expected_categories=case.expected_categories,
                    required_categories=("prohibited_claims",),
                    threshold=threshold,
                )
            )
    return summarize_marketing_context_eval_results(results, threshold=threshold)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate pgvector marketing-context retrieval candidate."
    )
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--dsn", default=os.getenv("PGVECTOR_DSN", ""))
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    if args.dsn:
        summary = run_database_eval(args.dsn, threshold=args.threshold, top_k=args.top_k)
    else:
        summary = summarize_marketing_context_eval_results(
            evaluate_offline_pgvector_candidate(top_k=args.top_k),
            threshold=args.threshold,
        )

    payload = json.dumps(summary.to_dict(), ensure_ascii=False, indent=2)
    print(payload)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    return 0 if summary.passed else 1


def _dedupe_rows(rows: list[PgvectorGuideRow]) -> list[PgvectorGuideRow]:
    seen: set[str] = set()
    unique_rows: list[PgvectorGuideRow] = []
    for row in rows:
        if row.doc_id in seen:
            continue
        seen.add(row.doc_id)
        unique_rows.append(row)
    return unique_rows


def _unique(values) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            unique_values.append(value)
    return unique_values


if __name__ == "__main__":
    sys.exit(main())
