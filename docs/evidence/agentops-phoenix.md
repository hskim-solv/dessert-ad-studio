# AgentOps Phoenix Evidence

Date: 2026-06-13

## Purpose

This note records operational evidence for Dessert Ad Studio's AgentOps path:
workflow-level OpenTelemetry/OpenInference spans, OTLP export, and the optional
Phoenix runtime path.

This is not a model-quality benchmark. Deterministic regression checks are
covered by `scripts/eval_demo_samples.py`.

## Implemented Surface

- `run_generation_workflow()` emits workflow spans.
- Spans include OpenInference span kinds: `AGENT`, `RERANKER`, `PROMPT`, `LLM`,
  and `TOOL`.
- `WORKFLOW_TRACE_EXPORT=console` emits local OpenTelemetry console spans.
- `WORKFLOW_TRACE_EXPORT=otlp` exports through the OTLP HTTP exporter.
- `docker-compose.agentops.yml` adds Phoenix as an optional service.

## Local Verification Completed

### Trace/Log Privacy Allowlist Gate

Command:

```bash
.venv/bin/pytest \
  tests/test_workflow.py::test_workflow_trace_and_log_use_privacy_allowlist \
  tests/test_api.py::test_image_failure_log_uses_privacy_allowlist \
  tests/test_otel_trace_smoke.py::test_otel_trace_smoke_runs_with_console_export \
  -q
```

Result:

```text
3 passed in 63.21s
```

This gate verifies that persistent workflow trace/log surfaces and image-failure
usage logs do not store raw product names, user constraints, revision requests,
reference filenames, generated copy text, raw prompt summaries, or raw image
paths. The durable fields use `has_*` booleans and `*_sha256` identifiers
instead. Agentic RAG deployment trace retention now has a first-gate attribute
contract in `agentic-rag-retention-policy.md`; external backend selection and
production customer trace capture remain pending user decisions.

### Compose Configuration

Command:

```bash
docker compose -f docker-compose.yml -f docker-compose.agentops.yml config >/tmp/dessert-agentops-compose.yml
```

Result:

```text
compose_config=passed
```

### Console Trace Smoke

Command:

```bash
WORKFLOW_TRACING=otel WORKFLOW_TRACE_EXPORT=console .venv/bin/python scripts/otel_trace_smoke.py
```

Result:

```text
trace_smoke=passed export=console endpoint=local-console steps=8 has_image_path=True image_path_sha256=7c253420001fbf660d27cef06ae4080dd20a4d8b8662d2707370189877f06f83
```

### Deterministic Eval Gate

Command:

```bash
.venv/bin/python scripts/eval_demo_samples.py \
  --output docs/evidence/workflow-eval-summary.json
```

Summary:

```text
eval_passed=True sample_count=3 average_score=1.0 failure_count=0
```

The durable summary is stored at
`docs/evidence/workflow-eval-summary.json`. It includes per-sample checks plus
`failure_count` and `failure_cases` fields, so failing workflow evals produce a
reviewable failure-case report without reading raw generation logs.

## Phoenix Live UI Verification

Phoenix was started through the optional AgentOps compose override:

```bash
docker compose -f docker-compose.yml -f docker-compose.agentops.yml up -d phoenix
```

Container state:

```text
part4-phoenix-1   arizephoenix/phoenix:latest   Up   0.0.0.0:4317->4317/tcp, 0.0.0.0:6006->6006/tcp
```

HTTP readiness:

```text
phoenix_http=ready
HTTP/1.1 200 OK
x-phoenix-server-version: 17.5.0
```

One workflow trace was exported to Phoenix through OTLP HTTP:

```bash
WORKFLOW_TRACING=otel \
WORKFLOW_TRACE_EXPORT=otlp \
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:6006/v1/traces \
.venv/bin/python scripts/otel_trace_smoke.py
```

Result:

```text
trace_smoke=passed export=otlp endpoint=http://localhost:6006/v1/traces steps=8 has_image_path=True image_path_sha256=<sha256>
```

Phoenix GraphQL verification:

```text
project=default traceCount=2
latest_root_span=generation_workflow spanKind=agent latencyMs=80.0 trace.numSpans=8
latest_trace_id=6bafdf5027405443eecb0fb0cf518d78
descendants=rank_templates, decode_reference, analyze_product, build_image_prompt, generate_copy, generate_image, write_log
```

Captured UI evidence:

- `docs/evidence/assets/phoenix-workflow-trace.png` shows the Phoenix project
  list after the first successful OTLP smoke request.
- `docs/evidence/assets/phoenix-trace-detail.png` shows the trace detail panel
  with the `generation_workflow` root span and workflow child spans.

## Previous Blocker Resolved

The first Phoenix run was blocked by local Docker/host disk capacity:

```text
failed to register layer: write /phoenix/.venv/lib/python3.13/site-packages/uvloop/loop.cpython-313-aarch64-linux-gnu.so: input/output error
```

Host disk state at the time of the failed attempt:

```text
Filesystem      Size    Used   Avail Capacity
/dev/disk3s5   228Gi   190Gi   116Mi   100%
```

After freeing disk space, the same compose and OTLP path verified successfully.

## Phoenix Evidence Reproduction

1. Start Phoenix:

```bash
docker compose -f docker-compose.yml -f docker-compose.agentops.yml up -d phoenix
```

2. Open Phoenix:

```text
http://localhost:6006
```

3. Send one workflow trace directly to local Phoenix:

```bash
WORKFLOW_TRACING=otel \
WORKFLOW_TRACE_EXPORT=otlp \
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:6006/v1/traces \
.venv/bin/python scripts/otel_trace_smoke.py
```

## Full Compose Evidence Procedure

Use this path when the full API/Triton/Streamlit compose stack is needed:

```bash
python scripts/export_template_scorer_onnx.py
docker compose -f docker-compose.yml -f docker-compose.agentops.yml up --build
```

In another shell, trigger a `/generate` request:

```bash
python scripts/api_smoke.py --base-url http://127.0.0.1:8080
```

Then open Phoenix:

```text
http://localhost:6006
```

Look for service name:

```text
dessert-ad-studio-api
```

## Source Checks

- Phoenix self-hosted default UI and OTLP HTTP endpoint:
  `http://localhost:6006` and `http://localhost:6006/v1/traces`.
- Phoenix gRPC OTLP endpoint: `4317`.
- Docker image used by the optional override: `arizephoenix/phoenix:latest`.

References:

- https://arize.com/docs/phoenix/self-hosting/configuration
- https://arize.com/docs/phoenix/self-hosting/deployment-options/docker
