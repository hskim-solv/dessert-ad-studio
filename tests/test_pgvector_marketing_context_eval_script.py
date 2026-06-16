import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_eval_pgvector_marketing_context_script_writes_offline_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "pgvector-baseline-results.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/eval_pgvector_marketing_context.py",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["sample_count"] >= 10
    assert summary["average_category_hit_rate"] >= 0.8
    assert summary["average_category_precision"] >= 0.9
    assert summary["required_category_hit_rate"] == 1.0
    assert summary["passed"] is True
