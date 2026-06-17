from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from typing import Any

from dessert_ad_studio.costing import cost_guard_passed, estimate_openai_image_cost


DEFAULT_OUTPUT_PATH = Path("docs/evidence/cost-guard-summary.json")


def build_cost_guard_summary(
    *,
    model_id: str,
    image_total_tokens: int,
    max_estimated_cost_usd: float,
    evidence_date: str,
) -> dict[str, Any]:
    usage = {"total_tokens": image_total_tokens}
    cost = estimate_openai_image_cost(
        model_id=model_id,
        usage=usage,
        max_budget_usd=max_estimated_cost_usd,
    )
    guard_passed = cost_guard_passed(cost)
    return {
        "cost_guard_smoke": "passed" if guard_passed else "failed",
        "scope": "offline_cost_estimate_no_api_call",
        "evidence_date": evidence_date,
        "model_id": model_id,
        "usage": usage,
        "cost": cost,
        "cost_guard": {
            "passed": guard_passed,
            "max_estimated_cost_usd": max_estimated_cost_usd,
            "estimated": cost["estimated"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build offline cost-guard evidence without calling a paid API.",
        allow_abbrev=False,
    )
    parser.add_argument("--model-id", default="gpt-image-2")
    parser.add_argument("--image-total-tokens", type=int, default=627)
    parser.add_argument("--max-estimated-cost-usd", type=float, default=0.02)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    if args.image_total_tokens < 0:
        raise SystemExit("--image-total-tokens must be non-negative")
    if args.max_estimated_cost_usd < 0:
        raise SystemExit("--max-estimated-cost-usd must be non-negative")

    summary = build_cost_guard_summary(
        model_id=args.model_id,
        image_total_tokens=args.image_total_tokens,
        max_estimated_cost_usd=args.max_estimated_cost_usd,
        evidence_date=args.date,
    )
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    print(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    return 0 if summary["cost_guard_smoke"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
