import pytest

from dessert_ad_studio.evaluation import (
    evaluate_marketing_context_retrieval,
    summarize_marketing_context_eval_results,
)
from dessert_ad_studio.marketing_context import KeywordMarketingContextRetriever
from dessert_ad_studio.product_analysis import MockProductAnalyzer
from dessert_ad_studio.schemas import GenerationRequest, MarketingContext


def _request() -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="discount",
        product_name="딸기 생크림 케이크",
        tone="warm",
        template_hint="cozy_cafe",
        price_text="주말 10% 할인",
        user_constraints="인스타그램 신메뉴 홍보, 20대 여성 타깃",
    )


def test_keyword_marketing_context_retriever_returns_curated_guidance() -> None:
    request = _request()
    analysis = MockProductAnalyzer().analyze(request, reference_image=b"png")

    context = KeywordMarketingContextRetriever().retrieve(request, analysis)

    assert context.retriever_backend == "keyword"
    assert context.retrieved_docs_count >= 3
    assert "cafe" in context.guide_categories
    assert "instagram" in context.guide_categories
    assert "prohibited_claims" in context.guide_categories
    assert any("방문" in item for item in context.copy_guidelines)
    assert any("해시태그" in item for item in context.platform_notes)
    assert any("과장" in item for item in context.prohibited_claims)


def test_keyword_marketing_context_retriever_is_deterministic() -> None:
    request = _request()
    analysis = MockProductAnalyzer().analyze(request)
    retriever = KeywordMarketingContextRetriever()

    first = retriever.retrieve(request, analysis)
    second = retriever.retrieve(request, analysis)

    assert first == second


def test_evaluate_marketing_context_retrieval_reports_missing_categories() -> None:
    context = MarketingContext(
        retriever_backend="keyword",
        guide_categories=["cafe", "prohibited_claims"],
        source_doc_ids=["guide-cafe-dessert-core-v1", "guide-ad-claims-safety-v1"],
        retrieved_docs_count=2,
    )

    result = evaluate_marketing_context_retrieval(
        sample_label="missing-platform",
        context=context,
        expected_categories=("cafe", "instagram", "prohibited_claims"),
        required_categories=("prohibited_claims",),
        threshold=0.8,
    )

    assert result.passed is False
    assert result.category_hit_rate == pytest.approx(2 / 3)
    assert result.category_precision == 1.0
    assert result.required_category_hit_rate == 1.0
    assert result.retrieved_categories == ["cafe", "prohibited_claims"]
    assert result.missing_categories == ["instagram"]
    assert result.unexpected_categories == []
    assert result.to_dict()["sample_label"] == "missing-platform"


def test_summarize_marketing_context_eval_results_requires_all_required_categories() -> None:
    passing = evaluate_marketing_context_retrieval(
        sample_label="safe",
        context=MarketingContext(
            retriever_backend="keyword",
            guide_categories=["cafe", "prohibited_claims"],
            source_doc_ids=["guide-cafe-dessert-core-v1", "guide-ad-claims-safety-v1"],
            retrieved_docs_count=2,
        ),
        expected_categories=("cafe", "prohibited_claims"),
        required_categories=("prohibited_claims",),
    )
    failing = evaluate_marketing_context_retrieval(
        sample_label="unsafe",
        context=MarketingContext(
            retriever_backend="keyword",
            guide_categories=["cafe"],
            source_doc_ids=["guide-cafe-dessert-core-v1"],
            retrieved_docs_count=1,
        ),
        expected_categories=("cafe", "prohibited_claims"),
        required_categories=("prohibited_claims",),
    )

    summary = summarize_marketing_context_eval_results([passing, failing])

    assert summary.sample_count == 2
    assert summary.average_category_hit_rate == pytest.approx(0.75)
    assert summary.average_category_precision == 1.0
    assert summary.required_category_hit_rate == pytest.approx(0.5)
    assert summary.passed is False
