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
- Live web search runtime policy: provider types, query redaction, domain
  allowlist requirement, timeout/result limits, citation requirement, and
  no-raw-HTML retention contract recorded without provider credentials.
- `sql_query`: in-memory SQLite allowlisted query, no arbitrary SQL, read-only
  policy summary, row limit, and timeout budget.
- Production DB access/audit policy: read-only role, private network/SSL
  boundary, query-id allowlist, audit event schema, and redaction contract
  recorded without credentials or a production connection.
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
- Live web search runtime policy: `first_gate_complete`; provider smoke
  `pending_user_approval`; raw query, raw user inputs, secrets, and raw HTML are
  excluded from committed evidence.
- SQL mode: `sqlite_allowlisted_query`
- SQL policy: read-only, query-id allowlist only, raw SQL disabled, mutation
  statements disabled, row limit `25`, timeout `250ms`
- Production DB access/audit policy: `first_gate_complete`; credentialed
  connection smoke `pending_user_approval`; required role
  `agentic_rag_readonly`; raw SQL, row values, raw user inputs, and secrets are
  excluded from committed audit evidence.
- internal API mode: `in_process_contract`
- MCP package smoke: `passed`
- MCP version: `1.28.0`
- MCP served transport policy: `streamable-http`, loopback-only `127.0.0.1`,
  manual command `python -m mcp_servers.dessert_ad_studio_server`
- MCP production auth status: `pending_auth_provider_selection`
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

This is not yet live web search traffic or credentialed production DB traffic.
The live web search runtime policy first gate records provider types, query
redaction, domain allowlist, result/timeout limits, citation requirement, and
raw-page retention boundary before any provider credential is used. Live web
search provider selection and smoke remain pending. The SQL runtime policy
first gate is local SQLite only, and the production DB access/audit policy first
gate records the required read-only role, network/SSL boundary, query allowlist,
audit event fields, and redaction contract before any credential is used.
Production DB credential injection, connection smoke, approved audit-retention
duration, and user/project/entity retention scope remain pending. The MCP proof
imports the package, calls the FastMCP-wrapped local tools, and records a
loopback-only `streamable-http` transport/auth boundary; it does not select a
production auth provider or run a remote client auth/transport smoke.
