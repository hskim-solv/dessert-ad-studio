from dessert_ad_studio.prompts import build_copy_prompt, build_image_prompt, template_features
from dessert_ad_studio.schemas import GenerationRequest


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
