import json
from pathlib import Path

import pytest

from dessert_ad_studio.observability import (
    InMemoryWorkflowTracer,
    OpenInferenceWorkflowTracer,
    build_openinference_attributes,
    build_workflow_tracer,
    resolve_otlp_trace_endpoint,
)


def test_in_memory_tracer_records_start_order_and_attributes() -> None:
    tracer = InMemoryWorkflowTracer()

    with tracer.span("generation_workflow", "agent", {"campaign_purpose": "new_menu"}) as root:
        root.set_attribute("copy_backend", "mock")
        with tracer.span("generate_copy", "llm", {"copy_backend": "mock"}) as child:
            child.set_attribute("option_count", 3)

    records = tracer.records()
    assert [record.name for record in records] == ["generation_workflow", "generate_copy"]
    assert records[0].attributes["openinference.span.kind"] == "AGENT"
    assert records[1].attributes["openinference.span.kind"] == "LLM"
    assert records[1].attributes["option_count"] == 3
    assert records[0].elapsed_ms >= 0


def test_openinference_attribute_builder_uses_stable_keys() -> None:
    attributes = build_openinference_attributes("tool", {"nested": {"a": 1}, "none": None})

    assert attributes["openinference.span.kind"] == "TOOL"
    assert attributes["nested"] == '{"a": 1}'
    assert "none" not in attributes


def test_openinference_attribute_builder_handles_nested_non_json_values() -> None:
    attributes = build_openinference_attributes(
        "tool",
        {
            "nested": {
                1: Path("outputs/example.png"),
                "items": [Path("assets/reference.png"), {"path": Path("logs/run.jsonl")}],
            },
        },
    )

    assert json.loads(attributes["nested"]) == {
        "1": "outputs/example.png",
        "items": ["assets/reference.png", {"path": "logs/run.jsonl"}],
    }


def test_openinference_tracer_exports_to_in_memory_span_exporter() -> None:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    workflow_tracer = OpenInferenceWorkflowTracer(
        tracer=provider.get_tracer("dessert-ad-studio-test")
    )

    with workflow_tracer.span("generate_image", "tool", {"image_backend": "mock"}) as span:
        span.set_attribute("image_path", "outputs/example.png")

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "generate_image"
    assert spans[0].attributes["openinference.span.kind"] == "TOOL"
    assert spans[0].attributes["image_backend"] == "mock"
    assert spans[0].attributes["image_path"] == "outputs/example.png"


def test_resolve_otlp_trace_endpoint_prefers_trace_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector:4318/custom")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")

    assert resolve_otlp_trace_endpoint() == "http://collector:4318/custom"


def test_resolve_otlp_trace_endpoint_appends_trace_path_to_base_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")

    assert resolve_otlp_trace_endpoint() == "http://collector:4318/v1/traces"


def test_resolve_otlp_trace_endpoint_defaults_to_local_phoenix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    assert resolve_otlp_trace_endpoint() == "http://localhost:6006/v1/traces"


def test_build_workflow_tracer_supports_otlp_export(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKFLOW_TRACE_EXPORT", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector:4318/v1/traces")

    tracer = build_workflow_tracer("otel")

    assert isinstance(tracer, OpenInferenceWorkflowTracer)


def test_build_workflow_tracer_rejects_unknown_export(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKFLOW_TRACE_EXPORT", "zipkin")

    with pytest.raises(ValueError, match="unsupported workflow trace export"):
        build_workflow_tracer("otel")
