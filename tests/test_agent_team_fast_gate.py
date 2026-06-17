from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_agent_team_fast_gate_lists_parallel_safe_lanes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/agent_team_fast_gate.py", "--list"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(completed.stdout)
    assert "agentic-rag" in payload["lanes"]
    assert "docs" in payload["lanes"]
    assert "paid-provider" not in payload["parallel_safe_lanes"]


def test_agent_team_fast_gate_dry_run_returns_commands_without_running() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/agent_team_fast_gate.py",
            "--lane",
            "agentic-rag",
            "--dry-run",
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["lane"] == "agentic-rag"
    assert payload["parallel_safe"] is True
    assert payload["paid_api"] is False
    assert payload["commands"]
    assert any("tests/test_agentic_rag.py" in command for command in payload["commands"])
    assert any("agentic_rag_websocket_smoke.py" in command for command in payload["commands"])
    assert any("agentic_rag_trace_smoke.py" in command for command in payload["commands"])
    assert payload["executed"] is False


def test_agent_team_fast_gate_rejects_paid_provider_without_execute() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/agent_team_fast_gate.py",
            "--lane",
            "paid-provider",
            "--dry-run",
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["lane"] == "paid-provider"
    assert payload["parallel_safe"] is False
    assert payload["paid_api"] is True
    assert payload["executed"] is False
