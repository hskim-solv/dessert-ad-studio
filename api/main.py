from __future__ import annotations

import asyncio
import json
import os
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any, AsyncIterator
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from dessert_ad_studio.a2a import (
    A2AInputError,
    A2ATaskStore,
    build_agent_card,
    completed_generation_task,
    extract_generation_request,
)
from dessert_ad_studio.agentic_rag import (
    build_agentic_rag_graph,
    build_agentic_rag_initial_state,
    build_generation_workflow_executor,
)
from dessert_ad_studio.backends.base import AdBackendError, CopyBackend, ImageBackend
from dessert_ad_studio.backends.flux2 import Flux2Backend
from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.backends.openai_copy import OpenAICopyBackend
from dessert_ad_studio.backends.openai_image import OpenAIImageBackend
from dessert_ad_studio.generation_jobs import (
    GENERATION_JOB_CANCEL_UNSUPPORTED_DETAIL,
    GenerationJobQueueError,
    GenerationJobStore,
    InMemoryGenerationJobStore,
    PostgresGenerationJobStore,
    enqueue_generation_job,
    generation_job_policy_summary,
    redacted_request_summary,
)
from dessert_ad_studio.marketing_context import (
    KeywordMarketingContextRetriever,
    MarketingContextRetriever,
)
from dessert_ad_studio.marketing_context_pgvector import (
    PgvectorHybridMarketingContextRetriever,
)
from dessert_ad_studio.observability import build_workflow_tracer
from dessert_ad_studio.privacy import redacted_image_path, redacted_reference_image_name
from dessert_ad_studio.product_analysis import (
    MockProductAnalyzer,
    OpenAIProductAnalyzer,
    ProductAnalyzer,
)
from dessert_ad_studio.reference_image import ReferenceImageError, decode_reference_image
from dessert_ad_studio.schemas import (
    GenerationRequest,
    GenerationResponse,
    MarketingContext,
    ProductAnalysis,
)
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
_A2A_TASKS = A2ATaskStore()


class _BestEffortGenerationLogger:
    def __init__(self, log_path: str | Path) -> None:
        from dessert_ad_studio.generation_logger import GenerationLogger

        self._logger = GenerationLogger(log_path)

    def write(self, record: dict[str, Any]) -> None:
        try:
            self._logger.write(record)
        except OSError:
            pass


class _WorkflowGenerationTelemetry:
    def __init__(self) -> None:
        self.started = perf_counter()
        self.ranking = None
        self.copy_result = None
        self.marketing_context: MarketingContext | None = None


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

    def generate_copy(
        self,
        request: GenerationRequest,
        *,
        product_analysis: ProductAnalysis | None = None,
        marketing_context: MarketingContext | None = None,
    ):
        result = self._backend.generate_copy(
            request,
            product_analysis=product_analysis,
            marketing_context=marketing_context,
        )
        self._telemetry.copy_result = result
        self._telemetry.marketing_context = marketing_context
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
        marketing_context = self._telemetry.marketing_context
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
            "marketing_context_backend": (
                marketing_context.retriever_backend if marketing_context is not None else None
            ),
            "marketing_context_retrieved_docs_count": (
                marketing_context.retrieved_docs_count if marketing_context is not None else None
            ),
            "marketing_context_categories": (
                list(marketing_context.guide_categories) if marketing_context is not None else []
            ),
            "used_reference": reference_image is not None,
            **redacted_reference_image_name(request.reference_image_name),
            "copy_usage": copy_result.usage,
            "image_usage": None,
            **redacted_image_path(None),
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


def _request_metric_path(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str) and route_path:
        return route_path
    return "__unmatched__"


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


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


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
            path=_request_metric_path(request),
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
    if name == "openai":
        return OpenAIProductAnalyzer()
    return None


@lru_cache(maxsize=None)
def _marketing_context_retriever_for(
    name: str,
    pgvector_dsn: str,
) -> MarketingContextRetriever | None:
    if name == "keyword":
        return KeywordMarketingContextRetriever()
    if name == "pgvector_hybrid":
        return PgvectorHybridMarketingContextRetriever(dsn=pgvector_dsn or None)
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


def get_marketing_context_retriever() -> MarketingContextRetriever:
    name = os.getenv("MARKETING_CONTEXT_BACKEND", "keyword")
    try:
        retriever = _marketing_context_retriever_for(name, os.getenv("PGVECTOR_DSN", ""))
    except RuntimeError as exc:
        if not _is_marketing_context_dependency_error(exc):
            raise
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if retriever is None:
        raise HTTPException(
            status_code=501,
            detail=f"unknown marketing context backend: {name}",
        )
    return retriever


def _is_marketing_context_dependency_error(exc: RuntimeError) -> bool:
    detail = str(exc)
    return detail.startswith(
        (
            "pgvector_hybrid retriever is not ready",
            "psycopg is required for pgvector_hybrid retriever",
        )
    )


@lru_cache(maxsize=None)
def get_generation_job_store() -> GenerationJobStore:
    backend = os.getenv("GENERATION_HISTORY_BACKEND", "").strip().lower()
    dsn = os.getenv("GENERATION_HISTORY_DSN", "")
    if not backend:
        backend = "postgres" if dsn else "memory"

    try:
        if backend == "memory":
            return InMemoryGenerationJobStore()
        if backend == "postgres":
            return PostgresGenerationJobStore(dsn)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    raise HTTPException(status_code=501, detail=f"unknown generation history backend: {backend}")


def build_workflow_dependencies(request: GenerationRequest) -> GenerationWorkflowDependencies:
    telemetry = _WorkflowGenerationTelemetry()
    copy_backend = _RecordingCopyBackend(get_copy_backend(), telemetry)
    image_backend = get_image_backend()

    reference_image = decode_reference_image(request.reference_image_b64)
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
    return GenerationWorkflowDependencies(
        template_scorer=_ApiTemplateRankingScorer(telemetry),
        copy_backend=copy_backend,
        image_backend=_FailureLoggingImageBackend(
            image_backend,
            telemetry=telemetry,
            copy_backend=copy_backend,
            product_analysis_backend=product_analyzer.name,
            log_path=log_path,
        ),
        product_analyzer=product_analyzer,
        marketing_context_retriever=get_marketing_context_retriever(),
        log_path=log_path,
        logger_factory=_BestEffortGenerationLogger,
        workflow_tracer=build_workflow_tracer(),
    )


def _agentic_rag_requires_paid_provider(dependencies: GenerationWorkflowDependencies) -> bool:
    backend_names = {
        dependencies.copy_backend.name,
        dependencies.image_backend.name,
        dependencies.product_analyzer.name,
    }
    return any(name != "mock" for name in backend_names)


async def _agentic_rag_sse_events(
    request: GenerationRequest,
    dependencies: GenerationWorkflowDependencies,
) -> AsyncIterator[str]:
    requires_paid_provider = _agentic_rag_requires_paid_provider(dependencies)
    graph = build_agentic_rag_graph(
        worker_executor=build_generation_workflow_executor(request, dependencies),
    )
    state = build_agentic_rag_initial_state(
        request,
        requires_paid_provider=requires_paid_provider,
        estimated_cost_usd=0.0,
        approval_cost_threshold_usd=0.0,
    )

    yield _sse_event(
        "run_started",
        {
            "status": "started",
            "stream_protocol": "sse",
            "raw_inputs_committed": False,
        },
    )
    final_status = "started"
    final_next_action = None
    for chunk in graph.stream(state, stream_mode="updates"):
        for node_name, update in chunk.items():
            payload = _agentic_rag_stream_update(node_name, update)
            final_status = payload.get("status", final_status)
            final_next_action = payload.get("next_action", final_next_action)
            yield _sse_event("node_completed", payload)
            await asyncio.sleep(0)

    run_completed = {
        "status": final_status,
        "raw_inputs_committed": False,
    }
    if final_next_action is not None:
        run_completed["next_action"] = final_next_action
    yield _sse_event("run_completed", run_completed)


def _agentic_rag_stream_update(node_name: str, update: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {"node": node_name}
    if "status" in update:
        payload["status"] = update["status"]
    if "next_action" in update:
        payload["next_action"] = update["next_action"]

    approval = update.get("approval")
    if isinstance(approval, dict):
        payload["approval_required"] = approval.get("required", False)
        payload["approval_reasons"] = list(approval.get("reasons", []))

    marketing_context = update.get("marketing_context")
    if isinstance(marketing_context, dict):
        payload["retriever_backend"] = marketing_context.get("retriever_backend")
        payload["retrieved_docs_count"] = marketing_context.get("retrieved_docs_count")

    citations = update.get("citations")
    if isinstance(citations, list):
        payload["citation_count"] = len(citations)

    worker_result = update.get("worker_result")
    if isinstance(worker_result, dict):
        payload["worker_status"] = worker_result.get("status")
        for key in (
            "copy_backend",
            "image_backend",
            "copy_option_count",
            "used_reference",
            "workflow_trace_steps",
        ):
            if key in worker_result:
                payload[key] = worker_result[key]

    reflection = update.get("reflection")
    if isinstance(reflection, dict):
        payload["reflection"] = {
            "attempts": reflection.get("attempts"),
            "last_error_type": reflection.get("last_error_type"),
            "retry_budget": reflection.get("retry_budget"),
        }
    return payload


def _sse_event(event_name: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return f"event: {event_name}\ndata: {payload}\n\n"


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
        marketing_context_retriever = get_marketing_context_retriever()
        generation_job_store = get_generation_job_store()
        template_scorer = get_template_scorer()
        if isinstance(template_scorer, TritonTemplateScorer) and not _is_triton_ready(
            template_scorer.url
        ):
            raise HTTPException(status_code=503, detail="triton template_scorer is not ready")
    except (HTTPException, AdBackendError) as exc:
        detail = getattr(exc, "detail", str(exc))
        raise HTTPException(status_code=503, detail=f"not ready: {detail}") from exc

    return {
        "status": "ready",
        "copy_backend": copy_backend.name,
        "image_backend": image_backend.name,
        "product_analysis_backend": product_analyzer.name,
        "marketing_context_backend": marketing_context_retriever.name,
        "generation_history_backend": generation_job_store.name,
        "generation_queue_backend": os.getenv("GENERATION_QUEUE_BACKEND", "inline"),
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
            lines.append(
                f"dessert_ad_studio_http_request_latency_seconds_total{labels} {total:.6f}"
            )

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
    try:
        dependencies = build_workflow_dependencies(request)
        return run_generation_workflow(request, dependencies).response
    except ReferenceImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AdBackendError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        if not _is_marketing_context_dependency_error(exc):
            raise
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/agentic-rag/runs/stream")
async def stream_agentic_rag_run(request: GenerationRequest) -> StreamingResponse:
    try:
        dependencies = build_workflow_dependencies(request)
    except ReferenceImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AdBackendError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        if not _is_marketing_context_dependency_error(exc):
            raise
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return StreamingResponse(
        _agentic_rag_sse_events(request, dependencies),
        media_type="text/event-stream",
    )


@app.post("/generation-jobs", status_code=202)
def create_generation_job(request: GenerationRequest) -> dict[str, Any]:
    if request.reference_image_b64:
        raise HTTPException(
            status_code=400,
            detail=(
                "비동기 생성 작업은 아직 참고 이미지를 지원하지 않습니다. "
                "참고 이미지는 동기 /generate 경로를 사용해주세요."
            ),
        )

    queue_backend = os.getenv("GENERATION_QUEUE_BACKEND", "inline").strip().lower()
    store = get_generation_job_store()
    job_id = f"gen-{uuid4()}"
    store.create_job(
        job_id,
        redacted_request_summary(request),
        queue_backend=queue_backend,
    )

    try:
        queue_job_id = enqueue_generation_job(
            job_id=job_id,
            request=request,
            queue_backend=queue_backend,
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            queue_name=os.getenv("GENERATION_QUEUE_NAME", "ad-generation"),
            result_ttl_seconds=_int_env("GENERATION_JOB_RESULT_TTL_SECONDS", 3600),
            failure_ttl_seconds=_int_env("GENERATION_JOB_FAILURE_TTL_SECONDS", 86400),
        )
    except GenerationJobQueueError as exc:
        store.mark_failed(job_id, str(exc))
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if queue_job_id:
        store.set_queue_job_id(job_id, queue_job_id)
    record = store.get_job(job_id)
    status = record.status if record is not None else "queued"
    return {
        "job_id": job_id,
        "status": status,
        "status_url": f"/generation-jobs/{job_id}",
        "queue_backend": queue_backend,
    }


@app.get("/generation-jobs/policy")
def get_generation_job_policy() -> dict[str, Any]:
    return generation_job_policy_summary()


@app.post("/generation-jobs/{job_id}/cancel")
def cancel_generation_job(job_id: str) -> dict[str, Any]:
    raise HTTPException(status_code=501, detail=GENERATION_JOB_CANCEL_UNSUPPORTED_DETAIL)


@app.get("/generation-jobs/{job_id}")
def get_generation_job(job_id: str) -> dict[str, Any]:
    record = get_generation_job_store().get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="generation job not found")
    return record.to_status_response()


@app.get("/.well-known/agent-card.json")
def a2a_agent_card(request: Request) -> dict[str, Any]:
    return build_agent_card(base_url=str(request.base_url).rstrip("/"))


@app.post("/message:send")
def a2a_send_message(payload: dict[str, Any]) -> dict[str, Any]:
    message = payload.get("message")
    if not isinstance(message, dict):
        raise HTTPException(status_code=400, detail="A2A request must include message")

    try:
        generation_request = extract_generation_request(message)
        dependencies = build_workflow_dependencies(generation_request)
        output = run_generation_workflow(generation_request, dependencies)
    except A2AInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ReferenceImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AdBackendError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        if not _is_marketing_context_dependency_error(exc):
            raise
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    task = completed_generation_task(
        output.response,
        message_id=message.get("messageId"),
        context_id=message.get("contextId"),
    )
    _A2A_TASKS.save(task)
    return {"task": task}


@app.get("/tasks/{task_id}")
def a2a_get_task(task_id: str) -> dict[str, Any]:
    task = _A2A_TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="A2A task not found")
    return task
