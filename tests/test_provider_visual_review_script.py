from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_provider_visual_review_builds_non_claiming_first_gate(
    tmp_path: Path,
) -> None:
    summary_path = tmp_path / "provider-visual-review-summary.json"
    report_path = tmp_path / "provider-visual-review.md"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_provider_visual_review.py",
            "--output",
            str(summary_path),
            "--report-output",
            str(report_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert summary["provider_visual_review_first_gate"] == "passed"
    assert summary["scope"] == "offline_reviewer_rubric_no_paid_api_call"
    assert summary["provider_quality_claimed"] is False
    assert summary["provider_quality_gate_passed"] is False
    assert summary["provider_quality_unproven"] is True
    assert summary["latest_paid_canary"]["api_reached"] is True
    assert summary["latest_paid_canary"]["cost_guard_passed"] is True
    assert summary["latest_paid_canary"]["roi_preservation_checks_passed"] is True
    assert summary["latest_paid_canary"]["text_contamination_passed"] is True
    assert summary["latest_paid_canary"]["latency_passed"] is False
    assert summary["latest_paid_canary"]["root_causes"] == ["latency_threshold_exceeded"]
    assert summary["offline_visual_proxy"]["passed"] is True
    assert summary["offline_visual_proxy"]["sample_count"] == 6
    assert summary["manual_local_review"]["visible_text_found"] is False
    assert summary["privacy_boundary"]["paid_api_call_made_by_script"] is False
    assert summary["privacy_boundary"]["generated_image_committed"] is False
    assert "latency strategy" in " ".join(summary["next_conditions"])

    report = report_path.read_text(encoding="utf-8")
    assert "Provider Visual Review Evidence" in report
    assert "Provider-quality image editing is not claimed as proven" in report


def test_provider_visual_review_fails_when_visual_proxy_failed(tmp_path: Path) -> None:
    visual_summary_path = tmp_path / "visual-quality-summary.json"
    visual_summary_path.write_text(
        json.dumps(
            {
                "visual_quality_eval": "failed",
                "sample_count": 1,
                "passed_count": 0,
                "pass_rate": 0.0,
                "items": [],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path = tmp_path / "provider-visual-review-summary.json"
    report_path = tmp_path / "provider-visual-review.md"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_provider_visual_review.py",
            "--visual-summary",
            str(visual_summary_path),
            "--output",
            str(summary_path),
            "--report-output",
            str(report_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 1
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["provider_visual_review_first_gate"] == "failed"
    assert summary["provider_quality_claimed"] is False
