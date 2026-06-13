# Workflow Observability and Eval Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local AgentOps evidence by tracing the existing generation workflow with OpenTelemetry/OpenInference-compatible spans and adding a deterministic demo eval harness.

**Architecture:** Keep `run_generation_workflow()` as the orchestration boundary. Add a focused `observability.py` module with noop, in-memory, and OpenTelemetry-backed tracers, then inject the tracer through `GenerationWorkflowDependencies`. Add `evaluation.py` and a CLI script that run existing demo samples through mock backends and fail on deterministic regressions.

**Tech Stack:** Python 3.11, FastAPI, pytest, OpenTelemetry Python SDK, OpenInference semantic conventions, existing mock backends and demo samples.

---

## File Structure

- Create `src/dessert_ad_studio/observability.py`
  - Owns workflow span protocols, local span records, OpenInference attribute mapping, and tracer factory.
- Modify `src/dessert_ad_studio/workflow.py`
  - Adds `workflow_tracer` dependency and wraps the existing steps in spans.
- Modify `api/main.py`
  - Builds a workflow tracer from environment variables and injects it into workflow dependencies.
- Create `src/dessert_ad_studio/evaluation.py`
  - Owns deterministic generation evaluation checks and summary aggregation.
- Create `scripts/eval_demo_samples.py`
  - Runs `DEMO_SAMPLES` with mock dependencies and prints JSON evidence.
- Modify `pyproject.toml`
  - Adds OpenTelemetry/OpenInference dependencies.
- Modify `README.md`
  - Adds AgentOps evidence commands.
- Create `tests/test_observability.py`
  - Covers span recording, OpenInference attributes, and OpenTelemetry export.
- Modify `tests/test_workflow.py`
  - Verifies injected tracer captures workflow and step spans without changing JSONL trace behavior.
- Create `tests/test_evaluation.py`
  - Covers valid demo scoring and failure reporting.
- Modify `tests/test_api.py`
  - Adds one small API dependency test for `WORKFLOW_TRACING=none` default and tracer factory wiring only if needed.

---

### Task 1: Observability Primitives

**Files:**
- Create: `src/dessert_ad_studio/observability.py`
- Create: `tests/test_observability.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add observability dependencies**

In `pyproject.toml`, add these runtime dependencies after `python-dotenv`:

```toml
  "opentelemetry-api>=1.38",
  "opentelemetry-sdk>=1.38",
  "openinference-semantic-conventions>=0.1.23",
```

- [ ] **Step 2: Install updated dependencies**

Run:

```bash
.venv/bin/pip install -e ".[dev]"
```

Expected: editable install completes without dependency resolution errors.

- [ ] **Step 3: Write failing tests for tracer behavior**

Create `tests/test_observability.py` with tests for:

```python
from dessert_ad_studio.observability import (
    InMemoryWorkflowTracer,
    OpenInferenceWorkflowTracer,
    build_openinference_attributes,
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
```

- [ ] **Step 4: Run the failing observability tests**

Run:

```bash
.venv/bin/pytest tests/test_observability.py -q
```

Expected: fail because `dessert_ad_studio.observability` does not exist yet.

- [ ] **Step 5: Implement observability module**

Create `src/dessert_ad_studio/observability.py` with:

```python
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any, Iterator, Mapping, Protocol

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
    ) -> Iterator[ActiveWorkflowSpan]: ...


def build_openinference_attributes(
    kind: str,
    attributes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    span_kind = _SPAN_KIND_VALUES.get(kind.lower())
    if span_kind is None:
        raise ValueError(f"unknown OpenInference span kind: {kind}")
    normalized: dict[str, Any] = {OPENINFERENCE_SPAN_KIND: span_kind}
    for key, value in (attributes or {}).items():
        if value is None:
            continue
        normalized[key] = _normalize_attribute_value(value)
    return normalized


def _normalize_attribute_value(value: Any) -> Any:
    if isinstance(value, str | bool | int | float):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping | list | tuple):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
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
        active = _InMemoryActiveWorkflowSpan(build_openinference_attributes(kind, attributes))
        with self._lock:
            index = len(self._records)
            self._records.append(
                WorkflowSpanRecord(name=name, kind=kind, attributes=dict(active.attributes), elapsed_ms=0)
            )
        error_type: str | None = None
        try:
            yield active
        except Exception as exc:
            error_type = exc.__class__.__name__
            active.set_attribute("error.type", error_type)
            raise
        finally:
            with self._lock:
                self._records[index] = replace(
                    self._records[index],
                    attributes=dict(active.attributes),
                    elapsed_ms=(perf_counter() - started) * 1000,
                    error_type=error_type,
                )

    def records(self) -> list[WorkflowSpanRecord]:
        with self._lock:
            return list(self._records)


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
    def __init__(self, tracer: Any | None = None) -> None:
        try:
            from opentelemetry import trace
        except ImportError as exc:
            raise RuntimeError("OpenTelemetry dependencies are not installed") from exc
        self._tracer = tracer or trace.get_tracer("dessert_ad_studio.workflow")

    @contextmanager
    def span(
        self,
        name: str,
        kind: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[ActiveWorkflowSpan]:
        span_attributes = build_openinference_attributes(kind, attributes)
        with self._tracer.start_as_current_span(name, attributes=span_attributes) as otel_span:
            active = _OpenTelemetryActiveWorkflowSpan(otel_span)
            try:
                yield active
            except Exception as exc:
                active.set_attribute("error.type", exc.__class__.__name__)
                raise


def build_workflow_tracer(mode: str | None = None) -> WorkflowTracer:
    selected = (mode or os.getenv("WORKFLOW_TRACING", "none")).strip().lower()
    if selected in {"none", "off", "false", "0", ""}:
        return NoopWorkflowTracer()
    if selected == "memory":
        return InMemoryWorkflowTracer()
    if selected == "otel":
        return _build_console_otel_tracer()
    raise ValueError(f"unknown WORKFLOW_TRACING mode: {selected}")


def _build_console_otel_tracer() -> OpenInferenceWorkflowTracer:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
    except ImportError as exc:
        raise RuntimeError("OpenTelemetry dependencies are not installed") from exc

    service_name = os.getenv("OTEL_SERVICE_NAME", "dessert-ad-studio")
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    return OpenInferenceWorkflowTracer(tracer=provider.get_tracer("dessert_ad_studio.workflow"))
```

- [ ] **Step 6: Run observability tests**

Run:

```bash
.venv/bin/pytest tests/test_observability.py -q
```

Expected: all observability tests pass.

- [ ] **Step 7: Commit Task 1**

```bash
git add pyproject.toml src/dessert_ad_studio/observability.py tests/test_observability.py
git commit -m "Add workflow observability primitives"
```

---

### Task 2: Workflow Span Instrumentation

**Files:**
- Modify: `src/dessert_ad_studio/workflow.py`
- Modify: `api/main.py`
- Modify: `tests/test_workflow.py`

- [ ] **Step 1: Write failing workflow tracer test**

Append to `tests/test_workflow.py`:

```python
from dessert_ad_studio.observability import InMemoryWorkflowTracer


def test_workflow_emits_openinference_spans(tmp_path: Path) -> None:
    tracer = InMemoryWorkflowTracer()
    deps = GenerationWorkflowDependencies(
        template_scorer=FakeTemplateScorer(),
        copy_backend=FakeCopyBackend(),
        image_backend=FakeImageBackend(),
        product_analyzer=FakeProductAnalyzer(),
        log_path=tmp_path / "generations.jsonl",
        workflow_tracer=tracer,
    )

    run_generation_workflow(request_payload(), deps)

    records = tracer.records()
    assert [record.name for record in records] == [
        "generation_workflow",
        "rank_templates",
        "decode_reference",
        "analyze_product",
        "build_image_prompt",
        "generate_copy",
        "generate_image",
        "write_log",
    ]
    assert records[0].attributes["openinference.span.kind"] == "AGENT"
    assert records[1].attributes["openinference.span.kind"] == "RERANKER"
    assert records[5].attributes["copy_backend"] == "fake-copy"
    assert records[6].attributes["image_backend"] == "fake-image"
    assert records[-1].attributes["log_path"].endswith("generations.jsonl")
```

- [ ] **Step 2: Run the failing workflow test**

Run:

```bash
.venv/bin/pytest tests/test_workflow.py::test_workflow_emits_openinference_spans -q
```

Expected: fail because `GenerationWorkflowDependencies` has no `workflow_tracer`.

- [ ] **Step 3: Add tracer dependency and span wrappers**

Modify `src/dessert_ad_studio/workflow.py`:

```python
from dessert_ad_studio.observability import NoopWorkflowTracer, WorkflowTracer
```

Add this field to `GenerationWorkflowDependencies`:

```python
    workflow_tracer: WorkflowTracer = field(default_factory=NoopWorkflowTracer)
```

Wrap `run_generation_workflow()` with:

```python
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
        ...
        workflow_span.set_attributes(
            {
                "copy_backend": dependencies.copy_backend.name,
                "image_backend": dependencies.image_backend.name,
                "used_reference": used_reference,
                "elapsed_ms": elapsed_ms,
                "image_path": image_result.path,
            }
        )
```

Wrap each existing step with matching span names and set result attributes before
calling `_append_trace()`.

- [ ] **Step 4: Inject tracer in API dependencies**

Modify `api/main.py`:

```python
from dessert_ad_studio.observability import build_workflow_tracer
```

Pass the tracer in `build_workflow_dependencies()`:

```python
        workflow_tracer=build_workflow_tracer(),
```

- [ ] **Step 5: Run workflow and API tests**

Run:

```bash
.venv/bin/pytest tests/test_workflow.py tests/test_api.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit Task 2**

```bash
git add src/dessert_ad_studio/workflow.py api/main.py tests/test_workflow.py
git commit -m "Trace generation workflow spans"
```

---

### Task 3: Deterministic Evaluation Module

**Files:**
- Create: `src/dessert_ad_studio/evaluation.py`
- Create: `tests/test_evaluation.py`

- [ ] **Step 1: Write failing evaluator tests**

Create `tests/test_evaluation.py` with tests that build a mock workflow output:

```python
from pathlib import Path

from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.evaluation import (
    REQUIRED_WORKFLOW_STEPS,
    evaluate_generation_output,
    summarize_eval_results,
)
from dessert_ad_studio.product_analysis import MockProductAnalyzer
from dessert_ad_studio.schemas import GenerationRequest
from dessert_ad_studio.triton import LocalTemplateScorer
from dessert_ad_studio.workflow import GenerationWorkflowDependencies, run_generation_workflow


def sample_request() -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="new_menu",
        product_name="말차 푸딩",
        tone="clean",
        template_hint="minimal_premium",
        price_text="5,500원",
        user_constraints="깔끔한 프리미엄 느낌",
    )


def mock_output(tmp_path: Path):
    backend = MockAdBackend(output_dir=tmp_path)
    return run_generation_workflow(
        sample_request(),
        GenerationWorkflowDependencies(
            template_scorer=LocalTemplateScorer(),
            copy_backend=backend,
            image_backend=backend,
            product_analyzer=MockProductAnalyzer(),
            log_path=tmp_path / "generations.jsonl",
        ),
    )


def test_evaluate_generation_output_scores_valid_mock_generation(tmp_path: Path) -> None:
    result = evaluate_generation_output("sample", sample_request(), mock_output(tmp_path))

    assert result.passed is True
    assert result.score >= 0.8
    assert all(check.passed for check in result.checks)


def test_evaluate_generation_output_reports_missing_workflow_step(tmp_path: Path) -> None:
    output = mock_output(tmp_path)
    output.trace.pop()

    result = evaluate_generation_output("sample", sample_request(), output)

    assert result.passed is False
    assert any(check.name == "workflow.required_steps" and not check.passed for check in result.checks)
    assert REQUIRED_WORKFLOW_STEPS[-1] == "write_log"


def test_summarize_eval_results_aggregates_scores(tmp_path: Path) -> None:
    result = evaluate_generation_output("sample", sample_request(), mock_output(tmp_path))
    summary = summarize_eval_results([result], threshold=0.8)

    assert summary.passed is True
    assert summary.sample_count == 1
    assert summary.average_score == result.score
```

- [ ] **Step 2: Run failing evaluator tests**

Run:

```bash
.venv/bin/pytest tests/test_evaluation.py -q
```

Expected: fail because `dessert_ad_studio.evaluation` does not exist yet.

- [ ] **Step 3: Implement evaluation module**

Create `src/dessert_ad_studio/evaluation.py` with dataclasses:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
import re

from dessert_ad_studio.schemas import GenerationRequest
from dessert_ad_studio.workflow import GenerationWorkflowOutput

REQUIRED_WORKFLOW_STEPS = (
    "rank_templates",
    "decode_reference",
    "analyze_product",
    "build_image_prompt",
    "generate_copy",
    "generate_image",
    "write_log",
)
_KOREAN_RE = re.compile(r"[가-힣]")


@dataclass(frozen=True)
class EvalCheck:
    name: str
    passed: bool
    score: float
    detail: str


@dataclass(frozen=True)
class GenerationEvalResult:
    sample_label: str
    score: float
    passed: bool
    checks: list[EvalCheck]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class EvalSummary:
    sample_count: int
    average_score: float
    passed: bool
    threshold: float
    results: list[GenerationEvalResult]

    def to_dict(self) -> dict:
        return asdict(self)
```

Implement `evaluate_generation_output()` with checks for:

```python
def evaluate_generation_output(
    sample_label: str,
    request: GenerationRequest,
    output: GenerationWorkflowOutput,
    threshold: float = 0.8,
) -> GenerationEvalResult:
    response = output.response
    checks = [
        _check("copy.option_count", len(response.copy_options) >= 3, "at least 3 copy options"),
        _check(
            "copy.korean_text",
            all(_has_korean(option.headline + option.body + option.call_to_action) for option in response.copy_options),
            "all copy options contain Korean text",
        ),
        _check(
            "copy.product_name",
            any(request.product_name in option.headline or request.product_name in option.body for option in response.copy_options),
            "product name appears in generated copy",
        ),
        _check("image.path", bool(response.image_path), "image path is populated"),
        _check("product_analysis.present", response.product_analysis.analyzer_backend != "", "product analysis exists"),
        _check(
            "workflow.required_steps",
            tuple(entry.step for entry in output.trace) == REQUIRED_WORKFLOW_STEPS,
            "workflow trace has required ordered steps",
        ),
        _check(
            "workflow.elapsed_ms",
            response.elapsed_ms >= 0 and all(entry.elapsed_ms >= 0 for entry in output.trace),
            "response and step elapsed times are non-negative",
        ),
    ]
    score = sum(check.score for check in checks) / len(checks)
    return GenerationEvalResult(
        sample_label=sample_label,
        score=score,
        passed=score >= threshold and all(check.passed for check in checks),
        checks=checks,
    )
```

- [ ] **Step 4: Run evaluator tests**

Run:

```bash
.venv/bin/pytest tests/test_evaluation.py -q
```

Expected: all evaluator tests pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add src/dessert_ad_studio/evaluation.py tests/test_evaluation.py
git commit -m "Add deterministic generation evals"
```

---

### Task 4: Demo Eval CLI

**Files:**
- Create: `scripts/eval_demo_samples.py`
- Modify: `README.md`

- [ ] **Step 1: Write CLI script**

Create `scripts/eval_demo_samples.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.demo_samples import DEMO_SAMPLES, DemoSample
from dessert_ad_studio.evaluation import evaluate_generation_output, summarize_eval_results
from dessert_ad_studio.product_analysis import MockProductAnalyzer
from dessert_ad_studio.schemas import GenerationRequest
from dessert_ad_studio.triton import LocalTemplateScorer
from dessert_ad_studio.workflow import GenerationWorkflowDependencies, run_generation_workflow


def request_from_sample(sample: DemoSample) -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose=sample.campaign_purpose,
        product_name=sample.product_name,
        tone=sample.tone,
        template_hint=sample.template_hint,
        price_text=sample.price_text,
        user_constraints=sample.user_constraints,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic evals for demo samples.")
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument("--output-dir", default="outputs/eval")
    parser.add_argument("--log-path", default="logs/eval-generations.jsonl")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    log_path = Path(args.log_path)
    results = []
    for sample in DEMO_SAMPLES:
        backend = MockAdBackend(output_dir=output_dir)
        request = request_from_sample(sample)
        output = run_generation_workflow(
            request,
            GenerationWorkflowDependencies(
                template_scorer=LocalTemplateScorer(),
                copy_backend=backend,
                image_backend=backend,
                product_analyzer=MockProductAnalyzer(),
                log_path=log_path,
            ),
        )
        results.append(evaluate_generation_output(sample.label, request, output, threshold=args.threshold))

    summary = summarize_eval_results(results, threshold=args.threshold)
    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    return 0 if summary.passed else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run eval script**

Run:

```bash
.venv/bin/python scripts/eval_demo_samples.py
```

Expected: JSON summary with `passed: true`, `sample_count: 3`, and `average_score >= 0.8`.

- [ ] **Step 3: Add README AgentOps section**

Add a README section after A2A or Tests:

```markdown
## AgentOps Evidence

Run deterministic local evals over the bundled demo samples:

```bash
python scripts/eval_demo_samples.py
```

Enable local OpenTelemetry/OpenInference span output for API requests:

```bash
WORKFLOW_TRACING=otel uvicorn api.main:app --port 8000
```

The workflow emits OpenInference span kinds for agent, reranker, prompt, LLM,
and tool steps. This is intentionally local-first: Phoenix or Langfuse can be
connected later through OTLP export without changing the workflow contract.
```

- [ ] **Step 4: Run eval script and README-adjacent tests**

Run:

```bash
.venv/bin/python scripts/eval_demo_samples.py
.venv/bin/pytest tests/test_demo_samples.py tests/test_evaluation.py -q
```

Expected: eval script exits `0`; selected tests pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add scripts/eval_demo_samples.py README.md
git commit -m "Document AgentOps eval evidence"
```

---

### Task 5: Final Verification and Review

**Files:**
- Review all touched files.

- [ ] **Step 1: Run full verification**

Run:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/python scripts/eval_demo_samples.py
```

Expected:

- pytest passes.
- ruff passes.
- eval summary exits `0` and reports all demo samples passed.

- [ ] **Step 2: Inspect changed files**

Run:

```bash
git status --short
git diff --stat HEAD
git diff --check
```

Expected:

- Only intended observability, workflow, eval, docs, and dependency files changed.
- `git diff --check` reports no whitespace errors.

- [ ] **Step 3: Spec compliance review**

Review against `docs/superpowers/specs/2026-06-13-workflow-observability-eval-design.md`:

- Existing API/A2A behavior remains compatible.
- Workflow spans exist and carry OpenInference span kind attributes.
- Demo eval script exists and exits non-zero on deterministic failure.
- README documents trace and eval evidence commands.

- [ ] **Step 4: Code quality review**

Check:

- `workflow.py` remains readable and does not duplicate step names inconsistently.
- `observability.py` handles missing optional dependencies clearly.
- Eval checks avoid model-quality claims that the deterministic harness cannot prove.
- Tests do not depend on external services.

- [ ] **Step 5: Final commit if reviews required changes**

If review fixes are needed:

```bash
git add src/dessert_ad_studio/observability.py src/dessert_ad_studio/workflow.py src/dessert_ad_studio/evaluation.py scripts/eval_demo_samples.py README.md tests/test_observability.py tests/test_workflow.py tests/test_evaluation.py pyproject.toml api/main.py
git commit -m "Harden workflow observability eval pack"
```

If no fixes are needed, no additional commit is required.
