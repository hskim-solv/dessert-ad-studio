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

os.environ.setdefault("OUTPUT_DIR", "outputs/agentic-rag-websocket-smoke")
os.environ.setdefault(
    "GENERATION_LOG_PATH",
    "logs/agentic-rag-websocket-smoke-generations.jsonl",
)
os.environ.setdefault(
    "AGENTIC_RAG_CHECKPOINT_DB",
    "outputs/agentic-rag-checkpoints/agentic-rag-websocket-smoke.sqlite",
)

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402


DEFAULT_OUTPUT_PATH = Path("docs/evidence/agentic-rag-websocket-summary.json")


def build_agentic_rag_websocket_summary(*, evidence_date: str) -> dict[str, Any]:
    client = TestClient(app)
    payload = {
        "campaign_purpose": "new_menu",
        "product_name": "비공개 말차 푸딩",
        "tone": "clean",
        "template_hint": "minimal_premium",
        "price_text": "5,500원",
        "user_constraints": "VIP 고객에게만 보일 문구",
    }

    with client.websocket_connect("/agentic-rag/runs/ws") as websocket:
        websocket.send_json(payload)
        messages = _receive_messages(websocket)

    run_started = messages[0]["data"]
    final_event = messages[-1]
    node_sequence = [
        message["data"].get("node") for message in messages if message["event"] == "node_completed"
    ]

    return {
        "agentic_rag_websocket_smoke": "passed",
        "scope": "local_fastapi_websocket_no_paid_api_call",
        "evidence_date": evidence_date,
        "stream_protocol": run_started["stream_protocol"],
        "run_id_prefix": run_started["run_id"].split("-", maxsplit=1)[0],
        "checkpointing_enabled": run_started["checkpointing_enabled"],
        "event_names": [message["event"] for message in messages],
        "node_sequence": node_sequence,
        "final_status": final_event["data"]["status"],
        "final_next_action": final_event["data"].get("next_action"),
        "worker_status": _first_message_value(messages, "worker_status"),
        "copy_option_count": _first_message_value(messages, "copy_option_count"),
        "raw_inputs_committed": False,
    }


def _receive_messages(websocket) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    while True:
        message = websocket.receive_json()
        messages.append(message)
        if message["event"] == "run_completed":
            return messages


def _first_message_value(messages: list[dict[str, Any]], key: str) -> Any:
    for message in messages:
        if key in message["data"]:
            return message["data"][key]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build local FastAPI WebSocket evidence for the Agentic RAG run stream.",
        allow_abbrev=False,
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    summary = build_agentic_rag_websocket_summary(evidence_date=args.date)
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    print(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
