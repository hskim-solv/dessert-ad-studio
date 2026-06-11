from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from dessert_ad_studio.backends.base import AdBackendError, CopyBackend, ImageBackend
from dessert_ad_studio.backends.flux2 import Flux2Backend
from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.backends.openai_copy import OpenAICopyBackend
from dessert_ad_studio.backends.openai_image import OpenAIImageBackend
from dessert_ad_studio.generation_logger import GenerationLogger
from dessert_ad_studio.prompts import build_image_prompt
from dessert_ad_studio.reference_image import ReferenceImageError, decode_reference_image
from dessert_ad_studio.schemas import GenerationRequest, GenerationResponse
from dessert_ad_studio.triton import LocalTemplateScorer, TritonTemplateScorer

load_dotenv()

app = FastAPI(title="Dessert Ad Studio API")


def get_template_scorer():
    require_triton = os.getenv("REQUIRE_TRITON", "0") == "1"
    triton_url = os.getenv("TRITON_URL", "localhost:8001")
    if require_triton:
        return TritonTemplateScorer(url=triton_url)
    return LocalTemplateScorer()


@lru_cache(maxsize=None)
def _copy_backend_for(name: str, output_dir: str) -> CopyBackend | None:
    if name == "mock":
        return MockAdBackend(output_dir=output_dir)
    if name == "openai":
        return OpenAICopyBackend()
    return None


@lru_cache(maxsize=None)
def _image_backend_for(name: str, output_dir: str) -> ImageBackend | None:
    if name == "mock":
        return MockAdBackend(output_dir=output_dir)
    if name == "openai":
        return OpenAIImageBackend(output_dir=output_dir)
    if name == "flux2":
        return Flux2Backend(output_dir=output_dir)
    return None


def get_copy_backend() -> CopyBackend:
    name = os.getenv("COPY_BACKEND", "mock")
    backend = _copy_backend_for(name, os.getenv("OUTPUT_DIR", "outputs"))
    if backend is None:
        raise HTTPException(status_code=501, detail=f"unknown copy backend: {name}")
    return backend


def get_image_backend() -> ImageBackend:
    name = os.getenv("IMAGE_BACKEND", "mock")
    backend = _image_backend_for(name, os.getenv("OUTPUT_DIR", "outputs"))
    if backend is None:
        raise HTTPException(status_code=501, detail=f"unknown image backend: {name}")
    return backend


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/rank-templates")
def rank_templates(request: GenerationRequest):
    scorer = get_template_scorer()
    try:
        return scorer.rank(request)
    except Exception as exc:
        if os.getenv("REQUIRE_TRITON", "0") == "1":
            raise HTTPException(
                status_code=503,
                detail=f"Triton template scoring failed: {exc}",
            ) from exc
        return LocalTemplateScorer().rank(request)


@app.post("/generate", response_model=GenerationResponse)
def generate(request: GenerationRequest) -> GenerationResponse:
    started = perf_counter()
    ranking = rank_templates(request)
    copy_backend = get_copy_backend()
    image_backend = get_image_backend()

    try:
        reference_image = decode_reference_image(request.reference_image_b64)
    except ReferenceImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if reference_image is not None and not image_backend.supports_reference_image:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{image_backend.name} 이미지 백엔드는 아직 참고 이미지를 지원하지 않습니다. "
                "참고 이미지 없이 다시 시도하거나 IMAGE_BACKEND=openai로 전환해주세요."
            ),
        )

    image_prompt = build_image_prompt(
        request,
        ranked_template=ranking.template_name,
        has_reference=reference_image is not None,
    )

    logger = GenerationLogger(Path(os.getenv("GENERATION_LOG_PATH", "logs/generations.jsonl")))
    log_record = {
        "campaign_purpose": request.campaign_purpose,
        "template": ranking.template_name,
        "template_scorer": ranking.scorer,
        "triton_latency_ms": ranking.latency_ms,
        "copy_backend": copy_backend.name,
        "copy_model_id": getattr(copy_backend, "model_id", None),
        "image_backend": image_backend.name,
        "image_model_id": getattr(image_backend, "model_id", None),
        "used_reference": reference_image is not None,
        "reference_image_name": request.reference_image_name,
    }

    copy_result = None
    try:
        copy_result = copy_backend.generate_copy(request)
        image_result = image_backend.generate_image(
            request,
            image_prompt=image_prompt,
            reference_image=reference_image,
        )
    except AdBackendError as exc:
        if copy_result is not None:
            # The copy call already spent tokens; keep them in the quota log
            # even though the request itself fails.
            try:
                logger.write(
                    {
                        **log_record,
                        "copy_usage": copy_result.usage,
                        "image_usage": None,
                        "image_path": None,
                        "error": exc.detail,
                        "elapsed_ms": (perf_counter() - started) * 1000,
                    }
                )
            except OSError:
                pass
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    elapsed_ms = (perf_counter() - started) * 1000

    try:
        logger.write(
            {
                **log_record,
                "copy_usage": copy_result.usage,
                "image_usage": image_result.usage,
                "elapsed_ms": elapsed_ms,
                "image_path": image_result.path,
            }
        )
    except OSError:
        pass  # best-effort cost log; never fail a completed generation on it

    return GenerationResponse(
        copy_options=copy_result.options,
        selected_template=ranking,
        image_path=image_result.path,
        image_backend=image_backend.name,
        copy_backend=copy_backend.name,
        used_reference=reference_image is not None,
        prompt_summary=image_prompt,
        elapsed_ms=elapsed_ms,
    )
