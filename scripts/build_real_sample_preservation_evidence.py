from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.request import Request, urlopen

from PIL import Image, ImageChops, ImageOps

from dessert_ad_studio.banner_overlay import BannerCopy, create_banner_overlay

REFERENCE_IMAGE_SIZE = (768, 768)


@dataclass(frozen=True)
class RealSampleSource:
    slug: str
    label: str
    product_name: str
    platform: str
    price_text: str
    source_page: str
    image_url: str
    license_name: str
    license_url: str
    attribution: str
    copy: BannerCopy


REAL_SAMPLE_SOURCES = (
    RealSampleSource(
        slug="dessert-plate",
        label="Dessert plate",
        product_name="디저트 플레이트",
        platform="인스타그램 피드",
        price_text="오늘 한정 세트",
        source_page="https://commons.wikimedia.org/wiki/File:Dessert_(28307972126).jpg",
        image_url=(
            "https://upload.wikimedia.org/wikipedia/commons/c/ce/Dessert_%2828307972126%29.jpg"
        ),
        license_name="CC BY-SA 2.0",
        license_url="https://creativecommons.org/licenses/by-sa/2.0",
        attribution="Charles Haynes",
        copy=BannerCopy(
            headline="디저트 플레이트",
            body="실제 제품 사진을 유지하고, 행사는 오버레이로만 표현",
            call_to_action="오늘 예약하기",
        ),
    ),
    RealSampleSource(
        slug="matcha-pudding",
        label="Matcha pudding",
        product_name="말차 푸딩",
        platform="인스타그램 스토리",
        price_text="2개 세트",
        source_page=(
            "https://commons.wikimedia.org/wiki/"
            "File:Black_Sesame_pudding,_Matcha_Chantilly_Cream_(15229247433).jpg"
        ),
        image_url=(
            "https://upload.wikimedia.org/wikipedia/commons/3/3d/"
            "Black_Sesame_pudding%2C_Matcha_Chantilly_Cream_%2815229247433%29.jpg"
        ),
        license_name="CC BY 2.0",
        license_url="https://creativecommons.org/licenses/by/2.0",
        attribution="Arnold Gatilao",
        copy=BannerCopy(
            headline="말차 푸딩",
            body="제품 컵과 색감을 보존하고, 문구는 하단 패널에 렌더링",
            call_to_action="저장하기",
        ),
    ),
    RealSampleSource(
        slug="flower-box",
        label="Flower box",
        product_name="플라워 박스",
        platform="네이버 스마트스토어 썸네일",
        price_text="예약 주문",
        source_page="https://commons.wikimedia.org/wiki/File:Blue_flowers_box.jpg",
        image_url="https://upload.wikimedia.org/wikipedia/commons/3/3b/Blue_flowers_box.jpg",
        license_name="CC BY-SA 4.0",
        license_url="https://creativecommons.org/licenses/by-sa/4.0",
        attribution="Наталія Статива-Жарко",
        copy=BannerCopy(
            headline="플라워 박스",
            body="실물 사진의 색상과 형태를 유지한 선물용 썸네일",
            call_to_action="예약하기",
        ),
    ),
)

ImageFetcher = Callable[[str], bytes]


def build_real_sample_preservation_evidence(
    *,
    repo_root: Path,
    asset_dir: Path,
    manifest_path: Path,
    markdown_path: Path,
    evidence_date: str,
    sources: Sequence[RealSampleSource] = REAL_SAMPLE_SOURCES,
    image_fetcher: ImageFetcher | None = None,
) -> dict[str, Any]:
    references_dir = asset_dir / "references"
    banners_dir = asset_dir / "banners"
    references_dir.mkdir(parents=True, exist_ok=True)
    banners_dir.mkdir(parents=True, exist_ok=True)
    fetch = image_fetcher or _download_image

    items: list[dict[str, Any]] = []
    for source in sources:
        reference_path = references_dir / f"{source.slug}.png"
        banner_path = banners_dir / f"{source.slug}_banner.png"

        image_bytes = fetch(source.image_url)
        _write_reference_image(image_bytes, reference_path)
        generated_banner_path = create_banner_overlay(
            image_path=reference_path,
            copy=source.copy,
            price_text=source.price_text,
            output_dir=banners_dir,
        )
        if generated_banner_path != banner_path:
            banner_path.unlink(missing_ok=True)
            generated_banner_path.replace(banner_path)
        _optimize_png(banner_path)

        preservation = _measure_top_region_pixel_match(reference_path, banner_path)
        passed = preservation["top_region_pixel_match_ratio"] >= 0.99
        items.append(
            {
                "slug": source.slug,
                "label": source.label,
                "product_name": source.product_name,
                "platform": source.platform,
                "source_page": source.source_page,
                "image_url": source.image_url,
                "license_name": source.license_name,
                "license_url": source.license_url,
                "attribution": source.attribution,
                "reference_path": _relative_path(reference_path, repo_root),
                "banner_path": _relative_path(banner_path, repo_root),
                "markdown_reference_path": _relative_path(
                    reference_path,
                    markdown_path.parent,
                ),
                "markdown_banner_path": _relative_path(banner_path, markdown_path.parent),
                "preservation_metric": preservation,
                "checklist_passed": passed,
            }
        )

    passed_count = sum(1 for item in items if item["checklist_passed"])
    ratios = [item["preservation_metric"]["top_region_pixel_match_ratio"] for item in items]
    summary = {
        "real_sample_preservation": "passed" if passed_count == len(items) else "failed",
        "evidence_date": evidence_date,
        "sample_count": len(items),
        "passed_count": passed_count,
        "pass_rate": passed_count / len(items) if items else 0.0,
        "min_top_region_pixel_match_ratio": min(ratios) if ratios else 0.0,
        "metric_definition": (
            "Pixel match ratio between the normalized public reference image and "
            "the generated banner in the top 55 percent of the image, which the "
            "deterministic overlay does not cover."
        ),
        "items": items,
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(_render_markdown(summary), encoding="utf-8")
    return summary


def _download_image(url: str) -> bytes:
    curl_result = subprocess.run(
        [
            "curl",
            "-fsSL",
            "-A",
            "dessert-ad-studio-evidence/1.0 (portfolio evidence)",
            url,
        ],
        check=False,
        capture_output=True,
    )
    if curl_result.returncode == 0:
        return curl_result.stdout

    request = Request(url, headers={"User-Agent": "dessert-ad-studio-evidence/1.0"})
    with urlopen(request, timeout=30) as response:
        return response.read()


def _write_reference_image(image_bytes: bytes, destination: Path) -> None:
    with Image.open(BytesIO(image_bytes)) as source:
        image = ImageOps.fit(
            source.convert("RGB"),
            REFERENCE_IMAGE_SIZE,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
    image.save(destination, format="PNG", optimize=True)


def _optimize_png(path: Path) -> None:
    with Image.open(path) as source:
        image = source.copy()
    image.save(path, format="PNG", optimize=True)


def _measure_top_region_pixel_match(reference_path: Path, banner_path: Path) -> dict[str, Any]:
    with Image.open(reference_path) as reference_source:
        reference = reference_source.convert("RGB")
    with Image.open(banner_path) as banner_source:
        banner = banner_source.convert("RGB")

    if reference.size != banner.size:
        return {
            "reference_size": list(reference.size),
            "banner_size": list(banner.size),
            "top_region_ratio": 0.55,
            "top_region_pixel_match_ratio": 0.0,
            "matched_pixels": 0,
            "total_pixels": 0,
        }

    width, height = reference.size
    top_height = max(1, int(height * 0.55))
    reference_region = reference.crop((0, 0, width, top_height))
    banner_region = banner.crop((0, 0, width, top_height))
    diff = ImageChops.difference(reference_region, banner_region)
    diff_mask = diff.convert("L").point(lambda value: 255 if value else 0)
    total_pixels = width * top_height
    diff_pixels = total_pixels - diff_mask.histogram()[0]
    matched_pixels = total_pixels - diff_pixels
    return {
        "reference_size": [width, height],
        "banner_size": [width, height],
        "top_region_ratio": 0.55,
        "top_region_pixel_match_ratio": round(matched_pixels / total_pixels, 6),
        "matched_pixels": matched_pixels,
        "total_pixels": total_pixels,
    }


def _render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Real-Sample Product Preservation Evidence",
        "",
        f"Date: {summary['evidence_date']}",
        "",
        "This evidence uses public Wikimedia Commons images as real product-photo",
        "stand-ins. The deterministic preservation path keeps the normalized",
        "reference image as the banner base and renders Korean copy as an overlay.",
        "",
        "## Summary",
        "",
        f"- Sample count: `{summary['sample_count']}`",
        f"- Passed: `{summary['passed_count']}`",
        f"- Pass rate: `{summary['pass_rate']:.2f}`",
        "- Metric: top 55% pixel match between reference and banner must be `>= 0.99`.",
        f"- Minimum observed match ratio: `{summary['min_top_region_pixel_match_ratio']:.6f}`",
        "",
        "## Samples",
        "",
        "| Sample | License | Reference | Banner | Match ratio |",
        "|---|---|---|---|---|",
    ]
    for item in summary["items"]:
        metric = item["preservation_metric"]["top_region_pixel_match_ratio"]
        license_link = f"[{item['license_name']}]({item['license_url']})"
        source_link = f"[source]({item['source_page']})"
        lines.append(
            "| "
            f"{item['label']} / `{item['product_name']}`<br>{source_link}<br>"
            f"Attribution: {item['attribution']} | "
            f"{license_link} | "
            f"![{item['label']} reference]({item['markdown_reference_path']}) | "
            f"![{item['label']} banner]({item['markdown_banner_path']}) | "
            f"`{metric:.6f}` |"
        )

    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            "```bash",
            ".venv/bin/python scripts/build_real_sample_preservation_evidence.py --date 2026-06-16",
            "```",
            "",
            "The command downloads public sample images from the source URLs listed",
            "in the manifest, normalizes them to 1024x1024, generates overlay",
            "banners, and writes the redaction-safe metric summary.",
            "",
            "## Boundary",
            "",
            "- These are public sample images, not customer uploads.",
            "- Raw model prompts, live provider responses, secrets, and customer data",
            "  are not stored.",
            "- This proves the deterministic local composition path. It does not claim",
            "  final OpenAI/FLUX image-edit preservation quality.",
            "",
        ]
    )
    return "\n".join(lines)


def _relative_path(path: Path, start: Path) -> str:
    return Path(path.resolve()).relative_to(start.resolve()).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build real-sample product-preservation evidence assets.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--asset-dir",
        type=Path,
        default=Path("docs/evidence/assets/real-sample-preservation"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("docs/evidence/real-sample-preservation-results.json"),
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=Path("docs/evidence/real-sample-preservation.md"),
    )
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args()

    summary = build_real_sample_preservation_evidence(
        repo_root=Path("."),
        asset_dir=args.asset_dir,
        manifest_path=args.manifest,
        markdown_path=args.markdown,
        evidence_date=args.date,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["real_sample_preservation"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
