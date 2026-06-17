from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_provider_gate_postmortem_summarizes_latest_failed_paid_gate(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "provider-gate-postmortem-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/analyze_provider_gate_failure.py",
            "--input",
            "docs/evidence/openai-image-edit-preservation-live-summary.json",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["provider_gate_postmortem"] == "failed_gate_analyzed"
    assert summary["source_summary"]["model_id"] == "gpt-image-2"
    assert summary["source_summary"]["quality"] == "medium"
    assert summary["source_summary"]["sample_count"] == 1
    assert summary["source_summary"]["estimated_cost_usd"] == 0.08859
    assert summary["source_summary"]["budget_max_usd"] == 0.1
    assert summary["source_summary"]["budget_over_by_usd"] == 0.0
    assert summary["preservation_result"]["roi_preservation_checks_passed"] is True
    assert summary["failure_counts"]["sample_elapsed_ms_le_threshold"] == 1
    assert "text_contamination_risk_le_threshold" not in summary["failure_counts"]
    assert "cost_guard_passed" not in summary["failure_counts"]
    assert summary["root_causes"] == ["latency_threshold_exceeded"]
    assert summary["next_paid_gate_conditions"] == [
        "review generated outputs locally before another paid full gate",
        (
            "decide whether to relax the latency threshold, switch model/quality, "
            "or keep provider-quality image editing unproven"
        ),
        "set an OpenAI dashboard hard budget because the script budget is post-response only",
        "keep deterministic Korean overlay rendering outside the image model",
    ]


def test_provider_gate_postmortem_handles_passing_summary(tmp_path: Path) -> None:
    input_path = tmp_path / "passing-summary.json"
    output_path = tmp_path / "provider-gate-postmortem-summary.json"
    input_path.write_text(
        json.dumps(
            {
                "openai_image_edit_preservation": "passed",
                "model_id": "gpt-image-test",
                "quality": "low",
                "elapsed_ms": 10_000,
                "usage": {"sample_count": 1, "total_tokens": 100},
                "cost": {"total_usd": 0.01, "budget": {"passed": True}},
                "cost_guard": {"passed": True},
                "provider_quality_gate": {
                    "passed": True,
                    "sample_count": 1,
                    "passed_count": 1,
                    "pass_rate": 1.0,
                },
                "sample_results": [
                    {
                        "checklist": {
                            "roi_color_histogram_similarity_ge_threshold": True,
                            "roi_average_hash_similarity_ge_threshold": True,
                            "roi_edge_similarity_ge_threshold": True,
                            "sample_elapsed_ms_le_threshold": True,
                            "text_contamination_risk_le_threshold": True,
                        },
                        "metrics": {"text_contamination_risk_score": 0.0},
                    }
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/analyze_provider_gate_failure.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["provider_gate_postmortem"] == "passed_gate_reviewed"
    assert summary["failure_counts"] == {}
    assert summary["root_causes"] == []
