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

os.environ.setdefault("OUTPUT_DIR", "outputs/agentic-rag-stream-smoke")
os.environ.setdefault("GENERATION_LOG_PATH", "logs/agentic-rag-stream-smoke-generations.jsonl")
os.environ.setdefault(
    "AGENTIC_RAG_CHECKPOINT_DB",
    "outputs/agentic-rag-checkpoints/agentic-rag-stream-smoke.sqlite",
)

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402


DEFAULT_OUTPUT_PATH = Path("docs/evidence/agentic-rag-stream-summary.json")


def build_agentic_rag_stream_summary(*, evidence_date: str) -> dict[str, Any]:
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

    node_sequence = [
        event["data"].get("node") for event in events if event["event"] == "node_completed"
    ]
    final_event = events[-1]
    return {
        "agentic_rag_stream_smoke": "passed",
        "scope": "local_fastapi_sse_no_paid_api_call",
        "evidence_date": evidence_date,
        "media_type": response.headers["content-type"],
        "run_id_prefix": run_id.split("-", maxsplit=1)[0],
        "checkpointing_enabled": events[0]["data"]["checkpointing_enabled"],
        "event_names": [event["event"] for event in events],
        "node_sequence": node_sequence,
        "final_status": final_event["data"]["status"],
        "final_next_action": final_event["data"].get("next_action"),
        "worker_status": _first_event_value(events, "worker_status"),
        "copy_option_count": _first_event_value(events, "copy_option_count"),
        "replay_status": replay["status"],
        "replay_next_action": replay["next_action"],
        "replay_checkpoint_backend": replay["checkpoint_backend"],
        "replay_checkpoint_count": replay["checkpoint_count"],
        "replay_node_sequence": replay["node_trace"],
        "replay_raw_inputs_committed": replay["raw_inputs_committed"],
        "raw_inputs_committed": False,
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


def _first_event_value(events: list[dict[str, Any]], key: str) -> Any:
    for event in events:
        if key in event["data"]:
            return event["data"][key]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build local FastAPI SSE evidence for the Agentic RAG run stream.",
        allow_abbrev=False,
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    summary = build_agentic_rag_stream_summary(evidence_date=args.date)
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    print(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
