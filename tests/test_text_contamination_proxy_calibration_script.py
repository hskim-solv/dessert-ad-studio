from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_text_contamination_proxy_calibration_writes_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "text-contamination-proxy-calibration-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/text_contamination_proxy_calibration_smoke.py",
            "--date",
            "2026-06-17",
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

    assert summary["text_contamination_proxy_calibration"] == "passed"
    assert summary["scope"] == "offline_synthetic_no_paid_api_call"
    assert summary["threshold"] == 0.45
    assert summary["cases"] == [
        {
            "name": "dark_sprinkle_texture_no_visible_text",
            "expected": "pass",
            "passed": True,
            "max_score": 0.45,
            "score": 0.0,
        },
        {
            "name": "dense_rendered_text",
            "expected": "fail",
            "passed": True,
            "min_score_exclusive": 0.45,
            "score": 1.0,
        },
    ]
    assert summary["paid_api_call_count"] == 0
    assert summary["raw_images_committed"] is False
