from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_agentic_rag_graph_smoke_writes_redacted_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "agentic-rag-graph-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/agentic_rag_graph_smoke.py",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["agentic_rag_graph_smoke"] == "passed"
    assert summary["scope"] == "offline_langgraph_control_plane_no_paid_api_call"
    assert summary["approval_route"]["status"] == "needs_approval"
    assert summary["approval_route"]["next_action"] == "wait_for_human_approval"
    assert summary["approval_route"]["node_trace"] == [
        "plan_campaign",
        "retrieve_context",
        "build_citations",
        "guardrail_check",
        "human_approval",
    ]
    assert summary["approval_route"]["checkpoint_count"] >= 1
    assert summary["approval_route"]["citation_count"] >= 1
    assert summary["approval_route"]["approval_required"] is True
    assert summary["worker_route"]["status"] == "completed"
    assert summary["worker_route"]["next_action"] == "return_cited_ad_package"
    assert summary["worker_route"]["worker_status"] == "succeeded"
    assert summary["worker_route"]["copy_option_count"] == 3
    assert summary["worker_route"]["node_trace"] == [
        "plan_campaign",
        "retrieve_context",
        "build_citations",
        "guardrail_check",
        "execute_worker",
        "finalize",
    ]

    serialized = json.dumps(summary, ensure_ascii=False)
    for raw_value in [
        "비공개 말차 푸딩",
        "VIP 고객에게만 보일 문구",
        "비공개 딸기 크림 크루아상",
        "VIP 촬영본",
        "secret-reference.png",
        "c2VjcmV0LWltYWdlLWJ5dGVz",
    ]:
        assert raw_value not in serialized


def test_agentic_rag_sqlite_checkpoint_smoke_writes_redacted_summary(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "agentic-rag-sqlite-checkpoint-summary.json"
    checkpoint_path = tmp_path / "agentic-rag-checkpoints.sqlite"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/agentic_rag_sqlite_checkpoint_smoke.py",
            "--output",
            str(output_path),
            "--checkpoint-db",
            str(checkpoint_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["agentic_rag_sqlite_checkpoint_smoke"] == "passed"
    assert summary["scope"] == "local_sqlite_langgraph_checkpointer_no_paid_api_call"
    assert summary["checkpoint_backend"] == "sqlite"
    assert summary["checkpoint_path_committed"] is False
    assert summary["checkpoint_file_created"] is True
    assert summary["checkpoint_count"] >= 1
    assert summary["reopened_checkpoint_count"] == summary["checkpoint_count"]
    assert summary["raw_inputs_found_in_checkpoint"] is False
    assert summary["final_status"] == "completed"
    assert summary["next_action"] == "return_cited_ad_package"

    serialized = json.dumps(summary, ensure_ascii=False)
    checkpoint_bytes = checkpoint_path.read_bytes()
    for raw_value in [
        "비공개 말차 푸딩",
        "VIP 고객에게만 보일 문구",
        "비공개 할인 강조",
        "secret-reference.png",
        "c2VjcmV0LWltYWdlLWJ5dGVz",
    ]:
        assert raw_value not in serialized
        assert raw_value.encode("utf-8") not in checkpoint_bytes
