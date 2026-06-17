from __future__ import annotations

from dessert_ad_studio.costing import (
    cost_guard_passed,
    estimate_openai_image_cost,
    estimate_openai_text_cost,
)


def test_estimate_openai_text_cost_uses_default_model_rates() -> None:
    estimate = estimate_openai_text_cost(
        model_id="gpt-5.4-mini",
        usage={
            "prompt_tokens": 1_000,
            "completion_tokens": 500,
            "total_tokens": 1_500,
        },
    )

    assert estimate["estimated"] is True
    assert estimate["total_usd"] == 0.003
    assert estimate["budget"] is None
    assert estimate["line_items"] == [
        {
            "model_id": "gpt-5.4-mini",
            "usage_type": "input_tokens",
            "tokens": 1_000,
            "usd_per_1m_tokens": 0.75,
            "cost_usd": 0.00075,
        },
        {
            "model_id": "gpt-5.4-mini",
            "usage_type": "output_tokens",
            "tokens": 500,
            "usd_per_1m_tokens": 4.5,
            "cost_usd": 0.00225,
        },
    ]


def test_estimate_openai_image_cost_uses_conservative_image_output_rate() -> None:
    estimate = estimate_openai_image_cost(
        model_id="gpt-image-2",
        usage={"total_tokens": 627},
        max_budget_usd=0.02,
    )

    assert estimate["estimated"] is True
    assert estimate["total_usd"] == 0.01881
    assert estimate["budget"] == {
        "max_usd": 0.02,
        "passed": True,
        "over_by_usd": 0.0,
    }
    assert estimate["line_items"] == [
        {
            "model_id": "gpt-image-2",
            "usage_type": "image_total_tokens_conservative",
            "tokens": 627,
            "usd_per_1m_tokens": 30.0,
            "cost_usd": 0.01881,
        }
    ]


def test_estimate_openai_image_cost_fails_budget_when_estimate_exceeds_limit() -> None:
    estimate = estimate_openai_image_cost(
        model_id="gpt-image-2",
        usage={"total_tokens": 627},
        max_budget_usd=0.01,
    )

    assert estimate["estimated"] is True
    assert estimate["budget"] == {
        "max_usd": 0.01,
        "passed": False,
        "over_by_usd": 0.00881,
    }


def test_estimate_openai_image_cost_requires_rate_for_unknown_model() -> None:
    estimate = estimate_openai_image_cost(
        model_id="gpt-image-unknown",
        usage={"total_tokens": 627},
    )

    assert estimate["estimated"] is False
    assert estimate["total_usd"] is None
    assert estimate["line_items"] == []
    assert "OPENAI_IMAGE_USD_PER_1M_TOKENS" in estimate["reason"]


def test_cost_guard_fails_when_budget_is_set_but_cost_is_not_estimated() -> None:
    estimate = estimate_openai_image_cost(
        model_id="gpt-image-unknown",
        usage={"total_tokens": 627},
        max_budget_usd=0.02,
    )

    assert estimate["estimated"] is False
    assert cost_guard_passed(estimate) is False
