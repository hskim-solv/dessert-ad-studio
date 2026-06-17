from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Protocol

from dessert_ad_studio.backends.base import CopyBackend, ImageBackend
from dessert_ad_studio.generation_logger import GenerationLogger
from dessert_ad_studio.marketing_context import (
    KeywordMarketingContextRetriever,
    MarketingContextRetriever,
)
from dessert_ad_studio.observability import NoopWorkflowTracer, WorkflowTracer
from dessert_ad_studio.privacy import (
    redacted_image_path,
    redacted_log_path,
    redacted_reference_image_name,
)
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
    marketing_context_retriever: MarketingContextRetriever = field(
        default_factory=KeywordMarketingContextRetriever
    )
    logger_factory: LoggerFactory = GenerationLogger
    workflow_tracer: WorkflowTracer = field(default_factory=NoopWorkflowTracer)


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
    tracer = dependencies.workflow_tracer

    with tracer.span(
        "generation_workflow",
        "agent",
        {
            "campaign_purpose": request.campaign_purpose,
            "tone": request.tone,
            "template_hint": request.template_hint,
            "has_reference_image": request.reference_image_b64 is not None,
        },
    ) as workflow_span:
        with tracer.span("rank_templates", "reranker") as span:
            step_started = perf_counter()
            ranking = dependencies.template_scorer.rank(request)
            metadata = {
                "template": ranking.template_name,
                "template_scorer": ranking.scorer,
                "triton_latency_ms": ranking.latency_ms,
            }
            span.set_attributes(metadata)
            _append_trace(trace, "rank_templates", step_started, metadata)

        with tracer.span("decode_reference", "tool") as span:
            step_started = perf_counter()
            reference_image = decode_reference_image(request.reference_image_b64)
            used_reference = reference_image is not None
            metadata = {
                "used_reference": used_reference,
                **redacted_reference_image_name(request.reference_image_name),
            }
            span.set_attributes(metadata)
            _append_trace(trace, "decode_reference", step_started, metadata)

        with tracer.span("analyze_product", "llm") as span:
            step_started = perf_counter()
            product_analysis = dependencies.product_analyzer.analyze(
                request,
                reference_image=reference_image,
            )
            metadata = {"product_analysis_backend": dependencies.product_analyzer.name}
            span.set_attributes(metadata)
            _append_trace(trace, "analyze_product", step_started, metadata)

        with tracer.span("retrieve_marketing_context", "retriever") as span:
            step_started = perf_counter()
            marketing_context = dependencies.marketing_context_retriever.retrieve(
                request,
                product_analysis,
            )
            metadata = {
                "marketing_context_backend": marketing_context.retriever_backend,
                "retrieved_docs_count": marketing_context.retrieved_docs_count,
                "guide_categories": list(marketing_context.guide_categories),
            }
            span.set_attributes(metadata)
            _append_trace(trace, "retrieve_marketing_context", step_started, metadata)

        with tracer.span("build_image_prompt", "prompt") as span:
            step_started = perf_counter()
            image_prompt = build_image_prompt(
                request,
                ranked_template=ranking.template_name,
                has_reference=used_reference,
                product_analysis=product_analysis,
            )
            metadata = {
                "prompt_length": len(image_prompt),
                "has_reference": used_reference,
                "product_analysis_backend": dependencies.product_analyzer.name,
                "has_selling_points": bool(product_analysis.selling_points),
                "selling_points_count": len(product_analysis.selling_points),
            }
            span.set_attributes(
                {
                    "prompt_length": len(image_prompt),
                    "used_reference": used_reference,
                    "product_analysis_backend": dependencies.product_analyzer.name,
                    "has_selling_points": bool(product_analysis.selling_points),
                    "selling_points_count": len(product_analysis.selling_points),
                }
            )
            _append_trace(trace, "build_image_prompt", step_started, metadata)

        with tracer.span("generate_copy", "llm") as span:
            step_started = perf_counter()
            copy_result = dependencies.copy_backend.generate_copy(
                request,
                product_analysis=product_analysis,
                marketing_context=marketing_context,
            )
            metadata = {
                "copy_backend": dependencies.copy_backend.name,
                "copy_model_id": getattr(dependencies.copy_backend, "model_id", None),
                "option_count": len(copy_result.options),
                "copy_usage": copy_result.usage,
            }
            span.set_attributes(metadata)
            _append_trace(trace, "generate_copy", step_started, metadata)

        with tracer.span("generate_image", "tool") as span:
            step_started = perf_counter()
            image_result = dependencies.image_backend.generate_image(
                request,
                image_prompt=image_prompt,
                reference_image=reference_image,
            )
            metadata = {
                "image_backend": dependencies.image_backend.name,
                "image_model_id": getattr(dependencies.image_backend, "model_id", None),
                **redacted_image_path(image_result.path),
                "image_usage": image_result.usage,
            }
            span.set_attributes(metadata)
            _append_trace(trace, "generate_image", step_started, metadata)

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
            marketing_context=marketing_context,
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
            "marketing_context_backend": marketing_context.retriever_backend,
            "marketing_context_retrieved_docs_count": marketing_context.retrieved_docs_count,
            "marketing_context_categories": list(marketing_context.guide_categories),
            "used_reference": used_reference,
            **redacted_reference_image_name(request.reference_image_name),
            "copy_usage": copy_result.usage,
            "image_usage": image_result.usage,
            "elapsed_ms": elapsed_ms,
            **redacted_image_path(image_result.path),
            "workflow_trace": _trace_payload(trace),
        }
        with tracer.span("write_log", "tool") as span:
            step_started = perf_counter()
            dependencies.logger_factory(dependencies.log_path).write(log_record)
            metadata = redacted_log_path(str(dependencies.log_path))
            span.set_attributes(metadata)
            trace.append(
                WorkflowTraceEntry(
                    step="write_log",
                    elapsed_ms=_elapsed_ms(step_started),
                    metadata=metadata,
                )
            )

        workflow_span.set_attributes(
            {
                "copy_backend": dependencies.copy_backend.name,
                "image_backend": dependencies.image_backend.name,
                "product_analysis_backend": dependencies.product_analyzer.name,
                "marketing_context_backend": marketing_context.retriever_backend,
                "marketing_context_retrieved_docs_count": marketing_context.retrieved_docs_count,
                "prompt_length": len(image_prompt),
                "used_reference": used_reference,
                "elapsed_ms": elapsed_ms,
                **redacted_image_path(image_result.path),
                **redacted_log_path(str(dependencies.log_path)),
            }
        )

        return GenerationWorkflowOutput(response=response, trace=trace)
