from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path

from PIL import Image

from dessert_ad_studio.banner_overlay import BannerCopy
from scripts.build_real_sample_preservation_evidence import (
    RealSampleSource,
    build_real_sample_preservation_evidence,
)


def test_build_real_sample_preservation_evidence_writes_assets_and_summary(
    tmp_path: Path,
) -> None:
    source = RealSampleSource(
        slug="local-sample",
        label="Local sample",
        product_name="테스트 케이크",
        platform="인스타그램 피드",
        price_text="테스트가",
        source_page="https://example.com/source",
        image_url="https://example.com/source.png",
        license_name="CC0",
        license_url="https://example.com/license",
        attribution="Example",
        copy=BannerCopy(
            headline="테스트 케이크",
            body="제품 사진은 유지하고 문구만 렌더링",
            call_to_action="확인하기",
        ),
    )

    summary = build_real_sample_preservation_evidence(
        repo_root=tmp_path,
        asset_dir=tmp_path / "docs" / "evidence" / "assets" / "real-samples",
        manifest_path=tmp_path / "docs" / "evidence" / "real-samples.json",
        markdown_path=tmp_path / "docs" / "evidence" / "real-samples.md",
        evidence_date="2026-06-16",
        sources=[source],
        image_fetcher=lambda _url: _sample_image_bytes(),
    )

    assert summary["real_sample_preservation"] == "passed"
    assert summary["sample_count"] == 1
    assert summary["passed_count"] == 1
    assert summary["min_top_region_pixel_match_ratio"] >= 0.99

    item = summary["items"][0]
    assert item["checklist_passed"] is True
    assert (tmp_path / item["reference_path"]).exists()
    assert (tmp_path / item["banner_path"]).exists()

    manifest = json.loads(
        (tmp_path / "docs" / "evidence" / "real-samples.json").read_text(encoding="utf-8")
    )
    assert manifest == summary
    markdown = (tmp_path / "docs" / "evidence" / "real-samples.md").read_text(encoding="utf-8")
    assert "Real-Sample Product Preservation Evidence" in markdown
    assert "테스트 케이크" in markdown


def _sample_image_bytes() -> bytes:
    image = Image.new("RGB", (640, 480), color=(240, 230, 210))
    for x in range(180, 460):
        for y in range(110, 330):
            image.putpixel((x, y), (210, 90, 120))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
