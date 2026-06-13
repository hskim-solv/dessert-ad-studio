from __future__ import annotations

import os
import subprocess
import sys


def test_otel_trace_smoke_runs_with_console_export(tmp_path) -> None:
    env = {
        **os.environ,
        "WORKFLOW_TRACING": "otel",
        "WORKFLOW_TRACE_EXPORT": "console",
        "OUTPUT_DIR": str(tmp_path / "outputs"),
        "GENERATION_LOG_PATH": str(tmp_path / "generations.jsonl"),
    }

    result = subprocess.run(
        [sys.executable, "scripts/otel_trace_smoke.py"],
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0
    stdout_lines = result.stdout.strip().splitlines()
    assert len(stdout_lines) == 1
    assert "trace_smoke=passed" in stdout_lines[0]
    assert "export=console" in stdout_lines[0]
