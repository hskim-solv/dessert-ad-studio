from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re

from dessert_ad_studio.evaluation import (
    MarketingContextEvalResult,
    evaluate_marketing_context_retrieval,
)
from dessert_ad_studio.marketing_context import _GUIDE_DOCS
from dessert_ad_studio.marketing_context_eval_cases import MARKETING_CONTEXT_EVAL_CASES
from dessert_ad_studio.product_analysis import MockProductAnalyzer
from dessert_ad_studio.schemas import GenerationRequest, MarketingContext, ProductAnalysis

EMBEDDING_DIMENSIONS = 32
_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣_]+")
_PREMIUM_STRONG_SIGNALS = ("premium", "프리미엄", "고급", "minimal_premium")
_PREMIUM_WEAK_SIGNALS = ("선물",)
_PGVECTOR_SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS marketing_guide_embeddings (
    doc_id text PRIMARY KEY,
    category text NOT NULL,
    content text NOT NULL,
    keywords text[] NOT NULL DEFAULT ARRAY[]::text[],
    embedding vector(32) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS marketing_guide_embeddings_category_idx
    ON marketing_guide_embeddings (category);

CREATE INDEX IF NOT EXISTS marketing_guide_embeddings_embedding_hnsw_idx
    ON marketing_guide_embeddings
    USING hnsw (embedding vector_cosine_ops);
"""
_PGVECTOR_UPSERT_SQL = """
INSERT INTO marketing_guide_embeddings
  (doc_id, category, content, keywords, embedding)
VALUES (%s, %s, %s, %s, %s::vector)
ON CONFLICT (doc_id) DO UPDATE SET
  category = EXCLUDED.category,
  content = EXCLUDED.content,
  keywords = EXCLUDED.keywords,
  embedding = EXCLUDED.embedding,
  updated_at = now()
"""


@dataclass(frozen=True)
class PgvectorGuideRow:
    doc_id: str
    category: str
    content: str
    keywords: tuple[str, ...]
    embedding: list[float]


@dataclass(frozen=True)
class PgvectorQueryTexts:
    semantic_text: str
    rerank_text: str


class DeterministicGuideEmbedder:
    """Small local embedding for CI/eval; not a production semantic model."""

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _tokens(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=4).digest()
            bucket = int.from_bytes(digest[:2], "big") % self.dimensions
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class PgvectorHybridMarketingContextRetriever:
    name = "pgvector_hybrid"

    def __init__(
        self,
        dsn: str | None = None,
        top_k: int = 3,
        embedder: DeterministicGuideEmbedder | None = None,
    ) -> None:
        self._dsn = dsn
        self._top_k = top_k
        self._embedder = embedder or DeterministicGuideEmbedder()
        self._rows = build_pgvector_guide_rows(self._embedder)
        self._row_by_id = {row.doc_id: row for row in self._rows}
        if self._dsn:
            self._ensure_database_seeded()

    def retrieve(
        self,
        request: GenerationRequest,
        product_analysis: ProductAnalysis,
    ) -> MarketingContext:
        query_texts = build_pgvector_query_texts(request, product_analysis)
        query_embedding = self._embedder.embed(query_texts.semantic_text)
        selected_rows = rank_hybrid_rows(
            query_embedding=query_embedding,
            rows=self._candidate_rows(query_embedding),
            top_k=self._top_k,
            rerank_text=query_texts.rerank_text,
        )
        safety_rows = [row for row in self._rows if row.category == "prohibited_claims"]
        context_rows = _dedupe_rows([*selected_rows, *safety_rows])
        return _marketing_context_from_rows(self.name, context_rows)

    def _candidate_rows(self, query_embedding: list[float]) -> list[PgvectorGuideRow]:
        if not self._dsn:
            return self._rows

        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg is required for pgvector_hybrid retriever") from exc

        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT doc_id
                        FROM marketing_guide_embeddings
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (to_pgvector_literal(query_embedding), len(self._rows)),
                    )
                    doc_ids = [doc_id for (doc_id,) in cursor.fetchall()]
        except psycopg.Error as exc:
            raise _pgvector_runtime_error("query", exc) from exc
        return [self._row_by_id[doc_id] for doc_id in doc_ids if doc_id in self._row_by_id]

    def _ensure_database_seeded(self) -> None:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg is required for pgvector_hybrid retriever") from exc

        try:
            with psycopg.connect(self._dsn) as conn:
                conn.execute(_PGVECTOR_SCHEMA_SQL)
                with conn.cursor() as cursor:
                    for row in self._rows:
                        cursor.execute(
                            _PGVECTOR_UPSERT_SQL,
                            (
                                row.doc_id,
                                row.category,
                                row.content,
                                list(row.keywords),
                                to_pgvector_literal(row.embedding),
                            ),
                        )
                conn.commit()
        except psycopg.Error as exc:
            raise _pgvector_runtime_error("seed", exc) from exc


def build_pgvector_guide_rows(
    embedder: DeterministicGuideEmbedder | None = None,
) -> list[PgvectorGuideRow]:
    model = embedder or DeterministicGuideEmbedder()
    return [
        PgvectorGuideRow(
            doc_id=doc.doc_id,
            category=doc.category,
            content=_guide_content(doc),
            keywords=doc.keywords,
            embedding=model.embed(_guide_content(doc)),
        )
        for doc in _GUIDE_DOCS
    ]


def evaluate_offline_pgvector_candidate(
    top_k: int = 3,
    embedder: DeterministicGuideEmbedder | None = None,
) -> list[MarketingContextEvalResult]:
    model = embedder or DeterministicGuideEmbedder()
    rows = build_pgvector_guide_rows(model)
    analyzer = MockProductAnalyzer()
    results: list[MarketingContextEvalResult] = []
    for case in MARKETING_CONTEXT_EVAL_CASES:
        analysis = analyzer.analyze(case.request)
        query_texts = build_pgvector_query_texts(case.request, analysis)
        selected_rows = rank_hybrid_rows(
            query_embedding=model.embed(query_texts.semantic_text),
            rows=rows,
            top_k=top_k,
            rerank_text=query_texts.rerank_text,
        )
        safety_rows = [row for row in rows if row.category == "prohibited_claims"]
        context_rows = _dedupe_rows([*selected_rows, *safety_rows])
        context = MarketingContext(
            retriever_backend="pgvector_offline",
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
            )
        )
    return results


def to_pgvector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"


def _pgvector_runtime_error(operation: str, exc: Exception) -> RuntimeError:
    return RuntimeError(
        f"pgvector_hybrid retriever is not ready: {operation} failed "
        f"({exc.__class__.__name__})"
    )


def build_pgvector_query_texts(
    request: GenerationRequest,
    product_analysis: ProductAnalysis,
) -> PgvectorQueryTexts:
    rerank_text = " ".join(
        value
        for value in (
            request.campaign_purpose,
            request.product_name,
            request.tone,
            request.template_hint,
            request.price_text,
            request.user_constraints,
        )
        if value
    )
    semantic_text = " ".join(
        value
        for value in (
            rerank_text,
            product_analysis.product_context,
            product_analysis.copy_focus,
            product_analysis.detected_product_name,
            " ".join(product_analysis.mood_keywords),
            " ".join(product_analysis.selling_points),
        )
        if value
    )
    return PgvectorQueryTexts(semantic_text=semantic_text, rerank_text=rerank_text)


def rank_hybrid_rows(
    query_embedding: list[float],
    rows: list[PgvectorGuideRow],
    top_k: int,
    rerank_text: str,
) -> list[PgvectorGuideRow]:
    query_tokens = set(_tokens(rerank_text))
    scored_rows = [
        (
            row,
            _keyword_signal_score(rerank_text, row),
            _lexical_overlap(query_tokens, row.content),
            _cosine_distance(query_embedding, row.embedding),
        )
        for row in rows
        if row.category != "prohibited_claims"
    ]
    filtered_rows = [item for item in scored_rows if item[1] > 0]
    if not filtered_rows:
        filtered_rows = scored_rows
    return [
        row
        for row, _keyword_score, _lexical_score, _distance in sorted(
            filtered_rows,
            key=lambda item: (-item[1], -item[2], item[3]),
        )[:top_k]
    ]


def _cosine_distance(left: list[float], right: list[float]) -> float:
    return 1.0 - sum(a * b for a, b in zip(left, right, strict=True))


def _guide_content(doc) -> str:
    values = [
        doc.category,
        *doc.keywords,
        *doc.copy_guidelines,
        *doc.tone_examples,
        *doc.platform_notes,
        *doc.prohibited_claims,
        *doc.cta_examples,
    ]
    return " ".join(value for value in values if value)


def _marketing_context_from_rows(
    retriever_backend: str,
    rows: list[PgvectorGuideRow],
) -> MarketingContext:
    doc_by_id = {doc.doc_id: doc for doc in _GUIDE_DOCS}
    docs = [doc_by_id[row.doc_id] for row in rows if row.doc_id in doc_by_id]
    return MarketingContext(
        retriever_backend=retriever_backend,
        guide_categories=_unique(doc.category for doc in docs),
        copy_guidelines=_unique(
            guideline for doc in docs for guideline in doc.copy_guidelines
        ),
        tone_examples=_unique(example for doc in docs for example in doc.tone_examples),
        platform_notes=_unique(note for doc in docs for note in doc.platform_notes),
        prohibited_claims=_unique(
            claim for doc in docs for claim in doc.prohibited_claims
        ),
        cta_examples=_unique(example for doc in docs for example in doc.cta_examples),
        source_doc_ids=[doc.doc_id for doc in docs],
        retrieved_docs_count=len(docs),
    )


def _lexical_overlap(query_tokens: set[str], content: str) -> int:
    return len(query_tokens.intersection(_tokens(content)))


def _keyword_signal_score(query_text: str, row: PgvectorGuideRow) -> int:
    normalized_query = query_text.lower()
    if row.category == "premium" and not any(
        signal in normalized_query for signal in _PREMIUM_STRONG_SIGNALS
    ):
        return sum(
            1
            for keyword in row.keywords
            if keyword
            and keyword.lower() in normalized_query
            and keyword.lower() not in _PREMIUM_WEAK_SIGNALS
        )
    return sum(
        1
        for keyword in row.keywords
        if keyword and keyword.lower() in normalized_query
    )


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


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
