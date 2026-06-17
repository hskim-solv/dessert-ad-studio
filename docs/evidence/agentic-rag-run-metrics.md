# Agentic RAG Run Metrics First Gate

Date: 2026-06-17

This evidence records the first local run-metrics gate for the Agentic RAG
control plane. It proves that a reviewer can inspect latency, token, cost,
tool-call, and failed-run summaries without storing raw customer inputs or
calling paid providers.

## Scope

- Executes the success route through:
  - `plan_campaign`
  - `run_tool_suite`
  - `retrieve_context`
  - `build_citations`
  - `guardrail_check`
  - `execute_worker`
  - `finalize`
- Captures per-node elapsed time from `InMemoryWorkflowTracer`.
- Reports local mock token usage and cost as explicit zero values.
- Reports planned tool budget and local tool-suite result counts.
- Executes a deterministic failed-worker route to summarize retry/reflection,
  redacted graceful fallback, and final `inspect_failed_run` behavior.

## Result

Summary artifact:

```text
docs/evidence/agentic-rag-run-metrics-summary.json
```

Current result:

- `agentic_rag_run_metrics_smoke`: `passed`
- `scope`: `local_agentic_rag_metrics_no_paid_api_call`
- paid API calls: `0`
- span count: `7`
- planned tool calls: `7`
- successful local tool results: `3`
- failed-run status: `failed`
- failed-run next action: `inspect_failed_run`
- retry attempts: `1`
- graceful fallback ready: `true`
- fallback reason: `worker_failed_after_retry_budget`
- raw error committed: `false`
- raw inputs committed: `false`

## Reproduce

```bash
.venv/bin/python scripts/agentic_rag_run_metrics_smoke.py \
  --date 2026-06-17 \
  --output docs/evidence/agentic-rag-run-metrics-summary.json
```

Focused test:

```bash
.venv/bin/pytest \
  tests/test_agentic_rag_smoke_script.py::test_agentic_rag_run_metrics_smoke_writes_redacted_summary \
  -q
```

## Limits

- This is a local no-paid-provider gate. Real provider token accounting and
  cost telemetry remain provider-gated.
- It proves summary-level failed-run analysis and redacted graceful fallback,
  not a production incident dashboard.
- Production retention policy still requires a deployment-specific review
  before storing external traces or run metrics.
