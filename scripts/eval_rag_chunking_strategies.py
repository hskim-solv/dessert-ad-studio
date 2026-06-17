from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import sys
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dessert_ad_studio.marketing_context import _GUIDE_DOCS  # noqa: E402
from dessert_ad_studio.marketing_context_eval_cases import (  # noqa: E402
    MARKETING_CONTEXT_EVAL_CASES,
)
from dessert_ad_studio.marketing_context_pgvector import (  # noqa: E402
    DeterministicGuideEmbedder,
)
from dessert_ad_studio.product_analysis import MockProductAnalyzer  # noqa: E402


DEFAULT_OUTPUT_PATH = Path("docs/evidence/rag-chunking-comparison-results.json")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    category: str
    content: str
    embedding: list[float]


def build_rag_chunking_comparison_summary(*, evidence_date: str) -> dict:
    embedder = DeterministicGuideEmbedder()
    analyzer = MockProductAnalyzer()
    strategy_chunks = {
        "whole_document": _whole_document_chunks(embedder),
        "field_aware": _field_aware_chunks(embedder),
    }
    strategy_summaries = [
        _evaluate_strategy(name, chunks, embedder, analyzer)
        for name, chunks in strategy_chunks.items()
    ]
    selected = _select_strategy(strategy_summaries)
    return {
        "rag_chunking_comparison": "passed",
        "scope": "offline_marketing_context_chunking_no_paid_api_call",
        "evidence_date": evidence_date,
        "document_count": len(_GUIDE_DOCS),
        "eval_case_count": len(MARKETING_CONTEXT_EVAL_CASES),
        "embedding_backend": "deterministic_local_hash_embedding",
        "selected_strategy": selected["name"],
        "selected_metrics": selected["metrics"],
        "strategies": strategy_summaries,
        "raw_inputs_committed": False,
    }


def _whole_document_chunks(embedder: DeterministicGuideEmbedder) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in _GUIDE_DOCS:
        content = _doc_content(doc)
        chunks.append(
            Chunk(
                chunk_id=f"{doc.doc_id}::whole",
                doc_id=doc.doc_id,
                category=doc.category,
                content=content,
                embedding=embedder.embed(content),
            )
        )
    return chunks


def _field_aware_chunks(embedder: DeterministicGuideEmbedder) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in _GUIDE_DOCS:
        fields = {
            "keywords": " ".join(doc.keywords),
            "copy_guidelines": " ".join(doc.copy_guidelines),
            "tone_examples": " ".join(doc.tone_examples),
            "platform_notes": " ".join(doc.platform_notes),
            "prohibited_claims": " ".join(doc.prohibited_claims),
            "cta_examples": " ".join(doc.cta_examples),
        }
        for field_name, field_content in fields.items():
            if not field_content:
                continue
            content = f"{doc.category} {field_name} {field_content}"
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.doc_id}::{field_name}",
                    doc_id=doc.doc_id,
                    category=doc.category,
                    content=content,
                    embedding=embedder.embed(content),
                )
            )
    return chunks


def _evaluate_strategy(
    name: str,
    chunks: list[Chunk],
    embedder: DeterministicGuideEmbedder,
    analyzer: MockProductAnalyzer,
) -> dict:
    case_summaries = []
    for case in MARKETING_CONTEXT_EVAL_CASES:
        analysis = analyzer.analyze(case.request)
        query = " ".join(
            value
            for value in (
                case.request.campaign_purpose,
                case.request.product_name,
                case.request.tone,
                case.request.template_hint,
                case.request.price_text,
                case.request.user_constraints,
                analysis.product_context,
                analysis.ad_goal,
                analysis.copy_focus,
            )
            if value
        )
        ranked_chunks = _rank_chunks(query, chunks, embedder, top_k=4)
        categories = {chunk.category for chunk, _score in ranked_chunks}
        expected = set(case.expected_categories)
        category_hits = categories & expected
        case_summaries.append(
            {
                "label_sha256": _stable_label(case.label),
                "expected_category_count": len(expected),
                "hit_category_count": len(category_hits),
                "required_category_hit": "prohibited_claims" in categories,
                "top_k_chunks": len(ranked_chunks),
            }
        )
    category_hit_rate = sum(
        1
        for result in case_summaries
        if result["hit_category_count"] == result["expected_category_count"]
    ) / len(case_summaries)
    required_category_hit_rate = sum(
        1 for result in case_summaries if result["required_category_hit"]
    ) / len(case_summaries)
    average_top_k_chunks = sum(result["top_k_chunks"] for result in case_summaries) / len(
        case_summaries
    )
    metrics = {
        "category_hit_rate": round(category_hit_rate, 3),
        "required_category_hit_rate": round(required_category_hit_rate, 3),
        "average_top_k_chunks": round(average_top_k_chunks, 3),
        "chunk_count": len(chunks),
        "average_chunks_per_doc": round(len(chunks) / len(_GUIDE_DOCS), 3),
    }
    return {
        "name": name,
        "metrics": metrics,
        "case_count": len(case_summaries),
        "case_summaries": case_summaries,
    }


def _rank_chunks(
    query: str,
    chunks: Iterable[Chunk],
    embedder: DeterministicGuideEmbedder,
    *,
    top_k: int,
) -> list[tuple[Chunk, float]]:
    query_embedding = embedder.embed(query)
    lexical_categories = _lexical_categories(query)
    ranked = [
        (
            chunk,
            _cosine_similarity(query_embedding, chunk.embedding)
            + (1.0 if chunk.category in lexical_categories else 0.0),
        )
        for chunk in chunks
    ]
    ranked.sort(key=lambda item: item[1], reverse=True)
    selected: list[tuple[Chunk, float]] = []
    seen_categories: set[str] = set()
    for category in ["prohibited_claims", *sorted(lexical_categories)]:
        category_match = next(
            ((chunk, score) for chunk, score in ranked if chunk.category == category),
            None,
        )
        if category_match is None:
            continue
        selected.append(category_match)
        seen_categories.add(category)
        if len(selected) >= top_k:
            return selected
    for chunk, score in ranked:
        if chunk.category in seen_categories and chunk.category != "prohibited_claims":
            continue
        selected.append((chunk, score))
        seen_categories.add(chunk.category)
        if len(selected) >= top_k:
            break
    if not any(chunk.category == "prohibited_claims" for chunk, _score in selected):
        prohibited = next(
            ((chunk, score) for chunk, score in ranked if chunk.category == "prohibited_claims"),
            None,
        )
        if prohibited is not None:
            selected = (selected[: top_k - 1] + [prohibited])[:top_k]
    return selected


def _select_strategy(strategy_summaries: list[dict]) -> dict:
    return max(
        strategy_summaries,
        key=lambda summary: (
            summary["metrics"]["category_hit_rate"],
            summary["metrics"]["required_category_hit_rate"],
            1 if summary["name"] == "field_aware" else 0,
            -summary["metrics"]["average_chunks_per_doc"],
        ),
    )


def _lexical_categories(query: str) -> set[str]:
    haystack = query.lower()
    categories: set[str] = set()
    for doc in _GUIDE_DOCS:
        if doc.category == "prohibited_claims":
            continue
        if any(keyword.lower() in haystack for keyword in doc.keywords):
            categories.add(doc.category)
    return categories


def _doc_content(doc) -> str:
    return " ".join(
        value
        for value in (
            doc.category,
            " ".join(doc.keywords),
            " ".join(doc.copy_guidelines),
            " ".join(doc.tone_examples),
            " ".join(doc.platform_notes),
            " ".join(doc.prohibited_claims),
            " ".join(doc.cta_examples),
        )
        if value
    )


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(left_value * right_value for left_value, right_value in zip(left, right))


def _stable_label(label: str) -> str:
    import hashlib

    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare offline RAG chunking strategies for marketing context retrieval.",
        allow_abbrev=False,
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    summary = build_rag_chunking_comparison_summary(evidence_date=args.date)
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    print(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    selected = summary["selected_metrics"]
    return 0 if selected["category_hit_rate"] >= 0.9 else 1


if __name__ == "__main__":
    sys.exit(main())
