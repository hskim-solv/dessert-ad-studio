# Agentic RAG SSE/WebSocket Streaming First Gate

Date: 2026-06-17

This evidence records the first FastAPI async SSE and WebSocket run-streaming
gate for the Agentic RAG control plane. It uses the local mock workflow path
and does not call paid providers, web search, cloud services, or MCP tools.

## Scope

- `POST /agentic-rag/runs/stream`
- `WS /agentic-rag/runs/ws`
- async FastAPI route returning `text/event-stream`
- async FastAPI WebSocket route sending JSON event envelopes
- SSE events:
  - `run_started`
  - `node_completed`
  - `run_completed`
- WebSocket messages use the same event names and redacted payload schema
- node progress for:
  - `plan_campaign`
  - `retrieve_context`
  - `build_citations`
  - `guardrail_check`
  - `execute_worker`
  - `finalize`
- redacted event payloads only
- durable `run_id` emitted in `run_started`
- local SQLite replay endpoint: `GET /agentic-rag/runs/{run_id}/replay`
- paid-provider approval route covered by focused SSE and WebSocket API tests

## Result

Summary artifacts:

```text
docs/evidence/agentic-rag-stream-summary.json
docs/evidence/agentic-rag-websocket-summary.json
```

Current SSE result:

- `agentic_rag_stream_smoke`: `passed`
- `scope`: `local_fastapi_sse_no_paid_api_call`
- media type: `text/event-stream; charset=utf-8`
- final status: `completed`
- final next action: `return_cited_ad_package`
- worker status: `succeeded`
- copy options: `3`
- checkpointing enabled: `true`
- replay checkpoint backend: `sqlite`
- replay checkpoints: `8`
- replay status: `completed`
- replay next action: `return_cited_ad_package`
- raw inputs committed: `false`

Current WebSocket result:

- `agentic_rag_websocket_smoke`: `passed`
- `scope`: `local_fastapi_websocket_no_paid_api_call`
- stream protocol: `websocket`
- final status: `completed`
- final next action: `return_cited_ad_package`
- worker status: `succeeded`
- copy options: `3`
- checkpointing enabled: `true`
- raw inputs committed: `false`

## Reproduce

```bash
.venv/bin/python scripts/agentic_rag_stream_smoke.py \
  --date 2026-06-17 \
  --output docs/evidence/agentic-rag-stream-summary.json

.venv/bin/python scripts/agentic_rag_websocket_smoke.py \
  --date 2026-06-17 \
  --output docs/evidence/agentic-rag-websocket-summary.json
```

Focused tests:

```bash
.venv/bin/pytest \
  tests/test_api.py::test_agentic_rag_run_stream_emits_redacted_worker_events \
  tests/test_api.py::test_agentic_rag_run_replay_returns_redacted_sqlite_checkpoint_summary \
  tests/test_api.py::test_agentic_rag_run_replay_returns_404_for_unknown_run \
  tests/test_api.py::test_agentic_rag_run_stream_routes_paid_provider_to_approval \
  tests/test_api.py::test_agentic_rag_run_websocket_emits_redacted_worker_events \
  tests/test_api.py::test_agentic_rag_run_websocket_routes_paid_provider_to_approval \
  tests/test_agentic_rag_stream_smoke_script.py -q
```

## Limits

This proves the first local SSE and WebSocket surfaces, not the full production
streaming system. The following remain pending:

- production stream replay and retention policy
- production Postgres or multi-instance graph checkpointing
- reviewer approval UI
- production trace retention policy for stream events
- bidirectional in-stream approval flow if reviewer decisions need to be sent
  before graph completion
