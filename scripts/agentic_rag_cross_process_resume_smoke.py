from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("OUTPUT_DIR", "outputs/agentic-rag-cross-process-resume-smoke")
os.environ.setdefault(
    "GENERATION_LOG_PATH",
    "logs/agentic-rag-cross-process-resume-smoke-generations.jsonl",
)
os.environ.setdefault(
    "AGENTIC_RAG_CHECKPOINT_DB",
    "outputs/agentic-rag-checkpoints/agentic-rag-cross-process-resume-smoke.sqlite",
)

from fastapi.testclient import TestClient  # noqa: E402

import api.main as api_main  # noqa: E402
from api.main import app  # noqa: E402


DEFAULT_OUTPUT_PATH = Path("docs/evidence/agentic-rag-cross-process-resume-summary.json")


def build_agentic_rag_cross_process_resume_summary(
    *,
    evidence_date: str,
) -> dict[str, Any]:
    original_requires_paid_provider = api_main._agentic_rag_requires_paid_provider
    api_main._agentic_rag_requires_paid_provider = lambda _deps: True
    try:
        client = TestClient(app)
        payload = {
            "campaign_purpose": "new_menu",
            "product_name": "비공개 말차 푸딩",
            "tone": "clean",
            "template_hint": "minimal_premium",
            "price_text": "5,500원",
            "user_constraints": "VIP 고객에게만 보일 문구",
        }
        with client.stream("POST", "/agentic-rag/runs/stream", json=payload) as response:
            body = response.read().decode("utf-8")
        if response.status_code != 200:
            raise RuntimeError(f"stream endpoint failed with HTTP {response.status_code}: {body}")

        events = _parse_sse_events(body)
        run_id = events[0]["data"]["run_id"]
        replay_response = client.get(f"/agentic-rag/runs/{run_id}/replay")
        replay = replay_response.json()
        if replay_response.status_code != 200:
            raise RuntimeError(
                f"replay endpoint failed with HTTP {replay_response.status_code}: {replay}"
            )

        with api_main._AGENTIC_RAG_PENDING_APPROVAL_RUNS_LOCK:
            api_main._AGENTIC_RAG_PENDING_APPROVAL_RUNS.clear()

        approval_response = client.post(
            f"/agentic-rag/runs/{run_id}/approval",
            json={
                "decision": "approved",
                "reviewer_id": "reviewer@example.com",
                "comment": "비공개 승인 메모",
            },
        )
        approval = approval_response.json()
        if approval_response.status_code != 200:
            raise RuntimeError(
                f"approval endpoint failed with HTTP {approval_response.status_code}: {approval}"
            )

        return {
            "agentic_rag_cross_process_resume_smoke": "passed",
            "scope": "local_redacted_sqlite_replay_resume_no_paid_api_call",
            "evidence_date": evidence_date,
            "run_id_prefix": run_id.split("-", maxsplit=1)[0],
            "checkpointing_enabled": events[0]["data"]["checkpointing_enabled"],
            "approval_route_status": events[-1]["data"]["status"],
            "approval_route_next_action": events[-1]["data"]["next_action"],
            "resume_policy_mode": replay["resume_policy_mode"],
            "pending_context_cleared_before_approval": True,
            "approval_decision_status": approval["status"],
            "approval_next_action": approval["next_action"],
            "post_approval_worker_resumed": approval["post_approval_worker_resumed"],
            "post_approval_resume_source": approval["post_approval_resume_source"],
            "post_approval_worker_status": approval["post_approval_worker_status"],
            "post_approval_status": approval["post_approval_status"],
            "copy_backend": approval["copy_backend"],
            "image_backend": approval["image_backend"],
            "copy_option_count": approval["copy_option_count"],
            "used_reference": approval["used_reference"],
            "audit_persisted": approval["audit_persisted"],
            "raw_inputs_committed": False,
        }
    finally:
        api_main._agentic_rag_requires_paid_provider = original_requires_paid_provider


def _parse_sse_events(body: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw_event in body.strip().split("\n\n"):
        event_name = ""
        data = ""
        for line in raw_event.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data = line.removeprefix("data: ")
        events.append({"event": event_name, "data": json.loads(data)})
    return events


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build local redacted cross-process resume evidence for Agentic RAG.",
        allow_abbrev=False,
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    summary = build_agentic_rag_cross_process_resume_summary(evidence_date=args.date)
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    print(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
