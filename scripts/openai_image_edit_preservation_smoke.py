"""Live OpenAI image-edit preservation smoke.

Costs real money and sends one public reference image plus a generated prompt to
OpenAI. Persistent output is redacted: the generated image stays under
``outputs/`` and only a metric summary is written to ``docs/evidence/``.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import date
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any

from dotenv import load_dotenv
from PIL import Image, ImageStat

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
    reference_bytes = reference_path.read_bytes()
    request = GenerationRequest(
        campaign_purpose="seasonal_event",
        product_name="말차 푸딩",
        tone="premium",
        template_hint="minimal_premium",
        price_text="2개 세트",
        user_constraints="원본 사진의 상품 형태와 컵 실루엣을 보존하고 배경만 광고용으로 정돈",
    )
    prompt = build_image_prompt(
        request,
        ranked_template=request.template_hint,
        has_reference=True,
    )

    backend = None
    if image_generator is None:
        backend = OpenAIImageBackend(
            output_dir=output_dir,
            model_id=model_id,
            quality=quality,
        )
        image_generator = _live_image_generator(backend)

    started = perf_counter()
    result = image_generator(
        reference_bytes=reference_bytes,
        output_dir=output_dir,
        prompt=prompt,
    )
    elapsed_ms = round((perf_counter() - started) * 1000)
    generated_path = Path(result.path)
    metrics = _image_metrics(reference_path, generated_path)
    checklist_passed = (
        metrics["generated_exists"]
        and metrics["generated_nonblank"]
        and metrics["generated_size"] == [1024, 1024]
        and metrics["color_histogram_similarity"] >= 0.25
    )

    summary = {
        "openai_image_edit_preservation": "passed" if checklist_passed else "failed",
        "evidence_date": evidence_date,
        "model_id": model_id or getattr(backend, "model_id", None) or "injected",
        "quality": quality or getattr(backend, "quality", None) or "injected",
        "used_reference": True,
        "elapsed_ms": elapsed_ms,
        "usage": result.usage,
        "reference_image": {
            "source": str(reference_path),
            "sha256": _sha256_bytes(reference_bytes),
            "committed_public_sample": True,
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
        },
        "metrics": metrics,
        "checklist": {
            "generated_file_exists": metrics["generated_exists"],
            "generated_nonblank": metrics["generated_nonblank"],
            "generated_size_1024": metrics["generated_size"] == [1024, 1024],
            "color_histogram_similarity_ge_0_25": (metrics["color_histogram_similarity"] >= 0.25),
        },
        "checklist_passed": checklist_passed,
        "privacy_boundary": {
            "raw_prompt_committed": False,
            "raw_model_response_committed": False,
            "generated_image_committed": False,
            "reference_image_public_sample": True,
        },
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


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


def _image_metrics(reference_path: Path, generated_path: Path) -> dict[str, Any]:
    if not generated_path.exists():
        return {
            "generated_exists": False,
            "reference_size": None,
            "generated_size": None,
            "generated_nonblank": False,
            "color_histogram_similarity": 0.0,
            "average_hash_similarity": 0.0,
        }

    with Image.open(reference_path) as reference_source:
        reference = reference_source.convert("RGB")
    with Image.open(generated_path) as generated_source:
        generated = generated_source.convert("RGB")

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
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--model-id", default=os.getenv("IMAGE_MODEL_ID"))
    parser.add_argument("--quality", default=os.getenv("IMAGE_QUALITY"))
    args = parser.parse_args()

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
