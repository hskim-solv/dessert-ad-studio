from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from PIL import Image, ImageFilter, ImageStat


DEFAULT_OUTPUT_PATH = Path("docs/evidence/visual-quality-summary.json")
DEMO_GALLERY_MANIFEST = Path("docs/evidence/demo-gallery-manifest.json")
REAL_SAMPLE_RESULTS = Path("docs/evidence/real-sample-preservation-results.json")
DEFAULT_THRESHOLDS = {
    "min_width": 768,
    "min_height": 768,
    "min_luminance_stddev": 35.0,
    "min_edge_density": 0.015,
    "min_unique_colors_128": 128,
    "min_bottom_region_luminance_range": 150,
}


def default_image_inputs() -> list[dict[str, str]]:
    inputs: list[dict[str, str]] = []
    demo_manifest = json.loads(DEMO_GALLERY_MANIFEST.read_text(encoding="utf-8"))
    for item in demo_manifest["items"]:
        inputs.append(
            {
                "source": "demo_gallery",
                "label": item["sample_label"],
                "path": item["banner_path"],
            }
        )

    real_sample_results = json.loads(REAL_SAMPLE_RESULTS.read_text(encoding="utf-8"))
    for item in real_sample_results["items"]:
        inputs.append(
            {
                "source": "real_sample_preservation",
                "label": item["label"],
                "path": item["banner_path"],
            }
        )
    return inputs


def evaluate_visual_quality(
    image_inputs: list[dict[str, str]],
    *,
    thresholds: dict[str, float],
) -> dict[str, Any]:
    items = [_evaluate_image(item, thresholds=thresholds) for item in image_inputs]
    passed_count = sum(1 for item in items if item["passed"])
    sample_count = len(items)
    pass_rate = round(passed_count / sample_count, 6) if sample_count else 0.0
    return {
        "visual_quality_eval": "passed"
        if sample_count and passed_count == sample_count
        else "failed",
        "scope": "committed_banner_asset_proxy_gate",
        "sample_count": sample_count,
        "passed_count": passed_count,
        "pass_rate": pass_rate,
        "thresholds": thresholds,
        "items": items,
    }


def _evaluate_image(
    item: dict[str, str],
    *,
    thresholds: dict[str, float],
) -> dict[str, Any]:
    path = Path(item["path"])
    with Image.open(path) as opened:
        image = opened.convert("RGB")
    width, height = image.size
    grayscale = image.convert("L")
    luminance = ImageStat.Stat(grayscale)
    edges = grayscale.filter(ImageFilter.FIND_EDGES)
    edge_histogram = edges.histogram()
    edge_pixels = sum(count for value, count in enumerate(edge_histogram) if value > 24)
    total_pixels = width * height
    unique_colors = _downsampled_unique_colors(image)
    bottom_range = _bottom_region_luminance_range(grayscale)

    metrics = {
        "width": width,
        "height": height,
        "luminance_stddev": round(luminance.stddev[0], 6),
        "edge_density": round(edge_pixels / total_pixels, 6),
        "unique_colors_128": unique_colors,
        "bottom_region_luminance_range": bottom_range,
    }
    checks = {
        "min_width": width >= thresholds["min_width"],
        "min_height": height >= thresholds["min_height"],
        "square_or_portrait_safe": width == height,
        "luminance_stddev": metrics["luminance_stddev"] >= thresholds["min_luminance_stddev"],
        "edge_density": metrics["edge_density"] >= thresholds["min_edge_density"],
        "unique_colors_128": unique_colors >= thresholds["min_unique_colors_128"],
        "bottom_region_luminance_range": bottom_range
        >= thresholds["min_bottom_region_luminance_range"],
    }
    return {
        "source": item["source"],
        "label": item["label"],
        "path": str(path),
        "passed": all(checks.values()),
        "metrics": metrics,
        "checks": checks,
    }


def _downsampled_unique_colors(image: Image.Image) -> int:
    colors = image.resize((128, 128)).getcolors(maxcolors=16_384)
    return len(colors) if colors is not None else 16_384


def _bottom_region_luminance_range(grayscale: Image.Image) -> int:
    top = int(grayscale.height * 0.65)
    bottom = grayscale.crop((0, top, grayscale.width, grayscale.height))
    histogram = bottom.histogram()
    min_value = next(value for value, count in enumerate(histogram) if count)
    max_value = next(255 - value for value, count in enumerate(reversed(histogram)) if count)
    return max_value - min_value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate committed banner assets with an offline visual quality proxy gate.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--image-path",
        action="append",
        type=Path,
        help="Evaluate a specific image path. May be passed more than once.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    if args.image_path:
        image_inputs = [
            {
                "source": "manual_image",
                "label": path.stem,
                "path": str(path),
            }
            for path in args.image_path
        ]
    else:
        image_inputs = default_image_inputs()

    summary = evaluate_visual_quality(image_inputs, thresholds=dict(DEFAULT_THRESHOLDS))
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    print(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    return 0 if summary["visual_quality_eval"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
