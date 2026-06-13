from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Protocol

from dessert_ad_studio.backends.base import CopyBackend, ImageBackend
from dessert_ad_studio.generation_logger import GenerationLogger
from dessert_ad_studio.product_analysis import ProductAnalyzer
from dessert_ad_studio.prompts import build_image_prompt
from dessert_ad_studio.reference_image import decode_reference_image
from dessert_ad_studio.schemas import GenerationRequest, GenerationResponse, TemplateRanking


class TemplateScorer(Protocol):
    def rank(self, request: GenerationRequest) -> TemplateRanking: ...


class WorkflowLogger(Protocol):
    def write(self, record: dict[str, Any]) -> None: ...


LoggerFactory = Callable[[str | Path], WorkflowLogger]


@dataclass(frozen=True)
class WorkflowTraceEntry:
    step: str
    elapsed_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationWorkflowDependencies:
    template_scorer: TemplateScorer
    copy_backend: CopyBackend
    image_backend: ImageBackend
    product_analyzer: ProductAnalyzer
    log_path: str | Path
    logger_factory: LoggerFactory = GenerationLogger


@dataclass(frozen=True)
class GenerationWorkflowOutput:
    response: GenerationResponse
    trace: list[WorkflowTraceEntry]


def _elapsed_ms(started: float) -> float:
    return (perf_counter() - started) * 1000


def _append_trace(
    trace: list[WorkflowTraceEntry],
    step: str,
    started: float,
    metadata: dict[str, Any] | None = None,
) -> None:
    trace.append(
        WorkflowTraceEntry(
            step=step,
            elapsed_ms=_elapsed_ms(started),
            metadata=metadata or {},
        )
    )


def _trace_payload(trace: list[WorkflowTraceEntry]) -> list[dict[str, Any]]:
    return [asdict(entry) for entry in trace]


def run_generation_workflow(
    request: GenerationRequest,
    dependencies: GenerationWorkflowDependencies,
) -> GenerationWorkflowOutput:
    started = perf_counter()
    trace: list[WorkflowTraceEntry] = []

    step_started = perf_counter()
    ranking = dependencies.template_scorer.rank(request)
    _append_trace(
        trace,
        "rank_templates",
        step_started,
        {
            "template": ranking.template_name,
            "template_scorer": ranking.scorer,
            "triton_latency_ms": ranking.latency_ms,
        },
    )

    step_started = perf_counter()
    reference_image = decode_reference_image(request.reference_image_b64)
    used_reference = reference_image is not None
    _append_trace(
        trace,
        "decode_reference",
        step_started,
        {
            "used_reference": used_reference,
            "reference_image_name": request.reference_image_name,
        },
    )

    step_started = perf_counter()
    product_analysis = dependencies.product_analyzer.analyze(
        request,
        reference_image=reference_image,
    )
    _append_trace(
        trace,
        "analyze_product",
        step_started,
        {"product_analysis_backend": dependencies.product_analyzer.name},
    )

    step_started = perf_counter()
    image_prompt = build_image_prompt(
        request,
        ranked_template=ranking.template_name,
        has_reference=used_reference,
    )
    _append_trace(
        trace,
        "build_image_prompt",
        step_started,
        {"prompt_length": len(image_prompt), "has_reference": used_reference},
    )

    step_started = perf_counter()
    copy_result = dependencies.copy_backend.generate_copy(request)
    _append_trace(
        trace,
        "generate_copy",
        step_started,
        {
            "copy_backend": dependencies.copy_backend.name,
            "copy_model_id": getattr(dependencies.copy_backend, "model_id", None),
            "option_count": len(copy_result.options),
            "copy_usage": copy_result.usage,
        },
    )

    step_started = perf_counter()
    image_result = dependencies.image_backend.generate_image(
        request,
        image_prompt=image_prompt,
        reference_image=reference_image,
    )
    _append_trace(
        trace,
        "generate_image",
        step_started,
        {
            "image_backend": dependencies.image_backend.name,
            "image_model_id": getattr(dependencies.image_backend, "model_id", None),
            "image_path": image_result.path,
            "image_usage": image_result.usage,
        },
    )

    elapsed_ms = _elapsed_ms(started)
    response = GenerationResponse(
        copy_options=copy_result.options,
        selected_template=ranking,
        image_path=image_result.path,
        image_backend=dependencies.image_backend.name,
        copy_backend=dependencies.copy_backend.name,
        used_reference=used_reference,
        prompt_summary=image_prompt,
        elapsed_ms=elapsed_ms,
        product_analysis=product_analysis,
    )

    log_record = {
        "campaign_purpose": request.campaign_purpose,
        "template": ranking.template_name,
        "template_scorer": ranking.scorer,
        "triton_latency_ms": ranking.latency_ms,
        "copy_backend": dependencies.copy_backend.name,
        "copy_model_id": getattr(dependencies.copy_backend, "model_id", None),
        "image_backend": dependencies.image_backend.name,
        "image_model_id": getattr(dependencies.image_backend, "model_id", None),
        "product_analysis_backend": dependencies.product_analyzer.name,
        "used_reference": used_reference,
        "reference_image_name": request.reference_image_name,
        "copy_usage": copy_result.usage,
        "image_usage": image_result.usage,
        "elapsed_ms": elapsed_ms,
        "image_path": image_result.path,
        "workflow_trace": _trace_payload(trace),
    }
    step_started = perf_counter()
    dependencies.logger_factory(dependencies.log_path).write(log_record)
    trace.append(
        WorkflowTraceEntry(
            step="write_log",
            elapsed_ms=_elapsed_ms(step_started),
            metadata={"log_path": str(dependencies.log_path)},
        )
    )

    return GenerationWorkflowOutput(response=response, trace=trace)
