# Workflow Observability and Eval Pack Design

## Context

Dessert Ad Studio already has a controlled generation workflow, JSONL generation
logs, FastAPI health and metrics endpoints, Kubernetes manifests, and an A2A
interoperability spike. The next portfolio gap is AgentOps evidence: traceable
workflow execution, reproducible local evaluation, and clear commands that prove
the service can be debugged and assessed like a production AI application.

This design implements a narrow first pass. It adds OpenTelemetry-compatible
workflow spans with OpenInference semantic attributes and a deterministic eval
harness for demo outputs. It does not introduce a hosted Phoenix, Langfuse, or
LiteLLM deployment yet.

## Goals

- Preserve the existing `run_generation_workflow()` behavior and API contract.
- Add a small observability abstraction that can emit local workflow spans.
- Map workflow steps to OpenInference span kinds and attributes.
- Keep tracing optional and safe when telemetry dependencies are unavailable.
- Add deterministic evaluation for copy, workflow, and product-preservation
  signals using existing demo samples and mock backends.
- Document repeatable evidence commands in the README.

## Non-Goals

- No new autonomous agent behavior.
- No hosted observability service setup.
- No Phoenix or Langfuse runtime requirement.
- No LiteLLM gateway routing.
- No model-quality benchmark claims beyond deterministic local checks.
- No change to the Korean text rendering rule; text remains rendered outside the
  image model.

## Recommended Approach

Use a lightweight in-repo tracing interface and an OpenTelemetry adapter.

Alternatives considered:

1. Directly call OpenTelemetry APIs from `workflow.py`.
   - Pro: smallest line count.
   - Con: couples business workflow to one telemetry implementation and makes
     unit tests more brittle.
2. Add a local `WorkflowTracer` interface with noop, in-memory, and
   OpenInference/OpenTelemetry adapters.
   - Pro: testable, optional, compatible with future Phoenix/Langfuse OTLP
     export, and keeps workflow code readable.
   - Con: one extra module.
3. Install a full AgentOps stack now.
   - Pro: visually impressive dashboards.
   - Con: too much operational surface before the workflow/eval evidence is
     stable.

Chosen approach: option 2.

## Architecture

Create `src/dessert_ad_studio/observability.py` with:

- `WorkflowSpanRecord`: local span evidence for tests and scripts.
- `WorkflowTracer`: protocol with a `span(name, kind, attributes)` context
  manager.
- `NoopWorkflowTracer`: default tracer that adds no overhead.
- `InMemoryWorkflowTracer`: deterministic local tracer for tests and CLI
  evidence.
- `OpenInferenceWorkflowTracer`: adapter that starts OpenTelemetry spans and
  sets OpenInference semantic attributes when optional dependencies are present.
- `build_workflow_tracer()`: factory driven by environment variables.

The workflow dependency object receives a `workflow_tracer` field defaulting to
`NoopWorkflowTracer`. Each existing workflow step wraps its current work in a
span:

```text
generation_workflow        AGENT
  rank_templates           RERANKER
  decode_reference         TOOL
  analyze_product          LLM
  build_image_prompt       PROMPT
  generate_copy            LLM
  generate_image           TOOL
  write_log                TOOL
```

The existing JSONL `workflow_trace` remains available for compatibility. Span
metadata and JSONL trace metadata should share stable step names.

## Configuration

Add optional observability dependencies to project dependencies:

- `opentelemetry-api`
- `opentelemetry-sdk`
- `openinference-semantic-conventions`

Runtime environment variables:

| Variable | Default | Behavior |
| --- | --- | --- |
| `WORKFLOW_TRACING` | `none` | `none`, `memory`, or `otel` |
| `WORKFLOW_TRACE_EXPORT` | `console` | First adapter supports console export |
| `OTEL_SERVICE_NAME` | `dessert-ad-studio` | OpenTelemetry resource service name |

`WORKFLOW_TRACING=memory` is intended for scripts/tests. `WORKFLOW_TRACING=otel`
creates OpenTelemetry spans with OpenInference attributes.

## Evaluation Harness

Create `src/dessert_ad_studio/evaluation.py` with deterministic evaluators:

- `evaluate_copy_options(response)`: verifies copy option count, Korean text
  presence, CTA presence, and empty-string regressions.
- `evaluate_workflow_trace(trace)`: verifies required step order and positive
  elapsed time.
- `evaluate_generation_response(request, output)`: combines copy, trace,
  backend, product-analysis, and product-name presence signals.

Create `scripts/eval_demo_samples.py` to run all demo samples through mock
backends, print a compact JSON summary, and exit non-zero if the average score
falls below the threshold.

The first threshold is intentionally conservative: all mock demo samples must
pass workflow integrity checks and return a score of at least `0.80`.

## Error Handling

- If OpenTelemetry/OpenInference packages are missing and `WORKFLOW_TRACING=otel`
  is requested, raise a clear `RuntimeError` at tracer construction time.
- If tracing is disabled or set to `none`, workflow behavior is unchanged.
- Eval scripts exit `1` only for deterministic quality gate failures, not for
  advisory warnings.

## Testing

Add focused tests:

- `tests/test_observability.py`
  - in-memory tracer records spans and attributes.
  - OpenInference attribute builder emits stable span kind fields.
  - OpenTelemetry adapter can export a span to an in-memory exporter when
    dependencies are installed.
- `tests/test_workflow.py`
  - injected tracer receives workflow and step spans.
  - existing JSONL workflow trace remains unchanged.
- `tests/test_evaluation.py`
  - evaluator scores a valid mock generation above threshold.
  - evaluator reports missing required workflow steps.
  - eval summary aggregates demo sample results deterministically.

Verification commands:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/python scripts/eval_demo_samples.py
```

## Acceptance Criteria

- Existing REST and A2A behavior remains compatible.
- Workflow execution can be traced locally without external services.
- OpenInference span kind attributes are attached to OpenTelemetry spans.
- Demo sample eval can be run from a single documented command.
- README includes an AgentOps evidence section with trace and eval commands.
- Full tests and lint pass.
