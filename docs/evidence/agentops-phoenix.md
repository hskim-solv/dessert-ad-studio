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
trace_smoke=passed export=console endpoint=local-console steps=7 image_path=outputs/otel-smoke/말차_푸딩_mock_ad.png
```

### Deterministic Eval Gate

Command:

```bash
.venv/bin/python scripts/eval_demo_samples.py
```

Summary:

```text
eval_passed=True sample_count=3 average_score=1.0
```

## Phoenix Live UI Attempt

Intended command:

```bash
docker compose -f docker-compose.yml -f docker-compose.agentops.yml up -d phoenix
```

Observed result:

```text
failed to register layer: write /phoenix/.venv/lib/python3.13/site-packages/uvloop/loop.cpython-313-aarch64-linux-gnu.so: input/output error
```

Host disk state at the time of the attempt:

```text
Filesystem      Size    Used   Avail Capacity
/dev/disk3s5   228Gi   190Gi   116Mi   100%
```

Docker follow-up commands reported:

```text
Error response from daemon: Docker Desktop is unable to start
```

Conclusion: live Phoenix UI capture is blocked by local Docker/host disk
capacity, not by the application code or compose syntax.

## Phoenix Evidence Procedure After Disk Cleanup

1. Free enough disk space for Docker Desktop and the Phoenix image.
2. Start Phoenix through the optional compose override:

```bash
docker compose -f docker-compose.yml -f docker-compose.agentops.yml up -d phoenix
```

3. Send one workflow trace directly to local Phoenix:

```bash
WORKFLOW_TRACING=otel \
WORKFLOW_TRACE_EXPORT=otlp \
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:6006/v1/traces \
.venv/bin/python scripts/otel_trace_smoke.py
```

Expected success line:

```text
trace_smoke=passed export=otlp endpoint=http://localhost:6006/v1/traces steps=7 ...
```

4. Open Phoenix:

```text
http://localhost:6006
```

5. Capture a screenshot showing workflow spans for the local smoke request.
   Save it under:

```text
docs/evidence/assets/phoenix-workflow-trace.png
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
