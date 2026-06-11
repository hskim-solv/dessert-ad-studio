from dessert_ad_studio.schemas import GenerationRequest
from dessert_ad_studio.triton import LocalTemplateScorer


def test_local_template_scorer_returns_ranked_template() -> None:
    request = GenerationRequest(
        campaign_purpose="seasonal_event",
        product_name="벚꽃 딸기 케이크",
        tone="warm",
        template_hint="seasonal_event",
    )
    ranking = LocalTemplateScorer().rank(request)

    assert ranking.template_name in {
        "cozy_cafe",
        "minimal_premium",
        "cute_dessert",
        "seasonal_event",
    }
    assert 0.0 <= ranking.score <= 1.0
    assert ranking.scorer == "local-template-scorer"
