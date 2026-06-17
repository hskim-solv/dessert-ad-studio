from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path

from PIL import Image, ImageDraw

from dessert_ad_studio.backends.base import ImageResult
from dessert_ad_studio.schemas import GenerationRequest
from scripts.openai_image_edit_preservation_smoke import (
    ReferenceSample,
    build_live_image_edit_preservation_summary,
    build_provider_quality_gate_summary,
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


def test_build_provider_quality_gate_summary_checks_multiple_samples_and_redacts_outputs(
    tmp_path: Path,
) -> None:
    first_reference = tmp_path / "first.png"
    second_reference = tmp_path / "second.png"
    _write_reference(first_reference)
    _write_reference(second_reference, background=(210, 232, 218), product=(95, 145, 100))

    output_dir = tmp_path / "outputs"
    summary_path = tmp_path / "provider-summary.json"
    samples = (
        ReferenceSample(
            slug="first",
            product_name="말차 푸딩",
            reference_path=first_reference,
            roi=(0.12, 0.08, 0.88, 0.78),
        ),
        ReferenceSample(
            slug="second",
            product_name="피스타치오 케이크",
            reference_path=second_reference,
            roi=(0.12, 0.08, 0.88, 0.78),
        ),
    )

    summary = build_provider_quality_gate_summary(
        samples=samples,
        output_dir=output_dir,
        summary_path=summary_path,
        evidence_date="2026-06-17",
        model_id="gpt-image-test",
        quality="medium",
        image_generator=_fake_image_generator,
    )

    assert summary["provider_quality_gate"]["passed"] is True
    assert summary["provider_quality_gate"]["sample_count"] == 2
    assert summary["provider_quality_gate"]["passed_count"] == 2
    assert summary["provider_quality_gate"]["min_roi_color_histogram_similarity"] >= 0.9
    assert summary["provider_quality_gate"]["min_roi_average_hash_similarity"] >= 0.9
    assert summary["provider_quality_gate"]["min_roi_edge_similarity"] >= 0.9
    assert summary["model_id"] == "gpt-image-test"
    assert summary["quality"] == "medium"
    assert len(summary["sample_results"]) == 2
    assert all(item["checklist_passed"] is True for item in summary["sample_results"])
    assert all(
        item["generated_image"]["path"] == "redacted_outputs_path"
        for item in summary["sample_results"]
    )
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "generated-말차_푸딩.png",
        "generated-피스타치오_케이크.png",
    ]

    persisted = json.loads(summary_path.read_text(encoding="utf-8"))
    serialized = json.dumps(persisted, ensure_ascii=False)
    assert persisted == summary
    assert str(output_dir) not in serialized
    assert "원본 사진의 상품 형태" not in serialized
    assert "reference_image_b64" not in serialized
    assert "b64_json" not in serialized


def test_provider_quality_gate_summary_includes_cost_guard(
    tmp_path: Path,
) -> None:
    reference_path = tmp_path / "reference.png"
    _write_reference(reference_path)
    output_dir = tmp_path / "outputs"
    summary_path = tmp_path / "provider-summary.json"

    summary = build_provider_quality_gate_summary(
        samples=(
            ReferenceSample(
                slug="budgeted",
                product_name="말차 푸딩",
                reference_path=reference_path,
                roi=(0.12, 0.08, 0.88, 0.78),
            ),
        ),
        output_dir=output_dir,
        summary_path=summary_path,
        evidence_date="2026-06-17",
        model_id="gpt-image-2",
        quality="medium",
        image_generator=_fake_image_generator,
        max_estimated_cost_usd=0.01,
    )

    assert summary["provider_quality_gate"]["passed"] is True
    assert summary["cost"]["estimated"] is True
    assert summary["cost"]["total_usd"] == 0.00369
    assert summary["cost"]["budget"] == {
        "max_usd": 0.01,
        "passed": True,
        "over_by_usd": 0.0,
    }
    assert summary["cost_guard"]["passed"] is True
    assert summary["openai_image_edit_preservation"] == "passed"


def test_provider_quality_gate_fails_when_cost_budget_is_exceeded(
    tmp_path: Path,
) -> None:
    reference_path = tmp_path / "reference.png"
    _write_reference(reference_path)
    output_dir = tmp_path / "outputs"
    summary_path = tmp_path / "provider-summary.json"

    summary = build_provider_quality_gate_summary(
        samples=(
            ReferenceSample(
                slug="over-budget",
                product_name="말차 푸딩",
                reference_path=reference_path,
                roi=(0.12, 0.08, 0.88, 0.78),
            ),
        ),
        output_dir=output_dir,
        summary_path=summary_path,
        evidence_date="2026-06-17",
        model_id="gpt-image-2",
        quality="medium",
        image_generator=_fake_image_generator,
        max_estimated_cost_usd=0.001,
    )

    assert summary["provider_quality_gate"]["passed"] is True
    assert summary["cost_guard"]["passed"] is False
    assert summary["cost"]["budget"] == {
        "max_usd": 0.001,
        "passed": False,
        "over_by_usd": 0.00269,
    }
    assert summary["openai_image_edit_preservation"] == "failed"


def test_provider_quality_gate_fails_for_low_roi_similarity_and_text_risk(
    tmp_path: Path,
) -> None:
    reference_path = tmp_path / "reference.png"
    _write_reference(reference_path)
    output_dir = tmp_path / "outputs"
    summary_path = tmp_path / "provider-summary.json"

    summary = build_provider_quality_gate_summary(
        samples=(
            ReferenceSample(
                slug="bad",
                product_name="말차 푸딩",
                reference_path=reference_path,
                roi=(0.12, 0.08, 0.88, 0.78),
            ),
        ),
        output_dir=output_dir,
        summary_path=summary_path,
        evidence_date="2026-06-17",
        model_id="gpt-image-test",
        quality="medium",
        image_generator=_fake_text_heavy_mismatch_generator,
    )

    result = summary["sample_results"][0]
    checklist = result["checklist"]
    assert summary["provider_quality_gate"]["passed"] is False
    assert result["checklist_passed"] is False
    assert checklist["roi_color_histogram_similarity_ge_threshold"] is False
    assert checklist["roi_average_hash_similarity_ge_threshold"] is False
    assert checklist["text_contamination_risk_le_threshold"] is False
    assert (
        result["metrics"]["text_contamination_risk_score"]
        > summary["thresholds"]["max_text_contamination_risk_score"]
    )


def _write_reference(
    path: Path,
    *,
    background: tuple[int, int, int] = (240, 230, 210),
    product: tuple[int, int, int] = (210, 90, 120),
) -> None:
    image = Image.new("RGB", (256, 256), color=background)
    draw = ImageDraw.Draw(image)
    draw.ellipse((70, 45, 190, 170), fill=product)
    draw.rectangle((40, 180, 220, 230), fill=(80, 60, 50))
    image.save(path)


def _fake_image_generator(
    *,
    reference_bytes: bytes,
    output_dir: Path,
    prompt: str,
    request: GenerationRequest,
) -> ImageResult:
    assert reference_bytes
    assert "원본 사진의 상품 형태" in prompt
    assert request.product_name
    output_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(reference_bytes)) as source:
        image = source.convert("RGB").resize((1024, 1024))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, image.height - 40, image.width, image.height), fill=(35, 35, 35))
    output_path = output_dir / f"generated-{request.product_name.replace(' ', '_')}.png"
    image.save(output_path)
    return ImageResult(path=str(output_path), usage={"total_tokens": 123})


def _fake_text_heavy_mismatch_generator(
    *,
    reference_bytes: bytes,
    output_dir: Path,
    prompt: str,
    request: GenerationRequest,
) -> ImageResult:
    assert reference_bytes
    assert "이미지 안에" in prompt
    assert request.product_name
    output_dir.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1024, 1024), color=(245, 245, 245))
    draw = ImageDraw.Draw(image)
    for y in range(80, 460, 48):
        draw.text((80, y), "MATCHA PUDDING SALE EVENT", fill=(10, 10, 10))
    draw.rectangle((280, 620, 740, 900), fill=(20, 30, 180))
    output_path = output_dir / "bad-generated.png"
    image.save(output_path)
    return ImageResult(path=str(output_path), usage={"total_tokens": 123})
