import json
from pathlib import Path

from dessert_ad_studio.demo_samples import DEMO_SAMPLES
from scripts.build_demo_gallery import build_demo_gallery


def test_build_demo_gallery_writes_assets_manifest_and_markdown(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "docs" / "evidence"
    summary = build_demo_gallery(
        repo_root=tmp_path,
        asset_dir=evidence_dir / "assets" / "demo-gallery",
        generated_dir=tmp_path / "outputs" / "demo-gallery",
        log_path=tmp_path / "logs" / "demo-gallery-generations.jsonl",
        manifest_path=evidence_dir / "demo-gallery-manifest.json",
        markdown_path=evidence_dir / "demo-gallery.md",
        evidence_date="2026-06-16",
    )

    assert summary["demo_gallery"] == "passed"
    assert summary["sample_count"] == len(DEMO_SAMPLES)
    assert summary["banner_count"] == len(DEMO_SAMPLES)
    assert summary["evidence_date"] == "2026-06-16"

    manifest = json.loads((evidence_dir / "demo-gallery-manifest.json").read_text())
    assert manifest == summary
    markdown = (evidence_dir / "demo-gallery.md").read_text(encoding="utf-8")
    assert "# Demo Gallery Evidence" in markdown

    for item in summary["items"]:
        banner_path = tmp_path / item["banner_path"]
        assert banner_path.exists()
        assert banner_path.suffix == ".png"
        assert item["workflow_steps"] == [
            "rank_templates",
            "decode_reference",
            "analyze_product",
            "retrieve_marketing_context",
            "build_image_prompt",
            "generate_copy",
            "generate_image",
            "write_log",
        ]
        assert item["gallery_copy_strategy"] == "product_name_headline"
        assert item["gallery_source_strategy"] == "mock_debug_text_removed"
        assert item["gallery_body"] == "제품 사진은 보존하고, 한국어 문구는 오버레이로 렌더링"
        assert item["gallery_cta"] == "방문하기"
        assert item["markdown_image_path"] in markdown
