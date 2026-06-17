import json
from pathlib import Path
import subprocess
import sys

from dessert_ad_studio.demo_samples import PRODUCT_LIKE_EVAL_SAMPLES


ROOT = Path(__file__).resolve().parents[1]


def test_product_like_eval_pack_has_at_least_30_scenarios() -> None:
    assert len(PRODUCT_LIKE_EVAL_SAMPLES) >= 30


def test_eval_product_like_samples_script_writes_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "product-like-workflow-eval-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/eval_product_like_samples.py",
            "--limit",
            "5",
            "--output",
            str(output_path),
            "--output-dir",
            str(tmp_path / "outputs"),
            "--log-path",
            str(tmp_path / "eval-product-like-generations.jsonl"),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["sample_count"] == 5
    assert summary["total_available"] >= 30
    assert summary["scenario_pack"] == "product_like_v1"
    assert summary["passed"] is True
    assert summary["failure_count"] == 0
    assert summary["failure_cases"] == []
