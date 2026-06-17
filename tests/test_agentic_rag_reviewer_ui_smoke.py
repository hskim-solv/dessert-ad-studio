from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_agentic_rag_reviewer_ui_smoke_writes_redacted_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "agentic-rag-reviewer-ui-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/agentic_rag_reviewer_ui_smoke.py",
            "--date",
            "2026-06-17",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["agentic_rag_reviewer_ui_smoke"] == "passed"
    assert summary["scope"] == "local_streamlit_reviewer_approval_ui_no_paid_api_call"
    assert summary["evidence_date"] == "2026-06-17"
    assert summary["streamlit_session_key"] == "agentic_rag_runs"
    assert summary["approval_run"]["status"] == "needs_approval"
    assert summary["approval_run"]["next_action"] == "wait_for_human_approval"
    assert summary["ui_decision"]["status"] == "approved"
    assert summary["ui_decision"]["next_action"] == "return_cited_ad_package"
    assert summary["ui_decision"]["post_approval_worker_resumed"] is True
    assert summary["ui_decision"]["post_approval_worker_status"] == "succeeded"
    assert summary["ui_decision"]["post_approval_status"] == "completed"
    assert len(summary["ui_decision"]["reviewer_id_sha256"]) == 64
    assert len(summary["ui_decision"]["comment_sha256"]) == 64
    assert summary["ui_decision"]["raw_inputs_committed"] is False
    assert summary["privacy_boundary"]["raw_reviewer_id_committed"] is False
    assert summary["privacy_boundary"]["raw_comment_committed"] is False
    assert summary["privacy_boundary"]["paid_api_call_count"] == 0

    serialized = json.dumps(summary, ensure_ascii=False)
    for raw_value in [
        "reviewer@example.com",
        "VIP 고객 원문이 담긴 비공개 승인 메모",
        "비공개 말차 푸딩",
    ]:
        assert raw_value not in serialized
