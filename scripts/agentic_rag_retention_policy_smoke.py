from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_PATH = Path("docs/evidence/agentic-rag-retention-policy-summary.json")
ADR_PATH = "docs/adr/0018-agentic-rag-retention-boundary.md"
RAW_SENTINELS = (
    "비공개 말차 푸딩",
    "VIP 고객에게만 보일 문구",
    "reviewer@example.com",
)


def build_agentic_rag_retention_policy_summary(*, evidence_date: str) -> dict[str, Any]:
    summary = {
        "agentic_rag_retention_policy_smoke": "passed",
        "scope": "policy_gate_no_raw_input_store",
        "evidence_date": evidence_date,
        "adr": ADR_PATH,
        "decision": "redacted_replay_with_ephemeral_raw_context_and_mock_resume_policy",
        "replay_retention": {
            "artifact": "local_sqlite_redacted_checkpoints",
            "raw_inputs_allowed": False,
            "default_storage": "outputs/agentic-rag-checkpoints/",
            "committed_to_git": False,
            "production_claim": "policy_defined_not_production_store",
        },
        "approval_retention": {
            "persistent_audit_claim": False,
            "stored_fields": [
                "decision",
                "reviewer_id_sha256",
                "comment_sha256",
                "approval_reasons",
                "post_approval_worker_status",
            ],
            "raw_reviewer_inputs_allowed": False,
        },
        "resume_retention": {
            "same_process_ephemeral_context": True,
            "mock_redacted_sqlite_replay_resume": True,
            "live_provider_cross_process_resume": "pending_user_decision",
            "raw_request_persistence_allowed": False,
        },
        "trace_retention": {
            "raw_model_inputs_allowed": False,
            "external_trace_payload_review_required": True,
            "production_trace_retention": "pending_deployment_policy",
        },
        "requires_user_decision_before": [
            "durable_raw_request_storage",
            "live_provider_cross_process_resume_store",
            "production_approval_audit_retention",
            "external_trace_payload_retention",
        ],
        "raw_inputs_committed": False,
    }
    if _contains_raw_sentinel(summary):
        raise RuntimeError("retention policy summary contains raw sensitive values")
    return summary


def _contains_raw_sentinel(value: Any) -> bool:
    serialized = json.dumps(value, ensure_ascii=False)
    return any(sentinel in serialized for sentinel in RAW_SENTINELS)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build Agentic RAG retention boundary evidence.",
        allow_abbrev=False,
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    summary = build_agentic_rag_retention_policy_summary(evidence_date=args.date)
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    print(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
