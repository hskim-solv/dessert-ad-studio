from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
import sys
from typing import Any

from PIL import Image, ImageDraw

from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.banner_overlay import BannerCopy, create_banner_overlay
from dessert_ad_studio.demo_samples import DEMO_SAMPLES, DemoSample
from dessert_ad_studio.product_analysis import MockProductAnalyzer
from dessert_ad_studio.schemas import GenerationRequest
from dessert_ad_studio.triton import LocalTemplateScorer
from dessert_ad_studio.workflow import GenerationWorkflowDependencies, run_generation_workflow

GALLERY_BODY = "제품 사진은 보존하고, 한국어 문구는 오버레이로 렌더링"
GALLERY_CTA = "방문하기"


def request_from_sample(sample: DemoSample) -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose=sample.campaign_purpose,
        product_name=sample.product_name,
        tone=sample.tone,
        template_hint=sample.template_hint,
        price_text=sample.price_text,
        user_constraints=sample.user_constraints,
    )


def build_demo_gallery(
    *,
    repo_root: Path,
    asset_dir: Path,
    generated_dir: Path,
    log_path: Path,
    manifest_path: Path,
    markdown_path: Path,
    evidence_date: str,
) -> dict[str, Any]:
    asset_dir.mkdir(parents=True, exist_ok=True)
    generated_dir.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []
    for index, sample in enumerate(DEMO_SAMPLES, start=1):
        backend = MockAdBackend(output_dir=generated_dir)
        request = request_from_sample(sample)
        output = run_generation_workflow(
            request,
            GenerationWorkflowDependencies(
                template_scorer=LocalTemplateScorer(),
                copy_backend=backend,
                image_backend=backend,
                product_analyzer=MockProductAnalyzer(),
                log_path=log_path,
            ),
        )
        gallery_copy = _gallery_banner_copy(request, output.response.copy_options)
        gallery_source_path = _prepare_gallery_source_image(
            source_path=Path(output.response.image_path),
            destination=generated_dir / f"demo-{index:02d}-source.png",
        )
        overlay_path = create_banner_overlay(
            image_path=gallery_source_path,
            copy=gallery_copy,
            price_text=request.price_text,
            output_dir=asset_dir,
        )
        final_banner_path = asset_dir / f"demo-{index:02d}.png"
        if overlay_path != final_banner_path:
            final_banner_path.unlink(missing_ok=True)
            overlay_path.replace(final_banner_path)

        items.append(
            {
                "sample_label": sample.label,
                "business_type": sample.business_type,
                "platform": sample.platform,
                "product_name": sample.product_name,
                "campaign_purpose": sample.campaign_purpose,
                "tone": sample.tone,
                "template_hint": sample.template_hint,
                "copy_options_count": len(output.response.copy_options),
                "selected_template": output.response.selected_template.template_name,
                "image_backend": output.response.image_backend,
                "copy_backend": output.response.copy_backend,
                "gallery_copy_strategy": "product_name_headline",
                "gallery_source_strategy": "mock_debug_text_removed",
                "gallery_body": GALLERY_BODY,
                "gallery_cta": GALLERY_CTA,
                "workflow_steps": [entry.step for entry in output.trace],
                "banner_path": _relative_path(final_banner_path, repo_root),
                "markdown_image_path": _relative_path(final_banner_path, markdown_path.parent),
            }
        )

    summary = {
        "demo_gallery": "passed" if len(items) == len(DEMO_SAMPLES) else "failed",
        "evidence_date": evidence_date,
        "sample_count": len(DEMO_SAMPLES),
        "banner_count": len(items),
        "items": items,
    }
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(payload + "\n", encoding="utf-8")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(_render_gallery_markdown(summary), encoding="utf-8")
    return summary


def _prepare_gallery_source_image(source_path: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as source:
        image = source.convert("RGBA")
    draw = ImageDraw.Draw(image)
    background = image.getpixel((0, 0))
    width, height = image.size
    draw.rectangle((0, int(height * 0.78), width, height), fill=background)
    image.save(destination, format="PNG")
    return destination


def _gallery_banner_copy(request: GenerationRequest, _copy_options: list) -> BannerCopy:
    return BannerCopy(
        headline=request.product_name,
        body=GALLERY_BODY,
        call_to_action=GALLERY_CTA,
    )


def _render_gallery_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Demo Gallery Evidence",
        "",
        f"Date: {summary['evidence_date']}",
        "",
        "This gallery is generated from the deterministic mock workflow. It is",
        "portfolio evidence for result UX, Korean overlay rendering, and the",
        "representative small-business scenarios used by the local demo.",
        "",
        "## Summary",
        "",
        f"- Sample count: `{summary['sample_count']}`",
        f"- Banner count: `{summary['banner_count']}`",
        f"- Result: `{summary['demo_gallery']}`",
        "",
        "## Gallery",
        "",
        "| Scenario | Platform | Banner |",
        "|---|---|---|",
    ]
    for item in summary["items"]:
        lines.append(
            "| "
            f"{item['sample_label']} / `{item['product_name']}` | "
            f"{item['platform']} | "
            f"![{item['sample_label']}]({item['markdown_image_path']}) |"
        )
    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            "```bash",
            ".venv/bin/python scripts/build_demo_gallery.py",
            "```",
            "",
            "Generated banners are committed under",
            "`docs/evidence/assets/demo-gallery/`. The raw generated images and",
            "generation logs stay under `outputs/` and `logs/`, which are ignored.",
            "",
        ]
    )
    return "\n".join(lines)


def _relative_path(path: Path, start: Path) -> str:
    return Path(os.path.relpath(path.resolve(), start.resolve())).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic portfolio demo gallery assets.",
        allow_abbrev=False,
    )
    parser.add_argument("--asset-dir", type=Path, default=Path("docs/evidence/assets/demo-gallery"))
    parser.add_argument("--generated-dir", type=Path, default=Path("outputs/demo-gallery"))
    parser.add_argument(
        "--log-path", type=Path, default=Path("logs/demo-gallery-generations.jsonl")
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path("docs/evidence/demo-gallery-manifest.json")
    )
    parser.add_argument("--markdown", type=Path, default=Path("docs/evidence/demo-gallery.md"))
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args()

    summary = build_demo_gallery(
        repo_root=Path("."),
        asset_dir=args.asset_dir,
        generated_dir=args.generated_dir,
        log_path=args.log_path,
        manifest_path=args.manifest,
        markdown_path=args.markdown,
        evidence_date=args.date,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["demo_gallery"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
