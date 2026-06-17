# 0012. LangGraph Agentic RAG Control Plane

- 날짜: 2026-06-17
- 상태: 채택됨

## 배경 (Context)

ADR 0011 sets the final portfolio target as a production-grade Agentic RAG
workflow over the existing small-business ad generation service. The current
workflow is a tested sequential Python pipeline with retrieval, trace,
privacy allowlists, async jobs, and deployment evidence, but it does not yet
prove typed agent state, conditional routing, checkpointing, retry/reflection,
or human-in-the-loop control.

This decision chooses the first orchestration layer for M8. The first slice
must be deterministic, offline, and non-paid. It must not replace the existing
generation workflow until the graph contract is proven.

## 선택 기준 (Criteria)

- Agentic RAG signal: directly proves typed graph state, conditional edges,
  checkpointing, and HITL routing expected in target roles.
- Integration safety: can wrap the existing workflow without rewriting the
  tested FastAPI, queue, retrieval, and image/copy backend contracts.
- Privacy boundary: can keep raw product text, prompts, reference images, and
  file paths out of persisted graph state and evidence artifacts.
- Evaluation fit: supports deterministic smoke tests, CI gates, and later
  Ragas/promptfoo/Phoenix evidence.
- Production path: has a clear route from in-memory local checkpointer to a
  durable SQLite/Postgres checkpointer.
- Dependency cost: adds a real agent framework without introducing paid calls
  or a hosted service.

## 후보 비교 (Comparison)

| 기준 | A. LangGraph StateGraph | B. 기존 custom workflow 확장 | C. LangChain Runnable/custom router |
|---|---|---|---|
| Agentic RAG signal | typed state, conditional edges, checkpointing, HITL/retry patterns를 직접 보여줌. | Python 함수 trace는 명확하지만 agent orchestration 신호가 약함. | Runnable chaining은 가능하지만 graph/checkpoint/HITL 신호가 덜 선명함. |
| Integration safety | 기존 workflow를 worker node 뒤에 둘 수 있어 점진 적용 가능. | 가장 안전하지만 최종 목표의 LangGraph 요구를 만족하지 못함. | 일부 통합은 쉽지만 복잡해질수록 custom 상태 관리가 필요함. |
| Privacy boundary | graph state schema를 redacted summary 중심으로 설계 가능. | 기존 log allowlist는 유지되지만 checkpoint 관점의 privacy proof가 없음. | 직접 잘 만들 수 있으나 framework-level checkpoint/replay story가 약함. |
| Evaluation fit | node trace, route, checkpoint를 pytest/smoke artifact로 검증하기 쉬움. | 현재 테스트와 잘 맞지만 agent eval 확장성이 낮음. | 가능하지만 portfolio reviewer가 구조를 읽기 어려울 수 있음. |
| Production path | InMemorySaver로 local proof, Postgres/SQLite saver로 재평가 가능. | 직접 구현해야 함. | 직접 구현하거나 별도 persistence를 붙여야 함. |
| Dependency cost | 새 Python dependency가 필요하지만 hosted service는 아님. | 새 dependency 없음. | LangChain dependency surface가 넓어질 수 있음. |

## 결정 (Decision)

후보 A, `LangGraph StateGraph`를 M8 control plane의 기본 orchestrator로
채택한다.

The first implementation is deliberately narrow:

- use a typed graph state for redacted request summaries, plan, retrieval
  context, citations, approval decision, worker result summary, reflection
  summary, and node trace
- route through deterministic nodes: plan, retrieve, cite, guardrail, optional
  local worker execution, reflection retry, human approval, and finalize
- use an in-memory checkpointer only for local tests and evidence
- call the existing `run_generation_workflow` only through local mock backends
  in the evidence smoke
- do not call paid providers, web search, external MCP tools, or production
  image/copy providers in this slice
- keep production API/streaming graph wiring for a later milestone

Follow-up decisions:

- ADR 0013 selected SSE as the first run streaming protocol.
- ADR 0014 selected local SQLite `SqliteSaver` as the first durable
  checkpointer gate.

## 결과 및 재평가 조건 (Consequences)

- 이 선택으로 감수하는 것:
  - `langgraph` becomes a runtime dependency and must stay covered by local
    tests and CI.
  - In-memory checkpointing is not a production durability claim.
  - The first graph proves routing, local worker dispatch, redacted worker
    summary, and retry/reflection behavior, not full Ragas, promptfoo, MCP,
    web search, production streaming, or provider-quality image generation.
- 재평가 트리거:
  - LangGraph cannot keep raw customer/product inputs out of persisted state
    without harming core functionality.
  - Checkpointing needs production durability before demo. ADR 0014 covers the
    first local SQLite gate; Postgres or cloud persistent storage still needs
    reevaluation if multi-instance workers or approval audit retention are
    required.
  - The graph integration creates regressions in the existing FastAPI,
    Redis/RQ, generation history, or workflow test suite.
