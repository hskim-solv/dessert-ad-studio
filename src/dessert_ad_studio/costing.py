from __future__ import annotations

import os
from typing import Any, Mapping


OPENAI_PRICING_URL = "https://openai.com/api/pricing/"
OPENAI_PRICING_CHECKED_DATE = "2026-06-17"

_TEXT_MODEL_RATES_USD_PER_1M = {
    "gpt-5.4-mini": {
        "input_tokens": 0.75,
        "output_tokens": 4.5,
    },
}

_IMAGE_MODEL_RATES_USD_PER_1M = {
    # The image backend exposes only total_tokens, so use the image output rate
    # as a conservative ceiling until input/output token buckets are available.
    "gpt-image-2": {
        "image_total_tokens_conservative": 30.0,
    },
}


def estimate_openai_text_cost(
    *,
    model_id: str | None,
    usage: Mapping[str, Any] | None,
    max_budget_usd: float | None = None,
) -> dict[str, Any]:
    prompt_tokens = _token_count(usage, "prompt_tokens")
    completion_tokens = _token_count(usage, "completion_tokens")
    if prompt_tokens is None and completion_tokens is None:
        return _not_estimated(
            model_id=model_id,
            reason="usage.prompt_tokens and usage.completion_tokens are required",
            max_budget_usd=max_budget_usd,
        )

    input_rate = _rate_from_env(
        "OPENAI_COPY_INPUT_USD_PER_1M_TOKENS",
        _TEXT_MODEL_RATES_USD_PER_1M.get(model_id or "", {}).get("input_tokens"),
    )
    output_rate = _rate_from_env(
        "OPENAI_COPY_OUTPUT_USD_PER_1M_TOKENS",
        _TEXT_MODEL_RATES_USD_PER_1M.get(model_id or "", {}).get("output_tokens"),
    )
    if input_rate is None or output_rate is None:
        return _not_estimated(
            model_id=model_id,
            reason=(
                "missing text token rates; set OPENAI_COPY_INPUT_USD_PER_1M_TOKENS "
                "and OPENAI_COPY_OUTPUT_USD_PER_1M_TOKENS for this model"
            ),
            max_budget_usd=max_budget_usd,
        )

    line_items = []
    if prompt_tokens is not None:
        line_items.append(
            _line_item(
                model_id=model_id,
                usage_type="input_tokens",
                tokens=prompt_tokens,
                usd_per_1m_tokens=input_rate,
            )
        )
    if completion_tokens is not None:
        line_items.append(
            _line_item(
                model_id=model_id,
                usage_type="output_tokens",
                tokens=completion_tokens,
                usd_per_1m_tokens=output_rate,
            )
        )
    return _estimated(line_items=line_items, max_budget_usd=max_budget_usd)


def estimate_openai_image_cost(
    *,
    model_id: str | None,
    usage: Mapping[str, Any] | None,
    max_budget_usd: float | None = None,
) -> dict[str, Any]:
    total_tokens = _token_count(usage, "total_tokens")
    if total_tokens is None:
        return _not_estimated(
            model_id=model_id,
            reason="usage.total_tokens is required",
            max_budget_usd=max_budget_usd,
        )

    rate = _rate_from_env(
        "OPENAI_IMAGE_USD_PER_1M_TOKENS",
        _IMAGE_MODEL_RATES_USD_PER_1M.get(model_id or "", {}).get(
            "image_total_tokens_conservative"
        ),
    )
    if rate is None:
        return _not_estimated(
            model_id=model_id,
            reason=("missing image token rate; set OPENAI_IMAGE_USD_PER_1M_TOKENS for this model"),
            max_budget_usd=max_budget_usd,
        )

    return _estimated(
        line_items=[
            _line_item(
                model_id=model_id,
                usage_type="image_total_tokens_conservative",
                tokens=total_tokens,
                usd_per_1m_tokens=rate,
            )
        ],
        max_budget_usd=max_budget_usd,
    )


def cost_guard_passed(estimate: Mapping[str, Any]) -> bool:
    budget = estimate.get("budget")
    if not isinstance(budget, Mapping):
        return True
    if estimate.get("estimated") is False:
        return False
    return budget.get("passed") is not False


def _estimated(
    *,
    line_items: list[dict[str, Any]],
    max_budget_usd: float | None,
) -> dict[str, Any]:
    total_usd = round(sum(item["cost_usd"] for item in line_items), 6)
    return {
        "estimated": True,
        "currency": "USD",
        "total_usd": total_usd,
        "pricing_basis": "USD per 1M tokens",
        "pricing_source": {
            "url": OPENAI_PRICING_URL,
            "checked_date": OPENAI_PRICING_CHECKED_DATE,
            "override_env_supported": True,
        },
        "line_items": line_items,
        "budget": _budget(total_usd=total_usd, max_budget_usd=max_budget_usd),
    }


def _not_estimated(
    *,
    model_id: str | None,
    reason: str,
    max_budget_usd: float | None,
) -> dict[str, Any]:
    return {
        "estimated": False,
        "currency": "USD",
        "total_usd": None,
        "reason": reason,
        "model_id": model_id,
        "pricing_basis": "USD per 1M tokens",
        "pricing_source": {
            "url": OPENAI_PRICING_URL,
            "checked_date": OPENAI_PRICING_CHECKED_DATE,
            "override_env_supported": True,
        },
        "line_items": [],
        "budget": _budget(total_usd=None, max_budget_usd=max_budget_usd),
    }


def _line_item(
    *,
    model_id: str | None,
    usage_type: str,
    tokens: int,
    usd_per_1m_tokens: float,
) -> dict[str, Any]:
    return {
        "model_id": model_id,
        "usage_type": usage_type,
        "tokens": tokens,
        "usd_per_1m_tokens": usd_per_1m_tokens,
        "cost_usd": round((tokens / 1_000_000) * usd_per_1m_tokens, 6),
    }


def _budget(
    *,
    total_usd: float | None,
    max_budget_usd: float | None,
) -> dict[str, Any] | None:
    if max_budget_usd is None:
        return None
    if total_usd is None:
        return {
            "max_usd": max_budget_usd,
            "passed": None,
            "over_by_usd": None,
        }
    passed = total_usd <= max_budget_usd
    return {
        "max_usd": max_budget_usd,
        "passed": passed,
        "over_by_usd": round(max(total_usd - max_budget_usd, 0.0), 6),
    }


def _rate_from_env(name: str, fallback: float | None) -> float | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return fallback
    try:
        value = float(raw)
    except ValueError:
        return fallback
    return value if value >= 0 else fallback


def _token_count(usage: Mapping[str, Any] | None, key: str) -> int | None:
    if usage is None:
        return None
    value = usage.get(key)
    return value if isinstance(value, int) and value >= 0 else None
