from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]


def test_eval_visual_quality_script_passes_committed_banner_assets(tmp_path: Path) -> None:
    output_path = tmp_path / "visual-quality-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/eval_visual_quality.py",
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

    assert summary["visual_quality_eval"] == "passed"
    assert summary["sample_count"] == 6
    assert summary["passed_count"] == 6
    assert summary["pass_rate"] == 1.0
    assert {item["source"] for item in summary["items"]} == {
        "demo_gallery",
        "real_sample_preservation",
    }


def test_eval_visual_quality_script_fails_blank_image(tmp_path: Path) -> None:
    image_path = tmp_path / "blank.png"
    Image.new("RGB", (768, 768), color=(240, 240, 240)).save(image_path)
    output_path = tmp_path / "visual-quality-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/eval_visual_quality.py",
            "--image-path",
            str(image_path),
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
    assert summary["visual_quality_eval"] == "failed"
    assert summary["items"][0]["checks"]["luminance_stddev"] is False
    assert summary["items"][0]["checks"]["edge_density"] is False


def test_eval_visual_quality_script_passes_structured_image(tmp_path: Path) -> None:
    image_path = tmp_path / "structured.png"
    image = Image.new("RGB", (768, 768), color=(235, 225, 200))
    draw = ImageDraw.Draw(image)
    for index in range(0, 768, 24):
        color = (30 + index % 180, 80 + index % 120, 150)
        draw.rectangle((index, 0, min(index + 12, 767), 767), fill=color)
    draw.rectangle((0, 520, 768, 768), fill=(30, 30, 30))
    draw.rectangle((80, 590, 690, 650), fill=(245, 245, 245))
    image.save(image_path)
    output_path = tmp_path / "visual-quality-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/eval_visual_quality.py",
            "--image-path",
            str(image_path),
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
    assert summary["visual_quality_eval"] == "passed"
    assert summary["items"][0]["checks"]["bottom_region_luminance_range"] is True
