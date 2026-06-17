# Agentic RAG Trace First Gate

Date: 2026-06-17

This evidence records the first OpenInference-compatible trace gate for the
Agentic RAG control plane. It proves graph-node spans with redacted attributes
without calling paid providers, live web search, cloud services, or production
MCP tools.

## Scope

- LangGraph node spans for:
  - `plan_campaign`
  - `run_tool_suite`
  - `retrieve_context`
  - `build_citations`
  - `guardrail_check`
  - `execute_worker`
  - `finalize`
- OpenInference span kinds:
  - `AGENT`
  - `TOOL`
  - `RETRIEVER`
  - `CHAIN`
  - `GUARDRAIL`
  - `TOOL`
- API stream path passes `build_workflow_tracer()` into the graph.
- Trace attributes are allowlisted summary fields only.

## Result

Summary artifact:

```text
docs/evidence/agentic-rag-trace-summary.json
```

Current result:

- `agentic_rag_trace_smoke`: `passed`
- `scope`: `local_in_memory_openinference_trace_no_paid_api_call`
- span count: `7`
- final status: `completed`
- final next action: `return_cited_ad_package`
- raw inputs committed: `false`

## Reproduce

```bash
.venv/bin/python scripts/agentic_rag_trace_smoke.py \
  --date 2026-06-17 \
  --output docs/evidence/agentic-rag-trace-summary.json
```

Focused tests:

```bash
.venv/bin/pytest \
  tests/test_agentic_rag.py::test_agentic_rag_graph_emits_redacted_openinference_spans \
  tests/test_api.py::test_agentic_rag_run_stream_uses_workflow_tracer_for_graph_nodes \
  tests/test_agentic_rag_smoke_script.py::test_agentic_rag_trace_smoke_writes_redacted_summary \
  -q
```

## Limits

- This proves local in-memory trace attributes and API wiring.
- Phoenix/OTLP export for Agentic RAG graph spans still depends on the existing
  AgentOps/Phoenix runtime path.
- Production trace retention and customer-data policy still require a
  deployment-specific attribute review.
