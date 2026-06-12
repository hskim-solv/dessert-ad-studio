from dessert_ad_studio.demo_samples import DEMO_SAMPLES, DemoSample
from dessert_ad_studio.schemas import GenerationRequest


def test_demo_samples_include_at_least_three_scenarios() -> None:
    assert len(DEMO_SAMPLES) >= 3


def test_demo_sample_labels_are_unique() -> None:
    labels = [sample.label for sample in DEMO_SAMPLES]
    assert len(labels) == len(set(labels))


def test_demo_samples_convert_to_generation_requests() -> None:
    for sample in DEMO_SAMPLES:
        request = GenerationRequest(
            campaign_purpose=sample.campaign_purpose,
            product_name=sample.product_name,
            tone=sample.tone,
            template_hint=sample.template_hint,
            price_text=sample.price_text,
            user_constraints=sample.user_constraints,
        )
        assert request.product_name == sample.product_name


def test_demo_samples_have_display_context() -> None:
    for sample in DEMO_SAMPLES:
        assert isinstance(sample, DemoSample)
        assert sample.business_type.strip()
        assert sample.platform.strip()
        assert sample.user_constraints.strip()
