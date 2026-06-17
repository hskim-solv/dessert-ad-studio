"""Live OpenAI image-edit preservation smoke.

Costs real money and sends one public reference image plus a generated prompt to
OpenAI. Persistent output is redacted: the generated image stays under
``outputs/`` and only a metric summary is written to ``docs/evidence/``.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any

from dotenv import load_dotenv
from PIL import Image, ImageFilter, ImageStat

from dessert_ad_studio.backends.base import ImageResult
from dessert_ad_studio.backends.openai_image import OpenAIImageBackend
from dessert_ad_studio.prompts import build_image_prompt
from dessert_ad_studio.schemas import GenerationRequest

ImageGenerator = Callable[..., ImageResult]


DEFAULT_REFERENCE_PATH = Path(
    "docs/evidence/assets/real-sample-preservation/references/matcha-pudding.png"
)
DEFAULT_SUMMARY_PATH = Path("docs/evidence/openai-image-edit-preservation-live-summary.json")
DEFAULT_OUTPUT_DIR = Path("outputs/openai-image-edit-preservation")
NO_TEXT_CONSTRAINT = (
    "원본 사진의 상품 형태와 컵/디저트 실루엣을 보존하고 배경만 광고용으로 정돈. "
    "이미지 안에 글자, 로고, 가격, 메뉴판 텍스트를 생성하지 말 것."
)
DEFAULT_GATE_THRESHOLDS = {
    "min_roi_color_histogram_similarity": 0.30,
    "min_roi_average_hash_similarity": 0.60,
    "min_roi_edge_similarity": 0.55,
    "max_text_contamination_risk_score": 0.45,
    "max_sample_elapsed_ms": 30_000,
    "min_sample_pass_rate": 0.80,
}


@dataclass(frozen=True)
class ReferenceSample:
    slug: str
    product_name: str
    reference_path: Path
    roi: tuple[float, float, float, float]


PUBLIC_REFERENCE_SAMPLES = (
    ReferenceSample(
        slug="dessert-plate",
        product_name="디저트 플레이트",
        reference_path=Path(
            "docs/evidence/assets/real-sample-preservation/references/dessert-plate.png"
        ),
        roi=(0.08, 0.06, 0.92, 0.76),
    ),
    ReferenceSample(
        slug="matcha-pudding",
        product_name="말차 푸딩",
        reference_path=DEFAULT_REFERENCE_PATH,
        roi=(0.15, 0.10, 0.85, 0.78),
    ),
    ReferenceSample(
        slug="flower-box",
        product_name="플라워 박스",
        reference_path=Path(
            "docs/evidence/assets/real-sample-preservation/references/flower-box.png"
        ),
        roi=(0.08, 0.08, 0.92, 0.76),
    ),
)


def build_live_image_edit_preservation_summary(
    *,
    reference_path: Path,
    output_dir: Path,
    summary_path: Path,
    evidence_date: str,
    model_id: str | None = None,
    quality: str | None = None,
    image_generator: ImageGenerator | None = None,
) -> dict[str, Any]:
    return build_provider_quality_gate_summary(
        samples=(
            ReferenceSample(
                slug=reference_path.stem,
                product_name="말차 푸딩",
                reference_path=reference_path,
                roi=(0.15, 0.10, 0.85, 0.78),
            ),
        ),
        output_dir=output_dir,
        summary_path=summary_path,
        evidence_date=evidence_date,
        model_id=model_id,
        quality=quality,
        image_generator=image_generator,
    )


def build_provider_quality_gate_summary(
    *,
    samples: tuple[ReferenceSample, ...],
    output_dir: Path,
    summary_path: Path,
    evidence_date: str,
    model_id: str | None = None,
    quality: str | None = None,
    image_generator: ImageGenerator | None = None,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    if not samples:
        raise ValueError("samples must not be empty")

    active_thresholds = {**DEFAULT_GATE_THRESHOLDS, **(thresholds or {})}

    backend = None
    if image_generator is None:
        backend = OpenAIImageBackend(
            output_dir=output_dir,
            model_id=model_id,
            quality=quality,
        )
        image_generator = _live_image_generator(backend)

    sample_results: list[dict[str, Any]] = []
    total_started = perf_counter()
    for sample in samples:
        sample_result = _run_reference_sample(
            sample=sample,
            output_dir=output_dir,
            model_image_generator=image_generator,
            thresholds=active_thresholds,
        )
        sample_results.append(sample_result)

    total_elapsed_ms = round((perf_counter() - total_started) * 1000)
    passed_count = sum(1 for result in sample_results if result["checklist_passed"])
    pass_rate = passed_count / len(sample_results)
    provider_gate_passed = pass_rate >= active_thresholds["min_sample_pass_rate"]
    roi_color_scores = [
        result["metrics"]["roi_color_histogram_similarity"] for result in sample_results
    ]
    roi_hash_scores = [
        result["metrics"]["roi_average_hash_similarity"] for result in sample_results
    ]
    roi_edge_scores = [result["metrics"]["roi_edge_similarity"] for result in sample_results]

    summary = {
        "openai_image_edit_preservation": "passed" if provider_gate_passed else "failed",
        "evidence_date": evidence_date,
        "model_id": model_id or getattr(backend, "model_id", None) or "injected",
        "quality": quality or getattr(backend, "quality", None) or "injected",
        "used_reference": True,
        "elapsed_ms": total_elapsed_ms,
        "usage": _aggregate_usage(sample_results),
        "thresholds": active_thresholds,
        "provider_quality_gate": {
            "passed": provider_gate_passed,
            "sample_count": len(sample_results),
            "passed_count": passed_count,
            "pass_rate": round(pass_rate, 6),
            "min_roi_color_histogram_similarity": round(min(roi_color_scores), 6),
            "min_roi_average_hash_similarity": round(min(roi_hash_scores), 6),
            "min_roi_edge_similarity": round(min(roi_edge_scores), 6),
            "max_text_contamination_risk_score": round(
                max(
                    result["metrics"]["text_contamination_risk_score"] for result in sample_results
                ),
                6,
            ),
        },
        "sample_results": sample_results,
        "privacy_boundary": {
            "raw_prompt_committed": False,
            "raw_model_response_committed": False,
            "generated_image_committed": False,
            "reference_image_public_sample": True,
        },
    }
    if len(sample_results) == 1:
        first = sample_results[0]
        summary.update(
            {
                "reference_image": first["reference_image"],
                "generated_image": first["generated_image"],
                "prompt": first["prompt"],
                "metrics": first["metrics"],
                "checklist": first["checklist"],
                "checklist_passed": first["checklist_passed"],
            }
        )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def _run_reference_sample(
    *,
    sample: ReferenceSample,
    output_dir: Path,
    model_image_generator: ImageGenerator,
    thresholds: dict[str, float],
) -> dict[str, Any]:
    reference_bytes = sample.reference_path.read_bytes()
    request = GenerationRequest(
        campaign_purpose="seasonal_event",
        product_name=sample.product_name,
        tone="premium",
        template_hint="minimal_premium",
        price_text="2개 세트",
        user_constraints=NO_TEXT_CONSTRAINT,
    )
    prompt = build_image_prompt(
        request,
        ranked_template=request.template_hint,
        has_reference=True,
    )
    started = perf_counter()
    result = model_image_generator(
        reference_bytes=reference_bytes,
        output_dir=output_dir,
        prompt=prompt,
    )
    elapsed_ms = round((perf_counter() - started) * 1000)
    generated_path = Path(result.path)
    metrics = _image_metrics(sample.reference_path, generated_path, roi=sample.roi)
    checklist = _sample_checklist(metrics=metrics, elapsed_ms=elapsed_ms, thresholds=thresholds)
    checklist_passed = all(checklist.values())
    return {
        "slug": sample.slug,
        "product_name": sample.product_name,
        "elapsed_ms": elapsed_ms,
        "usage": result.usage,
        "reference_image": {
            "source": str(sample.reference_path),
            "sha256": _sha256_bytes(reference_bytes),
            "committed_public_sample": True,
            "roi": list(sample.roi),
        },
        "generated_image": {
            "exists": generated_path.exists(),
            "committed": False,
            "path": "redacted_outputs_path",
            "sha256": _sha256_file(generated_path) if generated_path.exists() else None,
            "bytes": generated_path.stat().st_size if generated_path.exists() else 0,
        },
        "prompt": {
            "length": len(prompt),
            "sha256": _sha256_text(prompt),
            "no_text_instruction_present": "이미지 안에 글자" in prompt,
        },
        "metrics": metrics,
        "checklist": checklist,
        "checklist_passed": checklist_passed,
    }


def _live_image_generator(backend: OpenAIImageBackend) -> ImageGenerator:
    request = GenerationRequest(
        campaign_purpose="seasonal_event",
        product_name="말차 푸딩",
        tone="premium",
        template_hint="minimal_premium",
        price_text="2개 세트",
        user_constraints="원본 사진의 상품 형태와 컵 실루엣을 보존",
    )

    def generate(*, reference_bytes: bytes, output_dir: Path, prompt: str) -> ImageResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        return backend.generate_image(
            request,
            image_prompt=prompt,
            reference_image=reference_bytes,
        )

    return generate


def _sample_checklist(
    *,
    metrics: dict[str, Any],
    elapsed_ms: int,
    thresholds: dict[str, float],
) -> dict[str, bool]:
    return {
        "generated_file_exists": metrics["generated_exists"],
        "generated_nonblank": metrics["generated_nonblank"],
        "generated_size_1024": metrics["generated_size"] == [1024, 1024],
        "sample_elapsed_ms_le_threshold": elapsed_ms <= thresholds["max_sample_elapsed_ms"],
        "roi_color_histogram_similarity_ge_threshold": (
            metrics["roi_color_histogram_similarity"]
            >= thresholds["min_roi_color_histogram_similarity"]
        ),
        "roi_average_hash_similarity_ge_threshold": (
            metrics["roi_average_hash_similarity"] >= thresholds["min_roi_average_hash_similarity"]
        ),
        "roi_edge_similarity_ge_threshold": (
            metrics["roi_edge_similarity"] >= thresholds["min_roi_edge_similarity"]
        ),
        "text_contamination_risk_le_threshold": (
            metrics["text_contamination_risk_score"]
            <= thresholds["max_text_contamination_risk_score"]
        ),
    }


def _aggregate_usage(sample_results: list[dict[str, Any]]) -> dict[str, Any] | None:
    usage_records = [result.get("usage") for result in sample_results if result.get("usage")]
    if not usage_records:
        return None
    total_tokens = [
        record.get("total_tokens")
        for record in usage_records
        if isinstance(record, dict) and isinstance(record.get("total_tokens"), int)
    ]
    return {
        "sample_count": len(sample_results),
        "total_tokens": sum(total_tokens) if total_tokens else None,
    }


def _image_metrics(
    reference_path: Path,
    generated_path: Path,
    *,
    roi: tuple[float, float, float, float] | None = None,
) -> dict[str, Any]:
    if not generated_path.exists():
        return {
            "generated_exists": False,
            "reference_size": None,
            "generated_size": None,
            "generated_nonblank": False,
            "color_histogram_similarity": 0.0,
            "average_hash_similarity": 0.0,
            "roi_color_histogram_similarity": 0.0,
            "roi_average_hash_similarity": 0.0,
            "roi_edge_similarity": 0.0,
            "text_contamination_risk_score": 1.0,
        }

    with Image.open(reference_path) as reference_source:
        reference = reference_source.convert("RGB")
    with Image.open(generated_path) as generated_source:
        generated = generated_source.convert("RGB")

    reference_roi = _crop_normalized_roi(reference, roi)
    generated_roi = _crop_normalized_roi(generated, roi)
    generated_nonblank = _is_nonblank(generated)
    return {
        "generated_exists": True,
        "reference_size": list(reference.size),
        "generated_size": list(generated.size),
        "generated_nonblank": generated_nonblank,
        "color_histogram_similarity": round(
            _histogram_intersection(reference, generated),
            6,
        ),
        "average_hash_similarity": round(_average_hash_similarity(reference, generated), 6),
        "roi_color_histogram_similarity": round(
            _histogram_intersection(reference_roi, generated_roi),
            6,
        ),
        "roi_average_hash_similarity": round(
            _average_hash_similarity(reference_roi, generated_roi),
            6,
        ),
        "roi_edge_similarity": round(_edge_similarity(reference_roi, generated_roi), 6),
        "text_contamination_risk_score": round(_text_contamination_risk_score(generated), 6),
    }


def _is_nonblank(image: Image.Image) -> bool:
    grayscale = image.convert("L")
    extrema = grayscale.getextrema()
    return extrema[1] - extrema[0] > 8


def _histogram_intersection(reference: Image.Image, generated: Image.Image) -> float:
    ref = reference.resize((256, 256)).histogram()
    gen = generated.resize((256, 256)).histogram()
    ref_total = sum(ref) or 1
    gen_total = sum(gen) or 1
    return sum(min(a / ref_total, b / gen_total) for a, b in zip(ref, gen))


def _crop_normalized_roi(
    image: Image.Image,
    roi: tuple[float, float, float, float] | None,
) -> Image.Image:
    if roi is None:
        return image
    left, top, right, bottom = roi
    width, height = image.size
    box = (
        max(0, min(width - 1, round(left * width))),
        max(0, min(height - 1, round(top * height))),
        max(1, min(width, round(right * width))),
        max(1, min(height, round(bottom * height))),
    )
    if box[2] <= box[0] or box[3] <= box[1]:
        return image
    return image.crop(box)


def _edge_similarity(reference: Image.Image, generated: Image.Image) -> float:
    reference_edges = reference.convert("L").resize((128, 128)).filter(ImageFilter.FIND_EDGES)
    generated_edges = generated.convert("L").resize((128, 128)).filter(ImageFilter.FIND_EDGES)
    return _average_hash_similarity(reference_edges.convert("RGB"), generated_edges.convert("RGB"))


def _average_hash_similarity(reference: Image.Image, generated: Image.Image) -> float:
    ref_hash = _average_hash(reference)
    gen_hash = _average_hash(generated)
    matches = sum(1 for ref_bit, gen_bit in zip(ref_hash, gen_hash) if ref_bit == gen_bit)
    return matches / len(ref_hash)


def _average_hash(image: Image.Image) -> tuple[bool, ...]:
    small = image.convert("L").resize((8, 8))
    values = list(ImageStat.Stat(small).mean)
    threshold = values[0]
    pixels = list(small.tobytes())
    return tuple(pixel >= threshold for pixel in pixels)


def _text_contamination_risk_score(image: Image.Image) -> float:
    grayscale = image.convert("L").resize((512, 512))
    dark_mask = bytearray(1 if pixel < 150 else 0 for pixel in grayscale.tobytes())
    width, height = grayscale.size
    visited = bytearray(width * height)
    text_like_components = 0

    for index, is_dark in enumerate(dark_mask):
        if not is_dark or visited[index]:
            continue
        stack = [index]
        visited[index] = 1
        pixels = 0
        min_x = width
        max_x = 0
        min_y = height
        max_y = 0
        while stack:
            current = stack.pop()
            pixels += 1
            y, x = divmod(current, width)
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            for neighbor in _neighbor_indexes(x=x, y=y, width=width, height=height):
                if dark_mask[neighbor] and not visited[neighbor]:
                    visited[neighbor] = 1
                    stack.append(neighbor)
        component_width = max_x - min_x + 1
        component_height = max_y - min_y + 1
        if _is_text_like_component(
            pixels=pixels,
            width=component_width,
            height=component_height,
        ):
            text_like_components += 1

    return min(1.0, text_like_components / 12)


def _neighbor_indexes(*, x: int, y: int, width: int, height: int) -> tuple[int, ...]:
    neighbors = []
    for next_x, next_y in (
        (x - 1, y),
        (x + 1, y),
        (x, y - 1),
        (x, y + 1),
    ):
        if 0 <= next_x < width and 0 <= next_y < height:
            neighbors.append(next_y * width + next_x)
    return tuple(neighbors)


def _is_text_like_component(*, pixels: int, width: int, height: int) -> bool:
    if pixels < 3:
        return False
    if not (1 <= width <= 80 and 2 <= height <= 30):
        return False
    area = width * height
    density = pixels / area
    return 0.05 <= density <= 1.00


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise SystemExit("OPENAI_API_KEY가 없습니다. .env 또는 환경변수를 확인하세요.")

    parser = argparse.ArgumentParser(
        description="Run a live OpenAI image-edit preservation smoke with redacted evidence.",
        allow_abbrev=False,
    )
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE_PATH)
    parser.add_argument(
        "--reference-set",
        choices=("single", "public-samples"),
        default="single",
        help="Use one reference image or the three committed public sample references.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--model-id", default=os.getenv("IMAGE_MODEL_ID"))
    parser.add_argument("--quality", default=os.getenv("IMAGE_QUALITY"))
    args = parser.parse_args()

    if args.reference_set == "public-samples":
        summary = build_provider_quality_gate_summary(
            samples=PUBLIC_REFERENCE_SAMPLES,
            output_dir=args.output_dir,
            summary_path=args.summary,
            evidence_date=args.date,
            model_id=args.model_id,
            quality=args.quality,
        )
    else:
        summary = build_live_image_edit_preservation_summary(
            reference_path=args.reference,
            output_dir=args.output_dir,
            summary_path=args.summary,
            evidence_date=args.date,
            model_id=args.model_id,
            quality=args.quality,
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["openai_image_edit_preservation"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
