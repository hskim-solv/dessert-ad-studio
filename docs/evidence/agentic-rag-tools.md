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
- `sql_query`: in-memory SQLite allowlisted query, no arbitrary SQL, read-only
  policy summary, row limit, and timeout budget.
- `internal_api`: in-process `preview_generation_policy` contract.
- `document_retrieval`: existing keyword marketing-context retriever.
- MCP server: `mcp_servers/dessert_ad_studio_server.py` with FastMCP tool
  wrappers and local package import/tool-call smoke.
- Graph node: `run_tool_suite`.
- Tool budget: 7 planned tools, all allowlisted.

## Result

Summary artifact:

```text
docs/evidence/agentic-rag-tools-summary.json
docs/evidence/agentic-rag-mcp-server-summary.json
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
- SQL policy: read-only, query-id allowlist only, raw SQL disabled, mutation
  statements disabled, row limit `25`, timeout `250ms`
- internal API mode: `in_process_contract`
- MCP package smoke: `passed`
- MCP version: `1.28.0`
- MCP tools:
  - `search_marketing_guides`
  - `query_template_policy`
  - `preview_generation_policy`
- raw inputs committed: `false`

## Reproduce

```bash
.venv/bin/python scripts/agentic_rag_tools_smoke.py \
  --date 2026-06-17 \
  --output docs/evidence/agentic-rag-tools-summary.json

.venv/bin/python scripts/agentic_rag_mcp_server_smoke.py \
  --date 2026-06-17 \
  --output docs/evidence/agentic-rag-mcp-server-summary.json
```

Focused tests:

```bash
.venv/bin/pytest \
  tests/test_agentic_rag_tools.py \
  tests/test_agentic_rag_mcp_server.py \
  tests/test_agentic_rag.py -q
```

## Limits

This is not yet live web search or production DB access. The SQL runtime policy
first gate is local SQLite only; production credentials, audit logging,
retention, and DB role policy remain pending. The MCP proof imports the package
and calls the FastMCP-wrapped local tools, but it does not start a long-running
production MCP service or test remote client auth/transport.
