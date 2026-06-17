# Agentic RAG SSE Streaming First Gate

Date: 2026-06-17

This evidence records the first FastAPI async SSE run-streaming gate for the
Agentic RAG control plane. It uses the local mock workflow path and does not
call paid providers, web search, cloud services, or MCP tools.

## Scope

- `POST /agentic-rag/runs/stream`
- async FastAPI route returning `text/event-stream`
- SSE events:
  - `run_started`
  - `node_completed`
  - `run_completed`
- node progress for:
  - `plan_campaign`
  - `retrieve_context`
  - `build_citations`
  - `guardrail_check`
  - `execute_worker`
  - `finalize`
- redacted event payloads only
- paid-provider approval route covered by focused API test

## Result

Summary artifact:

```text
docs/evidence/agentic-rag-stream-summary.json
```

Current result:

- `agentic_rag_stream_smoke`: `passed`
- `scope`: `local_fastapi_sse_no_paid_api_call`
- media type: `text/event-stream; charset=utf-8`
- final status: `completed`
- final next action: `return_cited_ad_package`
- worker status: `succeeded`
- copy options: `3`
- raw inputs committed: `false`

## Reproduce

```bash
.venv/bin/python scripts/agentic_rag_stream_smoke.py \
  --date 2026-06-17 \
  --output docs/evidence/agentic-rag-stream-summary.json
```

Focused tests:

```bash
.venv/bin/pytest \
  tests/test_api.py::test_agentic_rag_run_stream_emits_redacted_worker_events \
  tests/test_api.py::test_agentic_rag_run_stream_routes_paid_provider_to_approval \
  tests/test_agentic_rag_stream_smoke_script.py -q
```

## Limits

This proves the first local SSE surface, not the full production streaming
system. The following remain pending:

- durable run IDs and replay
- SQLite/Postgres graph checkpointing
- reviewer approval UI
- production trace integration for stream events
- WebSocket support if bidirectional approval becomes necessary
