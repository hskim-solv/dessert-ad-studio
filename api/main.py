from __future__ import annotations

import os
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, HTTPException

from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.generation_logger import GenerationLogger
from dessert_ad_studio.prompts import build_image_prompt
from dessert_ad_studio.schemas import GenerationRequest, GenerationResponse
from dessert_ad_studio.triton import LocalTemplateScorer, TritonTemplateScorer

app = FastAPI(title="Dessert Ad Studio API")


def get_template_scorer():
    require_triton = os.getenv("REQUIRE_TRITON", "0") == "1"
    triton_url = os.getenv("TRITON_URL", "localhost:8001")
    if require_triton:
        return TritonTemplateScorer(url=triton_url)
    return TritonTemplateScorer(url=triton_url)


def get_backend() -> MockAdBackend:
    backend_name = os.getenv("IMAGE_BACKEND", "mock")
    if backend_name != "mock":
        raise HTTPException(
            status_code=501,
            detail=f"image backend is not enabled in API tests: {backend_name}",
        )
    return MockAdBackend(output_dir=os.getenv("OUTPUT_DIR", "outputs"))


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
    backend = get_backend()
    copy_options = backend.generate_copy(request)
    image_prompt = build_image_prompt(request, ranked_template=ranking.template_name)
    image_path = backend.generate_image(request, image_prompt=image_prompt)
    elapsed_ms = (perf_counter() - started) * 1000

    logger = GenerationLogger(Path(os.getenv("GENERATION_LOG_PATH", "logs/generations.jsonl")))
    logger.write(
        {
            "campaign_purpose": request.campaign_purpose,
            "template": ranking.template_name,
            "template_scorer": ranking.scorer,
            "triton_latency_ms": ranking.latency_ms,
            "image_backend": backend.name,
            "elapsed_ms": elapsed_ms,
            "image_path": image_path,
        }
    )

    return GenerationResponse(
        copy_options=copy_options,
        selected_template=ranking,
        image_path=image_path,
        image_backend=backend.name,
        prompt_summary=image_prompt,
        elapsed_ms=elapsed_ms,
    )
