from dessert_ad_studio.banner_overlay import build_demo_product_analysis
from dessert_ad_studio.product_analysis import MockProductAnalyzer
from dessert_ad_studio.schemas import GenerationRequest


def _request(reference_image_name: str | None = "cake.jpg") -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="discount",
        product_name="딸기 생크림 케이크",
        tone="warm",
        template_hint="cozy_cafe",
        price_text="주말 10% 할인",
        user_constraints="20대 여성 타깃, 감성적인 문구",
        reference_image_name=reference_image_name,
    )


def test_mock_product_analyzer_returns_display_fields_with_reference() -> None:
    analysis = MockProductAnalyzer().analyze(_request(), reference_image=b"png")

    assert analysis.label == "Product analysis"
    assert analysis.analyzer_backend == "mock"
    assert analysis.product_context == "딸기 생크림 케이크 / 디저트 카페 상품"
    assert "할인/프로모션" in analysis.ad_goal
    assert "따뜻한" in analysis.visual_strategy
    assert "업로드된 제품 사진" in analysis.photo_strategy
    assert "오버레이" in analysis.rendering_strategy


def test_mock_product_analyzer_handles_missing_reference_image() -> None:
    analysis = MockProductAnalyzer().analyze(
        _request(reference_image_name=None),
        reference_image=None,
    )

    assert "참고 이미지 없음" in analysis.photo_strategy


def test_build_demo_product_analysis_uses_mock_analyzer_fields() -> None:
    analysis = build_demo_product_analysis(_request())

    assert analysis["label"] == "Product analysis"
    assert analysis["analyzer_backend"] == "mock"
    assert analysis["product_context"] == "딸기 생크림 케이크 / 디저트 카페 상품"
