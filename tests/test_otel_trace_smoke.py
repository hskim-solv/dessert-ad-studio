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


def test_otel_trace_smoke_fails_for_unreachable_otlp_endpoint(tmp_path) -> None:
    env = {
        **os.environ,
        "WORKFLOW_TRACING": "otel",
        "WORKFLOW_TRACE_EXPORT": "otlp",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://127.0.0.1:9/v1/traces",
        "OUTPUT_DIR": str(tmp_path / "outputs"),
        "GENERATION_LOG_PATH": str(tmp_path / "generations.jsonl"),
    }

    result = subprocess.run(
        [sys.executable, "scripts/otel_trace_smoke.py"],
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )

    assert result.returncode != 0
    assert "trace_smoke=failed" in result.stdout
    assert "export=otlp" in result.stdout
