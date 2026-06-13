from __future__ import annotations

import os
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from threading import Lock
from time import perf_counter

import dessert_ad_studio.workflow as workflow_module
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response

from dessert_ad_studio.backends.base import AdBackendError, CopyBackend, ImageBackend
from dessert_ad_studio.backends.flux2 import Flux2Backend
from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.backends.openai_copy import OpenAICopyBackend
from dessert_ad_studio.backends.openai_image import OpenAIImageBackend
from dessert_ad_studio.product_analysis import MockProductAnalyzer, ProductAnalyzer
from dessert_ad_studio.reference_image import ReferenceImageError, decode_reference_image
from dessert_ad_studio.schemas import GenerationRequest, GenerationResponse
from dessert_ad_studio.triton import LocalTemplateScorer, TritonTemplateScorer
from dessert_ad_studio.workflow import (
    GenerationWorkflowDependencies,
    run_generation_workflow,
)

load_dotenv()

app = FastAPI(title="Dessert Ad Studio API")
_METRICS_LOCK = Lock()
_HTTP_REQUESTS_TOTAL: defaultdict[tuple[str, str, str], int] = defaultdict(int)
_HTTP_REQUEST_LATENCY_SECONDS_TOTAL: defaultdict[tuple[str, str], float] = defaultdict(float)


class _BestEffortGenerationLogger:
    def __init__(self, log_path: str | Path) -> None:
        from dessert_ad_studio.generation_logger import GenerationLogger

        self._logger = GenerationLogger(log_path)

    def write(self, record: dict[str, object]) -> None:
        try:
            self._logger.write(record)
        except OSError:
            pass


workflow_module.GenerationLogger = _BestEffortGenerationLogger


class _WorkflowGenerationTelemetry:
    def __init__(self) -> None:
        self.started = perf_counter()
        self.ranking = None
        self.copy_result = None


class _ApiTemplateRankingScorer:
    def __init__(self, telemetry: _WorkflowGenerationTelemetry) -> None:
        self._telemetry = telemetry

    def rank(self, request: GenerationRequest):
        ranking = rank_templates(request)
        self._telemetry.ranking = ranking
        return ranking


class _RecordingCopyBackend:
    def __init__(self, backend: CopyBackend, telemetry: _WorkflowGenerationTelemetry) -> None:
        self._backend = backend
        self._telemetry = telemetry

    @property
    def name(self) -> str:
        return self._backend.name

    @property
    def model_id(self) -> str | None:
        return getattr(self._backend, "model_id", None)

    def generate_copy(self, request: GenerationRequest):
        result = self._backend.generate_copy(request)
        self._telemetry.copy_result = result
        return result


class _FailureLoggingImageBackend:
    def __init__(
        self,
        backend: ImageBackend,
        telemetry: _WorkflowGenerationTelemetry,
        copy_backend: _RecordingCopyBackend,
        product_analysis_backend: str,
        log_path: Path,
    ) -> None:
        self._backend = backend
        self._telemetry = telemetry
        self._copy_backend = copy_backend
        self._product_analysis_backend = product_analysis_backend
        self._log_path = log_path

    @property
    def name(self) -> str:
        return self._backend.name

    @property
    def model_id(self) -> str | None:
        return getattr(self._backend, "model_id", None)

    @property
    def supports_reference_image(self) -> bool:
        return self._backend.supports_reference_image

    def generate_image(
        self,
        request: GenerationRequest,
        image_prompt: str,
        reference_image: bytes | None = None,
    ):
        try:
            return self._backend.generate_image(
                request,
                image_prompt=image_prompt,
                reference_image=reference_image,
            )
        except AdBackendError as exc:
            self._write_failure_log(request, reference_image=reference_image, exc=exc)
            raise

    def _write_failure_log(
        self,
        request: GenerationRequest,
        reference_image: bytes | None,
        exc: AdBackendError,
    ) -> None:
        copy_result = self._telemetry.copy_result
        if copy_result is None:
            return

        ranking = self._telemetry.ranking
        record = {
            "campaign_purpose": request.campaign_purpose,
            "template": getattr(ranking, "template_name", None),
            "template_scorer": getattr(ranking, "scorer", None),
            "triton_latency_ms": getattr(ranking, "latency_ms", None),
            "copy_backend": self._copy_backend.name,
            "copy_model_id": self._copy_backend.model_id,
            "image_backend": self.name,
            "image_model_id": self.model_id,
            "product_analysis_backend": self._product_analysis_backend,
            "used_reference": reference_image is not None,
            "reference_image_name": request.reference_image_name,
            "copy_usage": copy_result.usage,
            "image_usage": None,
            "image_path": None,
            "error": exc.detail,
            "elapsed_ms": (perf_counter() - self._telemetry.started) * 1000,
        }
        _BestEffortGenerationLogger(self._log_path).write(record)


def _record_http_request(method: str, path: str, status_code: int, elapsed_seconds: float) -> None:
    method = method.upper()
    status = str(status_code)
    with _METRICS_LOCK:
        _HTTP_REQUESTS_TOTAL[(method, path, status)] += 1
        _HTTP_REQUEST_LATENCY_SECONDS_TOTAL[(method, path)] += elapsed_seconds


def _prometheus_labels(labels: dict[str, str]) -> str:
    rendered = ",".join(f'{key}="{value}"' for key, value in labels.items())
    return "{" + rendered + "}" if rendered else ""


def _template_scorer_name(scorer) -> str:
    if isinstance(scorer, TritonTemplateScorer):
        return "triton-template-scorer"
    return "local-template-scorer"


def _is_triton_ready(url: str) -> bool:
    import tritonclient.http as httpclient

    client = httpclient.InferenceServerClient(url=url)
    return bool(client.is_server_live() and client.is_model_ready("template_scorer"))


@app.middleware("http")
async def record_metrics(request: Request, call_next):
    started = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        _record_http_request(
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            elapsed_seconds=perf_counter() - started,
        )


def get_template_scorer():
    require_triton = os.getenv("REQUIRE_TRITON", "0") == "1"
    triton_url = os.getenv("TRITON_URL", "localhost:8000")
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


def _product_analyzer_for(name: str) -> ProductAnalyzer | None:
    if name == "mock":
        return MockProductAnalyzer()
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


def get_product_analyzer() -> ProductAnalyzer:
    name = os.getenv("PRODUCT_ANALYSIS_BACKEND", "mock")
    analyzer = _product_analyzer_for(name)
    if analyzer is None:
        raise HTTPException(
            status_code=501,
            detail=f"unknown product analysis backend: {name}",
        )
    return analyzer


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/livez")
def livez() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    try:
        copy_backend = get_copy_backend()
        image_backend = get_image_backend()
        product_analyzer = get_product_analyzer()
        template_scorer = get_template_scorer()
        if isinstance(template_scorer, TritonTemplateScorer) and not _is_triton_ready(
            template_scorer.url
        ):
            raise HTTPException(status_code=503, detail="triton template_scorer is not ready")
    except HTTPException as exc:
        raise HTTPException(status_code=503, detail=f"not ready: {exc.detail}") from exc

    return {
        "status": "ready",
        "copy_backend": copy_backend.name,
        "image_backend": image_backend.name,
        "product_analysis_backend": product_analyzer.name,
        "template_scorer": _template_scorer_name(template_scorer),
    }


@app.get("/metrics")
def metrics() -> Response:
    lines = [
        "# HELP dessert_ad_studio_info Static application info.",
        "# TYPE dessert_ad_studio_info gauge",
        'dessert_ad_studio_info{service="api"} 1',
        "# HELP dessert_ad_studio_http_requests_total Total HTTP requests.",
        "# TYPE dessert_ad_studio_http_requests_total counter",
    ]
    with _METRICS_LOCK:
        for (method, path, status), count in sorted(_HTTP_REQUESTS_TOTAL.items()):
            labels = _prometheus_labels({"method": method, "path": path, "status": status})
            lines.append(f"dessert_ad_studio_http_requests_total{labels} {count}")
        lines.extend(
            [
                "# HELP dessert_ad_studio_http_request_latency_seconds_total "
                "Total HTTP request latency in seconds.",
                "# TYPE dessert_ad_studio_http_request_latency_seconds_total counter",
            ]
        )
        for (method, path), total in sorted(_HTTP_REQUEST_LATENCY_SECONDS_TOTAL.items()):
            labels = _prometheus_labels({"method": method, "path": path})
            lines.append(f"dessert_ad_studio_http_request_latency_seconds_total{labels} {total:.6f}")

    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


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
    telemetry = _WorkflowGenerationTelemetry()
    template_scorer = _ApiTemplateRankingScorer(telemetry)
    copy_backend = _RecordingCopyBackend(get_copy_backend(), telemetry)
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

    product_analyzer = get_product_analyzer()
    log_path = Path(os.getenv("GENERATION_LOG_PATH", "logs/generations.jsonl"))
    dependencies = GenerationWorkflowDependencies(
        template_scorer=template_scorer,
        copy_backend=copy_backend,
        image_backend=_FailureLoggingImageBackend(
            image_backend,
            telemetry=telemetry,
            copy_backend=copy_backend,
            product_analysis_backend=product_analyzer.name,
            log_path=log_path,
        ),
        product_analyzer=product_analyzer,
        log_path=log_path,
    )

    try:
        return run_generation_workflow(request, dependencies).response
    except ReferenceImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AdBackendError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
