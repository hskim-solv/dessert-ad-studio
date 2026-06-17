from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_agentic_rag_stream_smoke_writes_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "agentic-rag-stream-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/agentic_rag_stream_smoke.py",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["agentic_rag_stream_smoke"] == "passed"
    assert summary["scope"] == "local_fastapi_sse_no_paid_api_call"
    assert summary["media_type"].startswith("text/event-stream")
    assert summary["run_id_prefix"] == "agr"
    assert summary["checkpointing_enabled"] is True
    assert summary["event_names"] == [
        "run_started",
        "node_completed",
        "node_completed",
        "node_completed",
        "node_completed",
        "node_completed",
        "node_completed",
        "node_completed",
        "run_completed",
    ]
    assert summary["node_sequence"] == [
        "plan_campaign",
        "run_tool_suite",
        "retrieve_context",
        "build_citations",
        "guardrail_check",
        "execute_worker",
        "finalize",
    ]
    assert summary["final_status"] == "completed"
    assert summary["final_next_action"] == "return_cited_ad_package"
    assert summary["replay_status"] == "completed"
    assert summary["replay_next_action"] == "return_cited_ad_package"
    assert summary["replay_checkpoint_backend"] == "sqlite"
    assert summary["replay_checkpoint_count"] >= 1
    assert summary["replay_node_sequence"] == summary["node_sequence"]
    assert summary["replay_raw_inputs_committed"] is False
    assert summary["raw_inputs_committed"] is False

    serialized = json.dumps(summary, ensure_ascii=False)
    for raw_value in ["비공개 말차 푸딩", "VIP 고객"]:
        assert raw_value not in serialized


def test_agentic_rag_websocket_smoke_writes_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "agentic-rag-websocket-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/agentic_rag_websocket_smoke.py",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["agentic_rag_websocket_smoke"] == "passed"
    assert summary["scope"] == "local_fastapi_websocket_no_paid_api_call"
    assert summary["stream_protocol"] == "websocket"
    assert summary["run_id_prefix"] == "agr"
    assert summary["checkpointing_enabled"] is True
    assert summary["event_names"] == [
        "run_started",
        "node_completed",
        "node_completed",
        "node_completed",
        "node_completed",
        "node_completed",
        "node_completed",
        "node_completed",
        "run_completed",
    ]
    assert summary["node_sequence"] == [
        "plan_campaign",
        "run_tool_suite",
        "retrieve_context",
        "build_citations",
        "guardrail_check",
        "execute_worker",
        "finalize",
    ]
    assert summary["final_status"] == "completed"
    assert summary["final_next_action"] == "return_cited_ad_package"
    assert summary["raw_inputs_committed"] is False

    serialized = json.dumps(summary, ensure_ascii=False)
    for raw_value in ["비공개 말차 푸딩", "VIP 고객"]:
        assert raw_value not in serialized
