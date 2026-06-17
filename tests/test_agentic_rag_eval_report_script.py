from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_agentic_rag_eval_report_script_writes_reviewer_report(tmp_path: Path) -> None:
    report_path = tmp_path / "agentic-rag-eval-report.md"
    summary_path = tmp_path / "agentic-rag-eval-report-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_agentic_rag_eval_report.py",
            "--date",
            "2026-06-17",
            "--report-output",
            str(report_path),
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
    report = report_path.read_text(encoding="utf-8")

    assert summary["agentic_rag_eval_report"] == "passed"
    assert summary["scope"] == "offline_reviewer_eval_report_no_paid_api_call"
    assert summary["evidence_date"] == "2026-06-17"
    assert summary["golden_eval"]["case_count"] >= 13
    assert summary["golden_eval"]["faithfulness"] == 1.0
    assert summary["golden_eval"]["answer_relevancy"] == 1.0
    assert summary["retrieval"]["keyword_category_hit_rate"] >= 1.0
    assert summary["retrieval"]["chunking_selected_strategy"] == "field_aware"
    assert summary["retrieval"]["pgvector_precision"] >= 1.0
    assert summary["promptfoo"]["passed"] is True
    assert summary["guardrails"]["prompt_injection_blocked"] is True
    assert summary["guardrails"]["raw_inputs_absent"] is True
    assert summary["limits"]["ragas_live_gate"] == "pending_paid_api_approval"
    assert summary["limits"]["live_web_search_runtime_policy"] == "first_gate_complete"
    assert summary["limits"]["live_web_search_provider_smoke"] == "pending_user_approval"
    assert summary["limits"]["production_db_access_audit_policy"] == "first_gate_complete"
    assert summary["limits"]["credentialed_production_db_smoke"] == "pending_user_approval"
    assert summary["limits"]["local_sql_runtime_policy"] == "first_gate_complete"
    assert summary["limits"]["mcp_loopback_transport_auth_boundary"] == "first_gate_complete"
    assert (
        summary["limits"]["production_mcp_auth_remote_client"] == "pending_runtime_security_policy"
    )
    assert summary["privacy_boundary"]["raw_inputs_committed"] is False

    assert "# Agentic RAG Eval Report" in report
    assert "Faithfulness" in report
    assert "promptfoo" in report
    assert "Ragas live metrics remain pending" in report
    assert (
        "The live web search runtime policy, local SQL runtime policy, production\n"
        "DB access/audit policy, and MCP loopback transport/auth boundary first gates\n"
        "are complete"
    ) in report
    assert "docs/evidence/agentic-rag-eval-guardrail-summary.json" in report
