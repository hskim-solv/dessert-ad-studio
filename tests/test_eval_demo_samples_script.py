import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_eval_demo_samples_script_writes_workflow_eval_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "workflow-eval-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/eval_demo_samples.py",
            "--output",
            str(output_path),
            "--output-dir",
            str(tmp_path / "outputs"),
            "--log-path",
            str(tmp_path / "eval-generations.jsonl"),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["sample_count"] == 3
    assert summary["passed"] is True
    assert summary["failure_count"] == 0
    assert summary["failure_cases"] == []
    assert all("workflow.required_steps" in _check_names(result) for result in summary["results"])


def _check_names(result: dict) -> set[str]:
    return {check["name"] for check in result["checks"]}
