from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_demo_video_storyboard_script_writes_reviewer_artifacts(tmp_path: Path) -> None:
    storyboard_path = tmp_path / "demo-video-storyboard.md"
    summary_path = tmp_path / "demo-video-storyboard-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_demo_video_storyboard.py",
            "--date",
            "2026-06-17",
            "--storyboard-output",
            str(storyboard_path),
            "--summary-output",
            str(summary_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    storyboard = storyboard_path.read_text(encoding="utf-8")

    assert summary["demo_video_storyboard"] == "passed"
    assert summary["scope"] == "offline_reviewer_demo_video_plan_no_paid_api_call"
    assert summary["evidence_date"] == "2026-06-17"
    assert summary["shot_count"] >= 7
    assert summary["estimated_duration_seconds"] <= 180
    assert summary["actual_video_file_committed"] is False
    assert summary["provider_quality_claimed"] is False
    assert summary["privacy_boundary"]["raw_customer_data_committed"] is False
    assert summary["privacy_boundary"]["paid_api_call_count"] == 0
    assert summary["coverage"]["agentic_rag_control_plane"] is True
    assert summary["coverage"]["streaming_and_hitl"] is True
    assert summary["coverage"]["eval_report"] is True
    assert summary["coverage"]["provider_quality_failure_disclosed"] is True
    assert summary["coverage"]["provider_visual_review_disclosed"] is True

    for artifact in summary["referenced_artifacts"]:
        assert (ROOT / artifact).exists(), artifact

    assert "# Demo Video Storyboard" in storyboard
    assert "Production-grade Agentic RAG System" in storyboard
    assert "Do not claim provider-quality image editing" in storyboard
    assert "docs/evidence/provider-visual-review.md" in storyboard
    assert "docs/evidence/agentic-rag-eval-report.md" in storyboard
    assert "docs/evidence/assets/streamlit-reviewer-result.png" in storyboard
