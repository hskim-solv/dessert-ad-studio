# Agentic RAG Graph First Gate

Date: 2026-06-17

This evidence records the first offline LangGraph control-plane gate for
Dessert Ad Studio. It proves the graph skeleton and privacy boundary without
calling paid providers, web search, MCP tools, or the downstream image/copy
generation worker.

## Scope

- LangGraph `StateGraph` with typed state schema.
- Deterministic planner, retrieval, citation, guardrail, HITL, and finalize
  nodes.
- Conditional edge from guardrail check to either human approval or worker
  dispatch.
- In-memory checkpointer for local proof only.
- Redacted graph state: raw product name, user constraints, revision request,
  reference image bytes, and reference filename are not committed to the
  summary artifact.

## Result

Summary artifact:

```text
docs/evidence/agentic-rag-graph-summary.json
```

Current result:

- `agentic_rag_graph_smoke`: `passed`
- `scope`: `offline_langgraph_control_plane_no_api_call`
- `langgraph_version`: `1.2.5`
- final graph status: `needs_approval`
- next action: `wait_for_human_approval`
- node trace:
  - `plan_campaign`
  - `retrieve_context`
  - `build_citations`
  - `guardrail_check`
  - `human_approval`
- retrieved docs: `3`
- citations: `3`
- checkpoints: `7`
- raw inputs committed: `false`

## Reproduce

```bash
.venv/bin/python scripts/agentic_rag_graph_smoke.py \
  --date 2026-06-17 \
  --output docs/evidence/agentic-rag-graph-summary.json
```

Focused tests:

```bash
.venv/bin/pytest tests/test_agentic_rag.py tests/test_agentic_rag_smoke_script.py -q
```

## Limits

This is not yet the full Agentic RAG system. The following remain pending:

- downstream worker execution from the graph
- retry/reflection loop
- persistent SQLite/Postgres checkpointer
- SSE/WebSocket streaming
- Ragas and promptfoo eval gates
- web search, SQL, internal API, and MCP tools
- production citation assembly over generated ad packages
