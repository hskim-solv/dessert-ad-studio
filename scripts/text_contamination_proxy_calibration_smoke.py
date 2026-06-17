from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from typing import Any

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.openai_image_edit_preservation_smoke import (  # noqa: E402
    DEFAULT_GATE_THRESHOLDS,
    _text_contamination_risk_score,
)


DEFAULT_OUTPUT_PATH = Path("docs/evidence/text-contamination-proxy-calibration-summary.json")


def build_text_contamination_proxy_calibration_summary(
    *,
    evidence_date: str,
) -> dict[str, Any]:
    threshold = DEFAULT_GATE_THRESHOLDS["max_text_contamination_risk_score"]
    no_text_score = round(_text_contamination_risk_score(_dark_sprinkle_texture()), 6)
    text_score = round(_text_contamination_risk_score(_dense_rendered_text()), 6)
    cases: list[dict[str, Any]] = [
        {
            "name": "dark_sprinkle_texture_no_visible_text",
            "expected": "pass",
            "passed": no_text_score <= threshold,
            "max_score": threshold,
            "score": no_text_score,
        },
        {
            "name": "dense_rendered_text",
            "expected": "fail",
            "passed": text_score > threshold,
            "min_score_exclusive": threshold,
            "score": text_score,
        },
    ]
    passed = all(case["passed"] for case in cases)
    return {
        "text_contamination_proxy_calibration": "passed" if passed else "failed",
        "scope": "offline_synthetic_no_paid_api_call",
        "evidence_date": evidence_date,
        "threshold": threshold,
        "cases": cases,
        "paid_api_call_count": 0,
        "raw_images_committed": False,
    }


def _dark_sprinkle_texture() -> Image.Image:
    image = Image.new("RGB", (1024, 1024), color=(238, 232, 220))
    draw = ImageDraw.Draw(image)
    for y in range(80, 940, 45):
        for x in range(80, 940, 45):
            draw.rectangle((x, y, x + 3, y + 3), fill=(35, 30, 25))
    return image


def _dense_rendered_text() -> Image.Image:
    image = Image.new("RGB", (1024, 1024), color=(245, 245, 245))
    draw = ImageDraw.Draw(image)
    for y in range(80, 460, 48):
        draw.text((80, y), "MATCHA PUDDING SALE EVENT", fill=(10, 10, 10))
    return image


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build offline evidence for the text-contamination proxy calibration.",
        allow_abbrev=False,
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    summary = build_text_contamination_proxy_calibration_summary(evidence_date=args.date)
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    print(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    return 0 if summary["text_contamination_proxy_calibration"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
