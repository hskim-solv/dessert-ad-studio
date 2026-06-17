from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path

from PIL import Image, ImageDraw

from dessert_ad_studio.backends.base import ImageResult
from scripts.openai_image_edit_preservation_smoke import (
    build_live_image_edit_preservation_summary,
)


def test_build_live_image_edit_preservation_summary_redacts_prompt_and_output(
    tmp_path: Path,
) -> None:
    reference_path = tmp_path / "reference.png"
    _write_reference(reference_path)
    output_dir = tmp_path / "outputs"
    summary_path = tmp_path / "summary.json"

    summary = build_live_image_edit_preservation_summary(
        reference_path=reference_path,
        output_dir=output_dir,
        summary_path=summary_path,
        evidence_date="2026-06-17",
        model_id="gpt-image-test",
        quality="low",
        image_generator=_fake_image_generator,
    )

    assert summary["openai_image_edit_preservation"] == "passed"
    assert summary["evidence_date"] == "2026-06-17"
    assert summary["model_id"] == "gpt-image-test"
    assert summary["quality"] == "low"
    assert summary["used_reference"] is True
    assert summary["generated_image"]["exists"] is True
    assert summary["generated_image"]["committed"] is False
    assert summary["generated_image"]["path"] == "redacted_outputs_path"
    assert summary["generated_image"]["sha256"]
    assert summary["reference_image"]["sha256"]
    assert summary["prompt"]["length"] > 0
    assert summary["prompt"]["sha256"]
    assert summary["metrics"]["generated_nonblank"] is True
    assert summary["metrics"]["color_histogram_similarity"] >= 0.9

    persisted = json.loads(summary_path.read_text(encoding="utf-8"))
    serialized = json.dumps(persisted, ensure_ascii=False)
    assert persisted == summary
    assert "원본 사진의 상품 형태" not in serialized
    assert str(output_dir) not in serialized
    assert "reference_image_b64" not in serialized
    assert "b64_json" not in serialized


def _write_reference(path: Path) -> None:
    image = Image.new("RGB", (256, 256), color=(240, 230, 210))
    draw = ImageDraw.Draw(image)
    draw.ellipse((70, 45, 190, 170), fill=(210, 90, 120))
    draw.rectangle((40, 180, 220, 230), fill=(80, 60, 50))
    image.save(path)


def _fake_image_generator(*, reference_bytes: bytes, output_dir: Path, prompt: str) -> ImageResult:
    assert reference_bytes
    assert "원본 사진의 상품 형태" in prompt
    output_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(reference_bytes)) as source:
        image = source.convert("RGB").resize((1024, 1024))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, image.height - 40, image.width, image.height), fill=(35, 35, 35))
    output_path = output_dir / "generated.png"
    image.save(output_path)
    return ImageResult(path=str(output_path), usage={"total_tokens": 123})
