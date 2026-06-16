from dessert_ad_studio.prompts import build_copy_prompt, build_image_prompt, template_features
from dessert_ad_studio.schemas import GenerationRequest, MarketingContext, ProductAnalysis


def sample_request() -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="new_menu",
        product_name="딸기 크림 크루아상",
        tone="warm",
        template_hint="cozy_cafe",
        price_text="6,800원",
        user_constraints="봄 시즌 한정 느낌",
    )


def test_copy_prompt_contains_required_korean_context() -> None:
    prompt = build_copy_prompt(sample_request())

    assert "딸기 크림 크루아상" in prompt
    assert "신메뉴" in prompt
    assert "따뜻한" in prompt
    assert "3개" in prompt


def test_copy_prompt_can_include_product_analysis_and_marketing_context() -> None:
    product_analysis = ProductAnalysis(
        label="Product analysis",
        product_context="딸기 크림 크루아상 / 디저트 카페 상품",
        ad_goal="신메뉴 출시",
        visual_strategy="따뜻한 카페 배경",
        photo_strategy="reference 없음",
        copy_focus="겹겹이 바삭한 식감",
        rendering_strategy="overlay",
        analyzer_backend="fake",
        detected_product_name="딸기 크림 크루아상",
        selling_points=["바삭한 결", "딸기 크림"],
    )
    marketing_context = MarketingContext(
        retriever_backend="keyword",
        guide_categories=["cafe", "instagram", "prohibited_claims"],
        copy_guidelines=["방문 동기를 먼저 제시한다."],
        platform_notes=["해시태그는 3~5개로 제한한다."],
        prohibited_claims=["근거 없는 과장 효능을 쓰지 않는다."],
        cta_examples=["오늘 매장에서 만나보세요."],
        source_doc_ids=["guide-cafe-dessert-core-v1"],
        retrieved_docs_count=1,
    )

    prompt = build_copy_prompt(
        sample_request(),
        product_analysis=product_analysis,
        marketing_context=marketing_context,
    )

    assert "제품 분석 요약" in prompt
    assert "카피 포인트: 바삭한 결, 딸기 크림" in prompt
    assert "마케팅 가이드" in prompt
    assert "방문 동기" in prompt
    assert "해시태그" in prompt
    assert "과장 효능" in prompt


def test_image_prompt_contains_template_and_constraints() -> None:
    prompt = build_image_prompt(sample_request(), ranked_template="cozy_cafe")

    assert "cozy cafe" in prompt.lower()
    assert "SNS 정사각형 광고 이미지" in prompt
    assert "봄 시즌 한정 느낌" in prompt


def test_template_features_are_stable_vector() -> None:
    features = template_features(sample_request())

    assert len(features) == 8
    assert all(isinstance(value, float) for value in features)
    assert features[0] == 1.0


def test_image_prompt_without_reference_has_no_preserve_line() -> None:
    prompt = build_image_prompt(sample_request(), ranked_template="cozy_cafe")

    assert "보존" not in prompt


def test_image_prompt_with_reference_prepends_preserve_instruction() -> None:
    prompt = build_image_prompt(sample_request(), ranked_template="cozy_cafe", has_reference=True)

    assert prompt.splitlines()[0] == (
        "업로드된 제품 사진의 피사체와 구도를 보존하면서 광고 이미지로 연출한다."
    )
