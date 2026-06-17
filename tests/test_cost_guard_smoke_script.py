from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_cost_guard_smoke_writes_passing_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "cost-guard-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/cost_guard_smoke.py",
            "--model-id",
            "gpt-image-2",
            "--image-total-tokens",
            "627",
            "--max-estimated-cost-usd",
            "0.02",
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

    assert summary["cost_guard_smoke"] == "passed"
    assert summary["scope"] == "offline_cost_estimate_no_api_call"
    assert summary["model_id"] == "gpt-image-2"
    assert summary["usage"] == {"total_tokens": 627}
    assert summary["cost"]["total_usd"] == 0.01881
    assert summary["cost_guard"]["passed"] is True


def test_cost_guard_smoke_fails_when_budget_is_exceeded(tmp_path: Path) -> None:
    output_path = tmp_path / "cost-guard-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/cost_guard_smoke.py",
            "--model-id",
            "gpt-image-2",
            "--image-total-tokens",
            "627",
            "--max-estimated-cost-usd",
            "0.01",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 1
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["cost_guard_smoke"] == "failed"
    assert summary["cost_guard"]["passed"] is False
