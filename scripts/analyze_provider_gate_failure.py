from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any


DEFAULT_INPUT_PATH = Path("docs/evidence/openai-image-edit-preservation-live-summary.json")
DEFAULT_OUTPUT_PATH = Path("docs/evidence/provider-gate-postmortem-summary.json")
PRESERVATION_CHECKS = (
    "roi_color_histogram_similarity_ge_threshold",
    "roi_average_hash_similarity_ge_threshold",
    "roi_edge_similarity_ge_threshold",
)
NEXT_PAID_GATE_CONDITIONS = [
    "review ignored generated outputs locally before another paid run",
    "run a one-sample paid canary before the three-sample provider gate",
    "set an OpenAI dashboard hard budget because the script budget is post-response only",
    "keep deterministic Korean overlay rendering outside the image model",
]


def build_provider_gate_postmortem(summary: dict[str, Any]) -> dict[str, Any]:
    sample_results = summary.get("sample_results", [])
    failure_counts = _failure_counts(sample_results)
    if summary.get("cost_guard", {}).get("passed") is False:
        failure_counts["cost_guard_passed"] = 1

    root_causes = _root_causes(failure_counts)
    provider_gate = summary.get("provider_quality_gate", {})
    usage = summary.get("usage", {})
    cost = summary.get("cost", {})
    budget = cost.get("budget", {})
    sample_count = (
        provider_gate.get("sample_count") or usage.get("sample_count") or len(sample_results)
    )

    return {
        "provider_gate_postmortem": (
            "failed_gate_analyzed"
            if summary.get("openai_image_edit_preservation") != "passed"
            else "passed_gate_reviewed"
        ),
        "source_summary": {
            "model_id": summary.get("model_id"),
            "quality": summary.get("quality"),
            "sample_count": sample_count,
            "elapsed_ms": summary.get("elapsed_ms"),
            "total_tokens": usage.get("total_tokens"),
            "estimated_cost_usd": cost.get("total_usd"),
            "budget_max_usd": budget.get("max_usd"),
            "budget_over_by_usd": budget.get("over_by_usd", 0.0),
        },
        "provider_quality_gate": {
            "passed": provider_gate.get("passed"),
            "passed_count": provider_gate.get("passed_count"),
            "pass_rate": provider_gate.get("pass_rate"),
        },
        "preservation_result": {
            "roi_preservation_checks_passed": _all_preservation_checks_passed(sample_results),
            "minimum_roi_color_histogram_similarity": provider_gate.get(
                "min_roi_color_histogram_similarity"
            ),
            "minimum_roi_average_hash_similarity": provider_gate.get(
                "min_roi_average_hash_similarity"
            ),
            "minimum_roi_edge_similarity": provider_gate.get("min_roi_edge_similarity"),
        },
        "failure_counts": dict(failure_counts),
        "root_causes": root_causes,
        "next_paid_gate_conditions": NEXT_PAID_GATE_CONDITIONS,
        "privacy_boundary": {
            "raw_prompt_committed": False,
            "raw_model_response_committed": False,
            "generated_image_committed": False,
        },
    }


def _failure_counts(sample_results: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for result in sample_results:
        for check_name, passed in result.get("checklist", {}).items():
            if passed is False:
                counts[check_name] += 1
    return counts


def _all_preservation_checks_passed(sample_results: list[dict[str, Any]]) -> bool:
    return bool(sample_results) and all(
        result.get("checklist", {}).get(check_name) is True
        for result in sample_results
        for check_name in PRESERVATION_CHECKS
    )


def _root_causes(failure_counts: Counter[str]) -> list[str]:
    causes: list[str] = []
    if failure_counts.get("sample_elapsed_ms_le_threshold", 0):
        causes.append("latency_threshold_exceeded")
    if failure_counts.get("text_contamination_risk_le_threshold", 0):
        causes.append("text_contamination_heuristic_failed")
    if failure_counts.get("cost_guard_passed", 0):
        causes.append("cost_budget_exceeded")
    for check_name in PRESERVATION_CHECKS:
        if failure_counts.get(check_name, 0):
            causes.append("roi_preservation_failed")
            break
    return causes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze the redacted provider-quality image-edit gate summary.",
        allow_abbrev=False,
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    summary = json.loads(args.input.read_text(encoding="utf-8"))
    postmortem = build_provider_gate_postmortem(summary)
    payload = json.dumps(postmortem, ensure_ascii=False, indent=2)
    print(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
