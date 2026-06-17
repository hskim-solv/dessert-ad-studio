# Agentic RAG Local Tool Suite

Date: 2026-06-17

This evidence records the first local Agentic RAG tool-suite gate. It proves
that the graph can plan and execute web search, SQL query, internal API, and
document retrieval shaped tools without external network calls, paid APIs, or
production database access.

Decision record:

```text
docs/adr/0017-agentic-rag-tool-suite.md
```

## Scope

- `web_search`: local curated snapshot summary, no live network call.
- `sql_query`: in-memory SQLite allowlisted query, no arbitrary SQL.
- `internal_api`: in-process `preview_generation_policy` contract.
- `document_retrieval`: existing keyword marketing-context retriever.
- MCP server scaffold: `mcp_servers/dessert_ad_studio_server.py` with FastMCP
  tool wrappers.
- Graph node: `run_tool_suite`.
- Tool budget: 7 planned tools, all allowlisted.

## Result

Summary artifact:

```text
docs/evidence/agentic-rag-tools-summary.json
```

Current result:

- `agentic_rag_tools_smoke`: `passed`
- `scope`: `local_tool_suite_no_network_no_paid_api_call`
- planned tools:
  - `document_retrieval`
  - `web_search`
  - `sql_query`
  - `internal_api`
  - `citation_builder`
  - `guardrail_check`
  - `generation_workflow`
- web search mode: `local_curated_snapshot`
- SQL mode: `sqlite_allowlisted_query`
- internal API mode: `in_process_contract`
- raw inputs committed: `false`

## Reproduce

```bash
.venv/bin/python scripts/agentic_rag_tools_smoke.py \
  --date 2026-06-17 \
  --output docs/evidence/agentic-rag-tools-summary.json
```

Focused tests:

```bash
.venv/bin/pytest tests/test_agentic_rag_tools.py tests/test_agentic_rag.py -q
```

## Limits

This is not yet live web search, production SQL access, or a proven MCP package
execution gate. The FastMCP server is a scaffold and remains optional until
`mcp` dependency/runtime behavior is measured.
