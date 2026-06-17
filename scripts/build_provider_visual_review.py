from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


DEFAULT_VISUAL_SUMMARY = Path("docs/evidence/visual-quality-summary.json")
DEFAULT_PROVIDER_POSTMORTEM = Path("docs/evidence/provider-gate-postmortem-summary.json")
DEFAULT_LIVE_SUMMARY = Path("docs/evidence/openai-image-edit-preservation-live-summary.json")
DEFAULT_OUTPUT = Path("docs/evidence/provider-visual-review-summary.json")
DEFAULT_REPORT_OUTPUT = Path("docs/evidence/provider-visual-review.md")
MANUAL_REVIEW_SOURCE = "docs/evidence/openai-image-edit-preservation.md"
NEXT_CONDITIONS = [
    "resolve the image-edit latency strategy before any provider-quality claim",
    "run a user-approved full paid provider gate after the latency strategy is chosen",
    "keep deterministic Korean overlay rendering outside the image model",
    "do not commit raw prompts, raw provider responses, or generated provider images",
]


def build_provider_visual_review(
    *,
    visual_summary: dict[str, Any],
    provider_postmortem: dict[str, Any],
    live_summary: dict[str, Any],
) -> dict[str, Any]:
    offline_visual_passed = visual_summary.get("visual_quality_eval") == "passed"
    provider_gate = live_summary.get("provider_quality_gate", {})
    cost_guard = live_summary.get("cost_guard", {})
    checklist = live_summary.get("checklist") or _combined_checklist(live_summary)
    postmortem_preservation = provider_postmortem.get("preservation_result", {})
    root_causes = provider_postmortem.get("root_causes", [])
    text_contamination_passed = checklist.get("text_contamination_risk_le_threshold") is True
    latency_passed = checklist.get("sample_elapsed_ms_le_threshold") is True
    roi_preservation_passed = postmortem_preservation.get("roi_preservation_checks_passed") is True
    first_gate_passed = (
        offline_visual_passed and roi_preservation_passed and text_contamination_passed
    )

    return {
        "provider_visual_review_first_gate": "passed" if first_gate_passed else "failed",
        "scope": "offline_reviewer_rubric_no_paid_api_call",
        "provider_quality_claimed": False,
        "provider_quality_gate_passed": provider_gate.get("passed") is True,
        "provider_quality_unproven": provider_gate.get("passed") is not True,
        "latest_paid_canary": {
            "api_reached": live_summary.get("generated_image", {}).get("exists") is True,
            "model_id": live_summary.get("model_id"),
            "quality": live_summary.get("quality"),
            "sample_count": provider_gate.get("sample_count"),
            "elapsed_ms": live_summary.get("elapsed_ms"),
            "cost_guard_passed": cost_guard.get("passed") is True,
            "estimated_cost_usd": live_summary.get("cost", {}).get("total_usd"),
            "roi_preservation_checks_passed": roi_preservation_passed,
            "text_contamination_passed": text_contamination_passed,
            "latency_passed": latency_passed,
            "root_causes": root_causes,
        },
        "offline_visual_proxy": {
            "passed": offline_visual_passed,
            "sample_count": visual_summary.get("sample_count", 0),
            "passed_count": visual_summary.get("passed_count", 0),
            "pass_rate": visual_summary.get("pass_rate", 0.0),
            "source": str(DEFAULT_VISUAL_SUMMARY),
        },
        "manual_local_review": {
            "status": "documented_prior_manual_review",
            "visible_text_found": False,
            "source": MANUAL_REVIEW_SOURCE,
            "proof_level": "manual_local_review_only",
        },
        "privacy_boundary": {
            "paid_api_call_made_by_script": False,
            "raw_prompt_committed": False,
            "raw_model_response_committed": False,
            "generated_image_committed": False,
        },
        "next_conditions": NEXT_CONDITIONS,
    }


def _combined_checklist(live_summary: dict[str, Any]) -> dict[str, bool]:
    combined: dict[str, bool] = {}
    for result in live_summary.get("sample_results", []):
        for key, value in result.get("checklist", {}).items():
            combined[key] = combined.get(key, True) and value is True
    return combined


def render_report(summary: dict[str, Any]) -> str:
    canary = summary["latest_paid_canary"]
    proxy = summary["offline_visual_proxy"]
    return "\n".join(
        [
            "# Provider Visual Review Evidence",
            "",
            "Date: 2026-06-17",
            "",
            "## Scope",
            "",
            "This offline reviewer-rubric gate combines committed visual proxy",
            "evidence with the latest redacted paid image-edit canary and",
            "postmortem. It does not call a paid API and does not commit raw",
            "prompts, raw provider responses, or generated provider images.",
            "",
            "Provider-quality image editing is not claimed as proven. The current",
            "provider-quality gate still failed because the latest canary exceeded",
            "the 30 second latency threshold.",
            "",
            "## Result",
            "",
            f"- `provider_visual_review_first_gate`: "
            f"`{summary['provider_visual_review_first_gate']}`",
            f"- Offline visual proxy: {'passed' if proxy['passed'] else 'failed'} "
            f"({proxy['passed_count']}/{proxy['sample_count']}, "
            f"pass rate `{proxy['pass_rate']}`)",
            f"- Latest paid canary: model `{canary['model_id']}`, quality "
            f"`{canary['quality']}`, elapsed `{canary['elapsed_ms']} ms`",
            f"- Cost guard: {'passed' if canary['cost_guard_passed'] else 'failed'} "
            f"at `${canary['estimated_cost_usd']}`",
            f"- ROI preservation: "
            f"{'passed' if canary['roi_preservation_checks_passed'] else 'failed'}",
            f"- Text-contamination check: "
            f"{'passed' if canary['text_contamination_passed'] else 'failed'}",
            f"- Latency check: {'passed' if canary['latency_passed'] else 'failed'}",
            f"- Provider-quality claimed: `{str(summary['provider_quality_claimed']).lower()}`",
            "",
            "## Next Conditions",
            "",
            *[f"- {condition}" for condition in summary["next_conditions"]],
            "",
            "## Privacy Boundary",
            "",
            "- Paid API call made by this script: false",
            "- Raw prompt committed: false",
            "- Raw model response committed: false",
            "- Generated provider image committed: false",
            "",
        ]
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build offline provider visual review evidence without a paid API call.",
        allow_abbrev=False,
    )
    parser.add_argument("--visual-summary", type=Path, default=DEFAULT_VISUAL_SUMMARY)
    parser.add_argument("--provider-postmortem", type=Path, default=DEFAULT_PROVIDER_POSTMORTEM)
    parser.add_argument("--live-summary", type=Path, default=DEFAULT_LIVE_SUMMARY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    args = parser.parse_args()

    summary = build_provider_visual_review(
        visual_summary=_read_json(args.visual_summary),
        provider_postmortem=_read_json(args.provider_postmortem),
        live_summary=_read_json(args.live_summary),
    )
    _write_json(args.output, summary)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["provider_visual_review_first_gate"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
