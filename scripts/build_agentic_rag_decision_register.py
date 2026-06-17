from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date
import json
from pathlib import Path
from typing import Literal


DEFAULT_SUMMARY_OUTPUT = Path("docs/evidence/agentic-rag-decision-register-summary.json")
DEFAULT_REPORT_OUTPUT = Path("docs/evidence/agentic-rag-decision-register.md")
ApprovalReason = Literal[
    "paid_api_or_eval_llm",
    "credentialed_external_service",
    "production_storage_or_retention",
    "production_auth_security_boundary",
    "cloud_or_public_deployment",
    "provider_quality_claim_boundary",
]


@dataclass(frozen=True)
class PendingDecision:
    id: str
    title: str
    status: str
    approval_required: bool
    approval_reason: ApprovalReason
    no_claim_until_approved: bool
    current_boundary: str
    decision_needed: str
    next_evidence_artifact: str
    next_command_or_action: str


def pending_decisions() -> list[PendingDecision]:
    return [
        PendingDecision(
            id="ragas_live_eval",
            title="Run evaluator-LLM Ragas live metrics",
            status="pending_user_decision",
            approval_required=True,
            approval_reason="paid_api_or_eval_llm",
            no_claim_until_approved=True,
            current_boundary="Local Ragas-compatible proxy and promptfoo package gates are complete.",
            decision_needed="Approve paid/API-key evaluator execution and trace/result payload review.",
            next_evidence_artifact="docs/evidence/agentic-rag-eval-guardrail.md",
            next_command_or_action="Run the approved Ragas live gate with redacted output only.",
        ),
        PendingDecision(
            id="live_web_search_provider_smoke",
            title="Run live web search provider smoke",
            status="pending_user_decision",
            approval_required=True,
            approval_reason="credentialed_external_service",
            no_claim_until_approved=True,
            current_boundary="Live web search runtime policy is defined without credentials.",
            decision_needed="Select provider/API key, domain allowlist, and retention boundary.",
            next_evidence_artifact="docs/evidence/agentic-rag-tools-summary.json",
            next_command_or_action="Run a redacted live provider smoke after provider selection.",
        ),
        PendingDecision(
            id="credentialed_production_db_smoke",
            title="Run credentialed production DB smoke",
            status="pending_user_decision",
            approval_required=True,
            approval_reason="credentialed_external_service",
            no_claim_until_approved=True,
            current_boundary="Production DB access/audit policy first gate is complete without credentials.",
            decision_needed="Approve database target, readonly role, network path, audit retention, and rollback.",
            next_evidence_artifact="docs/evidence/agentic-rag-tools-summary.json",
            next_command_or_action="Run allowlisted readonly query smoke with redacted audit summary.",
        ),
        PendingDecision(
            id="production_mcp_remote_auth",
            title="Select MCP production auth provider and remote client smoke",
            status="pending_user_decision",
            approval_required=True,
            approval_reason="production_auth_security_boundary",
            no_claim_until_approved=True,
            current_boundary="Loopback transport/auth boundary and remote client auth contract are defined.",
            decision_needed="Choose auth provider, token issuance path, TLS/origin boundary, and client allowlist.",
            next_evidence_artifact="docs/evidence/agentic-rag-mcp-server-summary.json",
            next_command_or_action="Run remote client auth smoke against the approved endpoint.",
        ),
        PendingDecision(
            id="live_provider_cross_process_resume",
            title="Live-provider cross-process resume",
            status="pending_user_decision",
            approval_required=True,
            approval_reason="production_storage_or_retention",
            no_claim_until_approved=True,
            current_boundary="Same-process resume and mock-only redacted SQLite cross-process resume are complete.",
            decision_needed="Approve durable request/provider payload storage policy or keep live-provider resume unclaimed.",
            next_evidence_artifact="docs/evidence/agentic-rag-cross-process-resume.md",
            next_command_or_action="Run live-provider resume smoke only after storage/retention approval.",
        ),
        PendingDecision(
            id="production_replay_audit_storage",
            title="Production replay and approval audit storage",
            status="pending_user_decision",
            approval_required=True,
            approval_reason="production_storage_or_retention",
            no_claim_until_approved=True,
            current_boundary="Redacted local replay, approval metadata, and 7-day trace contract first gates are complete.",
            decision_needed="Approve storage location, retention period, deletion behavior, and user/project/entity scope.",
            next_evidence_artifact="docs/evidence/agentic-rag-retention-policy.md",
            next_command_or_action="Implement approved Postgres/object-store retention path and smoke it.",
        ),
        PendingDecision(
            id="external_trace_backend_customer_capture",
            title="External trace backend and production customer capture",
            status="pending_user_decision",
            approval_required=True,
            approval_reason="production_storage_or_retention",
            no_claim_until_approved=True,
            current_boundary="Deployment trace retention contract is complete; no external backend is configured.",
            decision_needed="Select backend, retention above or equal to 7 days, and customer trace capture policy.",
            next_evidence_artifact="docs/evidence/agentic-rag-retention-policy-summary.json",
            next_command_or_action="Run external trace smoke with allowlisted attributes only.",
        ),
        PendingDecision(
            id="image_edit_latency_strategy",
            title="Paid image-edit latency strategy",
            status="pending_user_decision",
            approval_required=True,
            approval_reason="provider_quality_claim_boundary",
            no_claim_until_approved=True,
            current_boundary=(
                "Latest paid canary passed API/cost/ROI/text checks but failed the 30s latency threshold; "
                "provider-quality image editing remains unproven."
            ),
            decision_needed="Keep 30s target, relax portfolio threshold with rationale, or switch model/quality.",
            next_evidence_artifact="docs/evidence/openai-image-edit-preservation.md",
            next_command_or_action="Run the approved paid canary/full gate after the latency strategy is chosen.",
        ),
        PendingDecision(
            id="cloud_deployment_and_recorded_demo",
            title="Cloud deployment path and final recorded demo",
            status="pending_user_decision",
            approval_required=True,
            approval_reason="cloud_or_public_deployment",
            no_claim_until_approved=True,
            current_boundary="Docker, GitHub Actions, K8s/kind, architecture diagram, eval report, and storyboard are complete.",
            decision_needed="Select AWS/GCP/Azure or keep kind-only evidence, then approve final recording/link policy.",
            next_evidence_artifact="docs/evidence/demo-video-storyboard.md",
            next_command_or_action="Deploy or record only after cloud/recording scope is selected.",
        ),
    ]


def build_decision_register_summary(*, evidence_date: str) -> dict[str, object]:
    decisions = [asdict(decision) for decision in pending_decisions()]
    return {
        "agentic_rag_decision_register": "passed",
        "scope": "pending_user_decision_register_no_external_calls",
        "evidence_date": evidence_date,
        "external_calls_made": False,
        "paid_api_calls_made": False,
        "production_claim_added": False,
        "decision_count": len(decisions),
        "decisions_requiring_user_approval": sum(
            1 for decision in decisions if decision["approval_required"]
        ),
        "decisions": decisions,
    }


def render_decision_register(summary: dict[str, object]) -> str:
    decisions = summary["decisions"]
    assert isinstance(decisions, list)
    rows = "\n".join(_render_decision_row(decision) for decision in decisions)
    return f"""# Agentic RAG Pending Decision Register

Date: {summary["evidence_date"]}

No external calls were made. No paid API calls were made. This register keeps
the portfolio boundary explicit: pending items are not production claims, and
provider-quality image editing remains unproven until the latency strategy is
resolved and a later paid gate passes.

## Summary

- `agentic_rag_decision_register`: `{summary["agentic_rag_decision_register"]}`
- Decision count: `{summary["decision_count"]}`
- Decisions requiring user approval: `{summary["decisions_requiring_user_approval"]}`
- Production claim added: `{str(summary["production_claim_added"]).lower()}`

## Decisions

| ID | Approval reason | Current boundary | Decision needed | Next evidence |
|---|---|---|---|---|
{rows}

## Reproduce

```bash
.venv/bin/python scripts/build_agentic_rag_decision_register.py \\
  --date {summary["evidence_date"]} \\
  --summary-output docs/evidence/agentic-rag-decision-register-summary.json \\
  --report-output docs/evidence/agentic-rag-decision-register.md
```
"""


def _render_decision_row(decision: object) -> str:
    assert isinstance(decision, dict)
    return (
        f"| `{decision['id']}` | `{decision['approval_reason']}` | "
        f"{decision['current_boundary']} | {decision['decision_needed']} | "
        f"`{decision['next_evidence_artifact']}` |"
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the Agentic RAG pending user-decision register.",
        allow_abbrev=False,
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify committed outputs are up to date without rewriting them.",
    )
    args = parser.parse_args()

    summary = build_decision_register_summary(evidence_date=args.date)
    summary_payload = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    report_payload = render_decision_register(summary)

    if args.check:
        mismatches = _find_output_mismatches(
            summary_output=args.summary_output,
            expected_summary=summary_payload,
            report_output=args.report_output,
            expected_report=report_payload,
        )
        check_payload = {
            "agentic_rag_decision_register_check": "passed" if not mismatches else "failed",
            "checked_outputs": [str(args.summary_output), str(args.report_output)],
            "mismatches": mismatches,
        }
        print(json.dumps(check_payload, ensure_ascii=False, indent=2))
        return 0 if not mismatches and summary["agentic_rag_decision_register"] == "passed" else 1

    _write_json(args.summary_output, summary)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(report_payload, encoding="utf-8")
    print(summary_payload.rstrip())
    return 0


def _find_output_mismatches(
    *,
    summary_output: Path,
    expected_summary: str,
    report_output: Path,
    expected_report: str,
) -> list[dict[str, str]]:
    mismatches: list[dict[str, str]] = []
    for path, expected in (
        (summary_output, expected_summary),
        (report_output, expected_report),
    ):
        if not path.exists():
            mismatches.append({"path": str(path), "reason": "missing"})
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            mismatches.append({"path": str(path), "reason": "stale_or_modified"})
    return mismatches


if __name__ == "__main__":
    raise SystemExit(main())
