# OTLP Phoenix Export Evidence Design

## Context

The workflow observability pack currently emits local OpenTelemetry spans with
OpenInference attributes, but `WORKFLOW_TRACE_EXPORT=console` is the only active
export path. The README correctly frames Phoenix and Langfuse as future work.
The next useful productionization step is to make that future path real enough
to demonstrate: export spans through OTLP and provide a local Phoenix compose
override for inspection.

## Goal

Add an optional OTLP trace export path and local Phoenix runtime evidence while
preserving the default no-tracing and console-tracing behavior.

## Non-Goals

- Do not make Phoenix required for normal API, Streamlit, or eval usage.
- Do not introduce Langfuse yet.
- Do not use `phoenix.otel.register()` or any helper that replaces the global
  OpenTelemetry provider.
- Do not send prompt bodies, uploaded image bytes, or generated image bytes into
  spans.
- Do not change workflow step names or JSONL generation logs.

## Approaches Considered

1. Add `arize-phoenix-otel` and use Phoenix's registration helper.
   - Pros: very small setup.
   - Cons: it is Phoenix-specific and may replace global tracer configuration,
     which is too invasive for this service.
2. Add the OpenTelemetry OTLP HTTP exporter and keep the existing local tracer
   factory.
   - Pros: vendor-neutral, fits Phoenix and other OTLP collectors, and preserves
     the current dependency injection design.
   - Cons: requires one more OpenTelemetry package and a little configuration.
3. Add a full observability stack with collector, Phoenix, Grafana, and Tempo.
   - Pros: strong platform story.
   - Cons: too much surface area before the simple OTLP evidence path exists.

Chosen approach: option 2.

## Documentation Basis

OpenTelemetry Python documents `opentelemetry-exporter-otlp-proto-http` as the
specific HTTP exporter package. Phoenix self-hosting docs describe Phoenix as an
all-in-one UI and collector that exposes port `6006` for the UI and OTLP HTTP
collection, and port `4317` for OTLP gRPC collection by default.

## Architecture

Extend `src/dessert_ad_studio/observability.py` so the existing
`build_workflow_tracer()` keeps the same modes:

- `WORKFLOW_TRACING=none`: `NoopWorkflowTracer`
- `WORKFLOW_TRACING=memory`: `InMemoryWorkflowTracer`
- `WORKFLOW_TRACING=otel`: `OpenInferenceWorkflowTracer`

Only the `otel` mode changes. `WORKFLOW_TRACE_EXPORT` accepts:

- `console`: current behavior, `ConsoleSpanExporter`
- `otlp`: new behavior, OTLP HTTP trace export
- `none` / `off` / `false` / `0`: no exporter attached to the provider

New OTLP configuration:

| Variable | Default | Meaning |
| --- | --- | --- |
| `WORKFLOW_TRACE_EXPORT` | `console` | `console`, `otlp`, or disabled |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | `http://localhost:6006/v1/traces` | Trace-specific OTLP HTTP endpoint |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | Base OTLP endpoint fallback |
| `OTEL_SERVICE_NAME` | `dessert-ad-studio` | OpenTelemetry service name |

Endpoint resolution:

1. Use `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` when set.
2. Else use `OTEL_EXPORTER_OTLP_ENDPOINT` when set. If it does not end with
   `/v1/traces`, append `/v1/traces`.
3. Else use `http://localhost:6006/v1/traces`, which matches local Phoenix
   OTLP HTTP collection.

## Docker Compose Evidence

Add `docker-compose.agentops.yml` as an optional override:

- Adds `phoenix` service using `arizephoenix/phoenix:latest`.
- Exposes `6006:6006` for Phoenix UI and OTLP HTTP.
- Exposes `4317:4317` for OTLP gRPC compatibility.
- Adds a persistent `phoenix-data` volume.
- Sets the API container environment:
  - `WORKFLOW_TRACING=otel`
  - `WORKFLOW_TRACE_EXPORT=otlp`
  - `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://phoenix:6006/v1/traces`
  - `OTEL_SERVICE_NAME=dessert-ad-studio-api`
- Adds `api -> phoenix` dependency in the override only.

Normal `docker compose up --build` remains unchanged.

## Smoke Evidence

Add `scripts/otel_trace_smoke.py`:

- Runs one mock workflow request.
- Uses `build_workflow_tracer("otel")`.
- Prints a compact success message with service name, export mode, endpoint, and
  generated image path.
- Does not require Phoenix for console mode.
- Can run against Phoenix when env vars point to the local compose service or a
  host Phoenix instance.

The existing eval script remains the deterministic quality gate. The new smoke
script is a trace export sanity check, not an evaluator.

## Testing

Add focused tests:

- `tests/test_observability.py`
  - `WORKFLOW_TRACE_EXPORT=otlp` builds an `OpenInferenceWorkflowTracer`.
  - trace endpoint resolution handles explicit trace endpoint, base endpoint,
    and default Phoenix endpoint.
  - unsupported export values raise a clear `ValueError`.
- `tests/test_otel_trace_smoke.py`
  - smoke script can run in console mode without Phoenix.

Manual verification:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
WORKFLOW_TRACING=otel WORKFLOW_TRACE_EXPORT=console .venv/bin/python scripts/otel_trace_smoke.py
```

Optional Phoenix verification:

```bash
docker compose -f docker-compose.yml -f docker-compose.agentops.yml up --build
```

Then open:

```text
http://localhost:6006
```

## Acceptance Criteria

- Defaults remain safe: no tracing unless `WORKFLOW_TRACING` is enabled.
- Console trace output still works.
- `WORKFLOW_TRACE_EXPORT=otlp` uses the OTLP HTTP exporter package.
- Phoenix is optional and only enabled through the compose override.
- README documents local AgentOps commands without claiming hosted production
  readiness.
- Full tests, lint, eval script, and console trace smoke pass.
