from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_agentic_rag_decision_register_writes_gated_pending_scope(
    tmp_path: Path,
) -> None:
    summary_path = tmp_path / "agentic-rag-decision-register-summary.json"
    report_path = tmp_path / "agentic-rag-decision-register.md"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_agentic_rag_decision_register.py",
            "--date",
            "2026-06-17",
            "--summary-output",
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
    report = report_path.read_text(encoding="utf-8")

    assert summary["agentic_rag_decision_register"] == "passed"
    assert summary["scope"] == "pending_user_decision_register_no_external_calls"
    assert summary["evidence_date"] == "2026-06-17"
    assert summary["external_calls_made"] is False
    assert summary["paid_api_calls_made"] is False
    assert summary["production_claim_added"] is False
    assert summary["decision_count"] >= 8
    assert summary["decisions_requiring_user_approval"] == summary["decision_count"]

    decision_ids = {item["id"] for item in summary["decisions"]}
    assert {
        "ragas_live_eval",
        "live_web_search_provider_smoke",
        "credentialed_production_db_smoke",
        "production_mcp_remote_auth",
        "live_provider_cross_process_resume",
        "production_replay_audit_storage",
        "external_trace_backend_customer_capture",
        "image_edit_latency_strategy",
        "cloud_deployment_and_recorded_demo",
    }.issubset(decision_ids)

    for item in summary["decisions"]:
        assert item["status"] == "pending_user_decision"
        assert item["approval_required"] is True
        assert item["no_claim_until_approved"] is True
        assert item["next_evidence_artifact"]
        assert item["approval_reason"] in {
            "paid_api_or_eval_llm",
            "credentialed_external_service",
            "production_storage_or_retention",
            "production_auth_security_boundary",
            "cloud_or_public_deployment",
            "provider_quality_claim_boundary",
        }

    assert "Agentic RAG Pending Decision Register" in report
    assert "No external calls were made" in report
    assert "provider-quality image editing remains unproven" in report
