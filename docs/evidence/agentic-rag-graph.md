# Agentic RAG Graph First Gate

Date: 2026-06-17

This evidence records the first offline LangGraph control-plane gate for
Dessert Ad Studio. It proves the graph skeleton, local tool-suite node, and
privacy boundary without calling paid providers, live web search, or production
MCP tools. It also proves that the graph can dispatch the existing local mock
image/copy generation workflow as a worker node after guardrails pass.

## Scope

- LangGraph `StateGraph` with typed state schema.
- Deterministic planner, local tool-suite, retrieval, citation, guardrail,
  worker, reflection, HITL, and finalize nodes.
- Local tool-suite node for web search snapshot, allowlisted SQLite query, and
  in-process internal API policy preview.
- Conditional edge from guardrail check to either human approval or worker
  dispatch.
- Worker execution through the existing `run_generation_workflow()` path using
  local mock backends.
- Redacted cited ad package summary that binds retrieved source document ids to
  generated worker artifact metadata without storing raw assets.
- Retry/reflection behavior covered by focused tests without persisting raw
  exception detail.
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
- `scope`: `offline_langgraph_control_plane_no_paid_api_call`
- `langgraph_version`: `1.2.5`

Approval route:

- final status: `needs_approval`
- next action: `wait_for_human_approval`
- node trace:
  - `plan_campaign`
  - `run_tool_suite`
  - `retrieve_context`
  - `build_citations`
  - `guardrail_check`
  - `human_approval`
- retrieved docs: `3`
- citations: `3`
- checkpoints: `8`
- raw inputs committed: `false`

Worker route:

- final status: `completed`
- next action: `return_cited_ad_package`
- worker status: `succeeded`
- copy backend: `mock`
- image backend: `mock`
- copy options: `3`
- cited ad package ready: `true`
- cited package source docs: `3`
- raw assets committed: `false`
- node trace:
  - `plan_campaign`
  - `run_tool_suite`
  - `retrieve_context`
  - `build_citations`
  - `guardrail_check`
  - `execute_worker`
  - `finalize`
- checkpoints: `9`
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

- production Postgres or multi-instance checkpointer policy
- live web search, production SQL access, and proven MCP package execution
- production/live citation assembly over generated ad packages
