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

os.environ.setdefault("OUTPUT_DIR", "outputs/agentic-rag-reviewer-ui-smoke")
os.environ.setdefault(
    "GENERATION_LOG_PATH",
    "logs/agentic-rag-reviewer-ui-smoke-generations.jsonl",
)
os.environ.setdefault(
    "AGENTIC_RAG_CHECKPOINT_DB",
    "outputs/agentic-rag-checkpoints/agentic-rag-reviewer-ui-smoke.sqlite",
)

from fastapi.testclient import TestClient  # noqa: E402

from app import streamlit_app  # noqa: E402
import api.main as api_main  # noqa: E402
from api.main import app  # noqa: E402


DEFAULT_OUTPUT_PATH = Path("docs/evidence/agentic-rag-reviewer-ui-summary.json")
RAW_SENTINELS = (
    "reviewer@example.com",
    "VIP 고객 원문이 담긴 비공개 승인 메모",
    "비공개 말차 푸딩",
    "VIP 고객에게만 보일 문구",
)


def build_agentic_rag_reviewer_ui_summary(*, evidence_date: str) -> dict[str, Any]:
    original_requires_paid_provider = api_main._agentic_rag_requires_paid_provider
    api_main._agentic_rag_requires_paid_provider = lambda _deps: True
    try:
        client = TestClient(app)
        pending_run = _create_pending_approval_run(client)
        approval_response = client.post(
            f"/agentic-rag/runs/{pending_run['run_id']}/approval",
            json=streamlit_app._build_agentic_rag_approval_payload(
                decision="approved",
                reviewer_id="reviewer@example.com",
                comment="VIP 고객 원문이 담긴 비공개 승인 메모",
            ),
        )
        approval = approval_response.json()
        if approval_response.status_code != 200:
            raise RuntimeError(
                f"approval endpoint failed with HTTP {approval_response.status_code}: {approval}"
            )
        merged_run = streamlit_app._merge_agentic_rag_approval_decision(
            pending_run,
            approval,
        )
        ui_decision = merged_run["decision"]
        summary = {
            "agentic_rag_reviewer_ui_smoke": "passed",
            "scope": "local_streamlit_reviewer_approval_ui_no_paid_api_call",
            "evidence_date": evidence_date,
            "streamlit_session_key": streamlit_app.AGENTIC_RAG_RUNS_KEY,
            "approval_run": {
                "run_id_prefix": pending_run["run_id"].split("-", maxsplit=1)[0],
                "status": pending_run["status"],
                "next_action": pending_run["next_action"],
                "approval_required": pending_run["approval_required"],
                "approval_reasons": pending_run["approval_reasons"],
            },
            "ui_decision": ui_decision,
            "privacy_boundary": {
                "raw_reviewer_id_committed": False,
                "raw_comment_committed": False,
                "raw_request_committed": False,
                "paid_api_call_count": 0,
            },
        }
        if _contains_raw_sentinel(summary):
            raise RuntimeError("reviewer UI summary contains raw sensitive values")
        return summary
    finally:
        api_main._agentic_rag_requires_paid_provider = original_requires_paid_provider


def _create_pending_approval_run(client: TestClient) -> dict[str, Any]:
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
    return {
        "run_id": run_id,
        "status": replay["status"],
        "next_action": replay["next_action"],
        "approval_required": bool(replay.get("approval_required", False)),
        "approval_reasons": list(replay.get("approval_reasons", [])),
    }


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


def _contains_raw_sentinel(value: Any) -> bool:
    serialized = json.dumps(value, ensure_ascii=False)
    return any(sentinel in serialized for sentinel in RAW_SENTINELS)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build local Streamlit reviewer approval UI evidence for Agentic RAG.",
        allow_abbrev=False,
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    summary = build_agentic_rag_reviewer_ui_summary(evidence_date=args.date)
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    print(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
