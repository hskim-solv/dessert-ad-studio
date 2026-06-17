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
    assert summary["scope"] == "offline_langgraph_control_plane_no_api_call"
    assert summary["graph"]["status"] == "needs_approval"
    assert summary["graph"]["next_action"] == "wait_for_human_approval"
    assert summary["graph"]["node_trace"] == [
        "plan_campaign",
        "retrieve_context",
        "build_citations",
        "guardrail_check",
        "human_approval",
    ]
    assert summary["graph"]["checkpoint_count"] >= 1
    assert summary["graph"]["citation_count"] >= 1
    assert summary["graph"]["approval_required"] is True

    serialized = json.dumps(summary, ensure_ascii=False)
    for raw_value in [
        "비공개 말차 푸딩",
        "VIP 고객에게만 보일 문구",
        "secret-reference.png",
        "c2VjcmV0LWltYWdlLWJ5dGVz",
    ]:
        assert raw_value not in serialized
