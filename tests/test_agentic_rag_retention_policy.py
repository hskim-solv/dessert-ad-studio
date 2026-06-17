from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_agentic_rag_retention_policy_smoke_writes_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "agentic-rag-retention-policy-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/agentic_rag_retention_policy_smoke.py",
            "--date",
            "2026-06-17",
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

    assert summary["agentic_rag_retention_policy_smoke"] == "passed"
    assert summary["scope"] == "policy_gate_no_runtime_retention_change"
    assert summary["evidence_date"] == "2026-06-17"
    assert summary["adr"] == "docs/adr/0018-agentic-rag-retention-boundary.md"
    assert summary["decision"] == "redacted_replay_with_ephemeral_raw_context"
    assert summary["replay_retention"]["artifact"] == "local_sqlite_redacted_checkpoints"
    assert summary["replay_retention"]["raw_inputs_allowed"] is False
    assert summary["approval_retention"]["persistent_audit_claim"] is False
    assert summary["resume_retention"]["same_process_ephemeral_context"] is True
    assert summary["resume_retention"]["durable_cross_process_resume"] == "pending_user_decision"
    assert summary["trace_retention"]["raw_model_inputs_allowed"] is False
    assert summary["requires_user_decision_before"] == [
        "durable_raw_request_storage",
        "cross_process_resume_store",
        "production_approval_audit_retention",
        "external_trace_payload_retention",
    ]
    assert summary["raw_inputs_committed"] is False

    serialized = json.dumps(summary, ensure_ascii=False)
    for raw_value in [
        "비공개 말차 푸딩",
        "VIP 고객에게만 보일 문구",
        "reviewer@example.com",
    ]:
        assert raw_value not in serialized
