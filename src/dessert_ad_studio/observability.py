from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
import importlib.util
import json
import os
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any, ContextManager, Protocol

OPENINFERENCE_SPAN_KIND = "openinference.span.kind"

_SPAN_KIND_VALUES = {
    "tool": "TOOL",
    "chain": "CHAIN",
    "llm": "LLM",
    "retriever": "RETRIEVER",
    "embedding": "EMBEDDING",
    "agent": "AGENT",
    "reranker": "RERANKER",
    "unknown": "UNKNOWN",
    "guardrail": "GUARDRAIL",
    "evaluator": "EVALUATOR",
    "prompt": "PROMPT",
}

_DISABLED_MODES = {"none", "off", "false", "0"}
_OTEL_MISSING_MESSAGE = (
    "WORKFLOW_TRACING=otel requires opentelemetry-api, opentelemetry-sdk, and "
    "openinference-semantic-conventions. Install project dependencies with "
    "`.venv/bin/pip install -e \".[dev]\"`."
)
_OTLP_HTTP_MISSING_MESSAGE = (
    "WORKFLOW_TRACE_EXPORT=otlp requires opentelemetry-exporter-otlp-proto-http. "
    "Install project dependencies with `.venv/bin/pip install -e \".[dev]\"`."
)


def resolve_otlp_trace_endpoint() -> str:
    trace_endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    if trace_endpoint:
        return trace_endpoint

    base_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not base_endpoint:
        return "http://localhost:6006/v1/traces"
    return _append_otlp_trace_path(base_endpoint)


def _append_otlp_trace_path(endpoint: str) -> str:
    normalized = endpoint.rstrip("/")
    if normalized.endswith("/v1/traces"):
        return normalized
    return f"{normalized}/v1/traces"


@dataclass(frozen=True)
class WorkflowSpanRecord:
    name: str
    kind: str
    attributes: dict[str, Any]
    elapsed_ms: float
    error_type: str | None = None


class ActiveWorkflowSpan(Protocol):
    def set_attribute(self, key: str, value: Any) -> None: ...
    def set_attributes(self, attributes: Mapping[str, Any]) -> None: ...


class WorkflowTracer(Protocol):
    def span(
        self,
        name: str,
        kind: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> ContextManager[ActiveWorkflowSpan]: ...


def build_openinference_attributes(
    kind: str,
    attributes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    span_kind = _normalize_span_kind(kind)
    normalized: dict[str, Any] = {OPENINFERENCE_SPAN_KIND: span_kind}
    for key, value in (attributes or {}).items():
        if value is None:
            continue
        normalized[key] = _normalize_attribute_value(value)
    return normalized


def _normalize_span_kind(kind: str) -> str:
    span_kind = _SPAN_KIND_VALUES.get(kind.lower())
    if span_kind is None:
        raise ValueError(f"unknown OpenInference span kind: {kind}")
    return span_kind


def _normalize_attribute_value(value: Any) -> Any:
    if isinstance(value, str | bool | int | float):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping | list | tuple):
        return json.dumps(_normalize_json_value(value), ensure_ascii=False, sort_keys=True)
    return str(value)


def _normalize_json_value(value: Any) -> Any:
    if value is None or isinstance(value, str | bool | int | float):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_json_value(nested_value)
            for key, nested_value in value.items()
        }
    if isinstance(value, list | tuple):
        return [_normalize_json_value(nested_value) for nested_value in value]
    return str(value)


class _NoopActiveWorkflowSpan:
    def set_attribute(self, key: str, value: Any) -> None:
        return None

    def set_attributes(self, attributes: Mapping[str, Any]) -> None:
        return None


class NoopWorkflowTracer:
    @contextmanager
    def span(
        self,
        name: str,
        kind: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[ActiveWorkflowSpan]:
        yield _NoopActiveWorkflowSpan()


class _InMemoryActiveWorkflowSpan:
    def __init__(self, attributes: dict[str, Any]) -> None:
        self.attributes = attributes

    def set_attribute(self, key: str, value: Any) -> None:
        if value is not None:
            self.attributes[key] = _normalize_attribute_value(value)

    def set_attributes(self, attributes: Mapping[str, Any]) -> None:
        for key, value in attributes.items():
            self.set_attribute(key, value)


class InMemoryWorkflowTracer:
    def __init__(self) -> None:
        self._records: list[WorkflowSpanRecord] = []
        self._lock = Lock()

    @contextmanager
    def span(
        self,
        name: str,
        kind: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[ActiveWorkflowSpan]:
        started = perf_counter()
        span_kind = _normalize_span_kind(kind)
        span_attributes = build_openinference_attributes(kind, attributes)
        active_span = _InMemoryActiveWorkflowSpan(span_attributes)
        index = self._append_record(
            WorkflowSpanRecord(
                name=name,
                kind=span_kind,
                attributes=dict(active_span.attributes),
                elapsed_ms=0.0,
            )
        )
        error_type: str | None = None
        try:
            yield active_span
        except Exception as exc:
            error_type = type(exc).__name__
            active_span.set_attribute("error.type", error_type)
            raise
        finally:
            elapsed_ms = (perf_counter() - started) * 1000
            self._replace_record(
                index,
                WorkflowSpanRecord(
                    name=name,
                    kind=span_kind,
                    attributes=dict(active_span.attributes),
                    elapsed_ms=elapsed_ms,
                    error_type=error_type,
                ),
            )

    def records(self) -> list[WorkflowSpanRecord]:
        with self._lock:
            return [replace(record, attributes=dict(record.attributes)) for record in self._records]

    def _append_record(self, record: WorkflowSpanRecord) -> int:
        with self._lock:
            index = len(self._records)
            self._records.append(record)
            return index

    def _replace_record(self, index: int, record: WorkflowSpanRecord) -> None:
        with self._lock:
            self._records[index] = record


class _OpenTelemetryActiveWorkflowSpan:
    def __init__(self, span: Any) -> None:
        self._span = span

    def set_attribute(self, key: str, value: Any) -> None:
        if value is not None:
            self._span.set_attribute(key, _normalize_attribute_value(value))

    def set_attributes(self, attributes: Mapping[str, Any]) -> None:
        for key, value in attributes.items():
            self.set_attribute(key, value)


class OpenInferenceWorkflowTracer:
    def __init__(self, tracer: Any) -> None:
        self._tracer = tracer

    @contextmanager
    def span(
        self,
        name: str,
        kind: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[ActiveWorkflowSpan]:
        span_attributes = build_openinference_attributes(kind, attributes)
        with self._tracer.start_as_current_span(name, attributes=span_attributes) as span:
            active_span = _OpenTelemetryActiveWorkflowSpan(span)
            try:
                yield active_span
            except Exception as exc:
                active_span.set_attribute("error.type", type(exc).__name__)
                raise


def build_workflow_tracer(mode: str | None = None) -> WorkflowTracer:
    selected_mode = (mode if mode is not None else os.getenv("WORKFLOW_TRACING", "none")).strip()
    normalized_mode = selected_mode.lower()
    if normalized_mode in _DISABLED_MODES:
        return NoopWorkflowTracer()
    if normalized_mode == "memory":
        return InMemoryWorkflowTracer()
    if normalized_mode == "otel":
        return _build_otel_workflow_tracer()
    raise ValueError(
        f"unsupported workflow tracing mode: {selected_mode!r}; expected none, memory, or otel"
    )


def _build_otel_workflow_tracer() -> OpenInferenceWorkflowTracer:
    if not _has_module("opentelemetry") or not _has_module("opentelemetry.sdk"):
        raise RuntimeError(_OTEL_MISSING_MESSAGE)
    if not _has_module("openinference") or not _has_module("openinference.semconv"):
        raise RuntimeError(_OTEL_MISSING_MESSAGE)

    try:
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
    except ImportError as exc:
        raise RuntimeError(_OTEL_MISSING_MESSAGE) from exc

    provider = TracerProvider(
        resource=Resource.create(
            {"service.name": os.getenv("OTEL_SERVICE_NAME", "dessert-ad-studio")}
        )
    )
    trace_export = os.getenv("WORKFLOW_TRACE_EXPORT", "console").strip().lower()
    if trace_export == "console":
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    elif trace_export == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        except ImportError as exc:
            raise RuntimeError(_OTLP_HTTP_MISSING_MESSAGE) from exc
        provider.add_span_processor(
            SimpleSpanProcessor(OTLPSpanExporter(endpoint=resolve_otlp_trace_endpoint()))
        )
    elif trace_export not in _DISABLED_MODES:
        raise ValueError(
            f"unsupported workflow trace export: {trace_export!r}; expected console, otlp, or none"
        )
    return OpenInferenceWorkflowTracer(provider.get_tracer("dessert_ad_studio.workflow"))


def _has_module(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False
