from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_agentic_rag_final_readiness_script_writes_boundary_audit(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "agentic-rag-final-readiness.md"
    summary_path = tmp_path / "agentic-rag-final-readiness-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_agentic_rag_final_readiness.py",
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

    assert summary["agentic_rag_final_readiness"] == "passed"
    assert summary["scope"] == "portfolio_boundary_audit_no_paid_api_call"
    assert summary["missing_artifacts"] == []
    assert summary["evidence_index_integrity"]["passed"] is True
    assert summary["evidence_index_integrity"]["missing_from_evidence_index"] == []
    assert summary["evidence_index_integrity"]["checked_artifact_count"] == len(
        summary["source_artifacts"]
    )
    assert summary["ci_gate_integrity"]["passed"] is True
    assert summary["ci_gate_integrity"]["workflow"] == ".github/workflows/ci.yml"
    assert (
        summary["ci_gate_integrity"]["required_strings_present"]
        == (summary["ci_gate_integrity"]["required_strings_total"])
    )
    assert summary["ci_gate_integrity"]["missing_required_strings"] == []
    assert summary["claim_boundary_integrity"]["passed"] is True
    assert (
        summary["claim_boundary_integrity"]["required_phrase_checks_passed"]
        == summary["claim_boundary_integrity"]["required_phrase_checks_total"]
    )
    assert summary["claim_boundary_integrity"]["missing_required_phrases"] == []
    assert summary["claim_boundary_integrity"]["forbidden_phrase_hits"] == []
    assert summary["capability_counts"]["total"] == 9
    assert summary["capability_counts"]["passed"] == 9
    assert summary["capability_counts"]["not_claimed"] == 1
    assert summary["completion_claim"]["production_complete"] is False
    assert "live/API-key" in summary["completion_claim"]["reason"]
    assert summary["pending_decision_register"]["decision_count"] == 9
    assert (
        summary["pending_decision_register"]["decisions_requiring_user_approval"]
        == summary["pending_decision_register"]["decision_count"]
    )
    assert summary["pending_decision_register"]["production_claim_added"] is False
    assert (
        "cloud_deployment_and_recorded_demo"
        in (summary["pending_decision_register"]["decision_ids"])
    )
    assert summary["provider_quality_boundary"]["provider_quality_claimed"] is False
    assert summary["provider_quality_boundary"]["provider_quality_unproven"] is True
    assert summary["provider_quality_boundary"]["root_causes"] == ["latency_threshold_exceeded"]
    assert summary["privacy_boundary"]["paid_api_call_count"] == 0
    assert summary["privacy_boundary"]["raw_inputs_committed"] is False

    capabilities = {item["id"]: item for item in summary["capabilities"]}
    assert capabilities["backend_async_streaming"]["status"] == "first_gate_passed"
    assert capabilities["evaluation_and_ci"]["status"] == (
        "first_gate_passed_with_live_ragas_pending"
    )
    assert capabilities["deployment_packaging"]["status"] == (
        "first_gate_passed_with_cloud_demo_file_pending"
    )
    assert capabilities["provider_quality_claim_boundary"]["status"] == "not_claimed"

    assert "# Agentic RAG Final Readiness Audit" in report
    assert "Production complete: `False`" in report
    assert "`provider_quality_claim_boundary`" in report
    assert "latency_threshold_exceeded" in report
    assert "Evidence Index Integrity" in report
    assert "CI Gate Integrity" in report
    assert "Claim Boundary Integrity" in report
    assert "docs/evidence/agentic-rag-decision-register-summary.json" in report


def test_agentic_rag_final_readiness_check_mode_detects_stale_outputs(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "agentic-rag-final-readiness.md"
    summary_path = tmp_path / "agentic-rag-final-readiness-summary.json"
    base_command = [
        sys.executable,
        "scripts/build_agentic_rag_final_readiness.py",
        "--date",
        "2026-06-17",
        "--report-output",
        str(report_path),
        "--summary-output",
        str(summary_path),
    ]

    write_completed = subprocess.run(
        base_command,
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    assert write_completed.returncode == 0, write_completed.stderr + write_completed.stdout

    check_completed = subprocess.run(
        [*base_command, "--check"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    assert check_completed.returncode == 0, check_completed.stderr + check_completed.stdout
    check_summary = json.loads(check_completed.stdout)
    assert check_summary["agentic_rag_final_readiness_check"] == "passed"
    assert check_summary["mismatches"] == []

    report_path.write_text(report_path.read_text(encoding="utf-8") + "\nSTALE\n")
    stale_completed = subprocess.run(
        [*base_command, "--check"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    assert stale_completed.returncode == 1
    stale_summary = json.loads(stale_completed.stdout)
    assert stale_summary["agentic_rag_final_readiness_check"] == "failed"
    assert stale_summary["mismatches"] == [
        {"path": str(report_path), "reason": "stale_or_modified"}
    ]
