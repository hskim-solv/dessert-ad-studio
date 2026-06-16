import math

import pytest

from dessert_ad_studio.evaluation import summarize_marketing_context_eval_results
from dessert_ad_studio.marketing_context_pgvector import (
    EMBEDDING_DIMENSIONS,
    DeterministicGuideEmbedder,
    PgvectorHybridMarketingContextRetriever,
    build_pgvector_guide_rows,
    evaluate_offline_pgvector_candidate,
    to_pgvector_literal,
)
from dessert_ad_studio.marketing_context_eval_cases import MARKETING_CONTEXT_EVAL_CASES
from dessert_ad_studio.product_analysis import MockProductAnalyzer


def test_deterministic_guide_embedder_returns_normalized_fixed_width_vector() -> None:
    embedder = DeterministicGuideEmbedder()

    first = embedder.embed("인스타그램 디저트 카페 신메뉴")
    second = embedder.embed("인스타그램 디저트 카페 신메뉴")

    assert first == second
    assert len(first) == EMBEDDING_DIMENSIONS
    assert math.sqrt(sum(value * value for value in first)) == pytest.approx(1.0)


def test_build_pgvector_guide_rows_contains_curated_source_metadata() -> None:
    rows = build_pgvector_guide_rows()

    assert {row.doc_id for row in rows} >= {
        "guide-cafe-dessert-core-v1",
        "guide-instagram-sns-v1",
        "guide-ad-claims-safety-v1",
    }
    assert all(len(row.embedding) == EMBEDDING_DIMENSIONS for row in rows)
    assert all(row.content for row in rows)
    assert all(row.category for row in rows)


def test_to_pgvector_literal_preserves_dimensions() -> None:
    literal = to_pgvector_literal([0.1, -0.2, 0.3])

    assert literal == "[0.100000,-0.200000,0.300000]"


def test_offline_pgvector_candidate_hits_required_categories() -> None:
    summary = summarize_marketing_context_eval_results(evaluate_offline_pgvector_candidate())

    assert summary.sample_count >= 10
    assert summary.average_category_hit_rate >= 0.8
    assert summary.average_category_precision >= 0.9
    assert summary.required_category_hit_rate == 1.0
    assert summary.passed is True


def test_hybrid_reranker_does_not_promote_premium_from_gift_word_only() -> None:
    results = {result.sample_label: result for result in evaluate_offline_pgvector_candidate()}

    assert results["discount-promotion"].unexpected_categories == []


def test_pgvector_hybrid_retriever_returns_guidance_without_extra_categories() -> None:
    case = next(item for item in MARKETING_CONTEXT_EVAL_CASES if item.label == "discount-promotion")
    analysis = MockProductAnalyzer().analyze(case.request)

    context = PgvectorHybridMarketingContextRetriever().retrieve(case.request, analysis)

    assert context.retriever_backend == "pgvector_hybrid"
    assert context.guide_categories == ["discount", "prohibited_claims"]
    assert any("할인율" in item for item in context.copy_guidelines)
    assert any("과장" in item for item in context.prohibited_claims)
