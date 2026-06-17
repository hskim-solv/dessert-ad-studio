# 0017. Agentic RAG Tool Suite

- 날짜: 2026-06-17
- 상태: 채택됨

## 배경 (Context)

Agentic RAG final target은 document retrieval, web search, SQL query, internal
API, MCP tool server를 요구한다. 현재 graph first gate는 document retrieval과
generation workflow 중심이며 web/SQL/internal API/MCP는 pending으로 남아 있다.

이번 결정의 목표는 외부 네트워크, paid API, production DB credential 없이 도구
orchestration 증거를 먼저 만드는 것이다. 실제 live web search와 credentialed
production DB traffic은 비용/보안/retention 정책이 필요하므로 기본 CI에 넣지
않는다. 대신 live web search는 provider type, query redaction, domain
allowlist, result/timeout limit, citation requirement를 먼저 고정하고,
production DB access/audit은 read-only role, private network/SSL, query-id
allowlist, audit event schema, redaction contract를 먼저 고정한다.

## 선택 기준 (Criteria)

| 기준 | 이유 |
|---|---|
| 무비용 재현성 | 기본 CI와 로컬 reviewer command가 paid API 없이 돌아야 한다. |
| tool contract 명확성 | 각 tool은 입력, mode, redacted output, allowlist 경계를 보여야 한다. |
| 보안 경계 | arbitrary SQL, live web access, raw prompt persistence를 막아야 한다. |
| MCP 확장성 | FastAPI core를 흔들지 않고 MCP server를 thin wrapper로 붙일 수 있어야 한다. |
| 포트폴리오 신호 | 실제 graph state에 tool result가 남고 eval/trace/guardrail에서 검증 가능해야 한다. |

## 후보 비교 (Comparison)

| 기준 | 후보 A: local deterministic tool suite + optional FastMCP scaffold | 후보 B: live web/production DB/MCP를 즉시 도입 | 후보 C: 문서만 pending 유지 |
|---|---|---|---|
| 무비용 재현성 | 높음. local snapshot, in-memory SQLite, in-process API만 사용한다. | 낮음. 외부 API, credential, network 상태에 의존한다. | 높음. 하지만 기능 증거가 없다. |
| tool contract 명확성 | 높음. `agentic_tools.py`가 세 tool contract를 고정한다. | 중간. provider별 응답 shape가 흔들릴 수 있다. | 낮음. 구현 surface가 없다. |
| 보안 경계 | 높음. query text/raw request를 output에 남기지 않고 SQL은 query_id allowlist, read-only policy, row/timeout budget만 허용한다. | 낮음에서 중간. live connector별 보안 검토가 필요하다. | 높음. 실행 surface가 없기 때문이다. |
| MCP 확장성 | 중간. FastMCP server file과 optional extra 경로를 둔다. | 높음. 실제 server smoke까지 가능하다. | 낮음. MCP 구현이 없다. |
| 포트폴리오 신호 | 중간에서 높음. graph node, summary artifact, tests가 남는다. | 높음. 하지만 운영 리스크가 크다. | 낮음. pending claim만 남는다. |

## 결정 (Decision)

후보 A를 채택한다.

- graph에 `run_tool_suite` node를 추가한다.
- 기본 planned tools는 `document_retrieval`, `web_search`, `sql_query`,
  `internal_api`, `citation_builder`, `guardrail_check`, `generation_workflow`
  7개로 확장한다.
- `web_search`는 local curated snapshot summary로 시작한다.
- live web search runtime policy는 credential 없이 first gate로 기록한다:
  provider type `search_api`/`mcp_web_search`, raw query/user input/secret
  redaction, domain allowlist, max results, timeout, citation requirement, raw
  HTML non-retention을 고정한다.
- `sql_query`는 in-memory SQLite와 query_id allowlist만 허용하고, raw SQL
  입력, mutation statement, unlimited row scan을 금지하는 read-only policy
  summary를 반환한다.
- production DB access/audit policy는 credential 없이 first gate로 기록한다:
  required role `agentic_rag_readonly`, private network 또는 tunnel requirement,
  SSL required, query-id allowlist, row limit, statement timeout, redacted audit
  event fields만 허용한다.
- `internal_api`는 in-process `preview_generation_policy` contract로 시작한다.
- MCP는 `mcp_servers/dessert_ad_studio_server.py` FastMCP server와 `mcp`
  dependency로 둔다. 기본 CI에서 package import와 local tool-call smoke를
  실행한다. Served transport first gate는 loopback-only `streamable-http`
  policy와 manual command를 기록한다. Production auth provider와 remote
  client smoke는 별도 evidence로 남긴다.

## 결과 및 재평가 조건 (Consequences)

- 이 선택으로 감수하는 것:
  - web search 실행은 live search가 아니라 local snapshot이다. Live provider
    selection과 smoke는 아직 사용자 결정이 필요하지만, runtime-security policy
    first gate는 proven이다.
  - SQL query는 production DB가 아니라 allowlisted SQLite proof다. 다만
    read-only, raw SQL disabled, mutation disabled, row limit, timeout budget
    policy는 local first gate로 증명한다.
  - production DB access/audit은 policy first gate만 proven이다. Credentialed
    connection smoke, production audit store, approved retention duration,
    user/project/entity retention scope는 아직 사용자 결정이 필요하다.
  - MCP server는 local import/tool-call smoke와 loopback-only served
    transport/auth boundary까지만 proven이다. Production auth provider와 remote
    client contract는 별도 evidence가 필요하다.
- 재평가 트리거:
  - MCP tool server를 served transport demo에 포함해야 할 때.
  - production DB credential, DB role, audit, retention policy가 정해질 때.
  - live web search provider 비용/retention/allowlist 기준이 정해질 때.
  - tool result가 trace/log/eval artifact에서 raw request leakage를 일으킬 때.
