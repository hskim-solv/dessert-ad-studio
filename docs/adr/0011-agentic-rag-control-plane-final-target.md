# 0011. Agentic RAG Control Plane Final Target

- 날짜: 2026-06-17
- 상태: 채택됨

## 배경 (Context)

The portfolio target has moved from a narrow dessert ad generator toward a
senior-level production-grade Agentic RAG system. The project already has
FastAPI, Pydantic contracts, async generation jobs, Redis/RQ, Postgres history,
pgvector retrieval evidence, deterministic evals, Phoenix/OTEL traces, Docker,
Kubernetes smoke evidence, and paid provider-quality failure evidence.

The decision is how to absorb the stronger Agentic RAG requirements without
discarding this evidence or turning the repository into a generic chatbot.

## 선택 기준 (Criteria)

- Portfolio signal: proves the Korean senior AI/backend/RAG/LLMOps hiring
  signals most directly.
- Evidence reuse: preserves already verified deployment, eval, observability,
  privacy, and multimodal workflow evidence.
- Implementation focus: keeps the next milestones concrete and reviewable.
- Overclaim control: keeps proven, failed, and pending scope separated.
- Extensibility: leaves room for MCP, Ragas, promptfoo, SSE, HITL, and cloud
  deploy without making them appear already complete.

## 후보 비교 (Comparison)

| 기준 | A. 새 generic RAG chatbot로 재작성 | B. 현 워크플로우 위 Agentic RAG control plane | C. 기존 image workflow만 유지 |
|---|---|---|---|
| Portfolio signal | RAG 신호는 강하지만 기존 multimodal/ops evidence가 약해짐. | RAG, agent orchestration, backend, eval, observability, deployability를 한 제품 안에서 증명. | Multimodal backend는 보이지만 Agentic RAG/LangGraph 신호가 부족. |
| Evidence reuse | 기존 evidence 대부분이 보조 자료로 밀림. | 기존 evidence가 agent tool/eval/deploy proof로 재사용됨. | 기존 evidence는 보존되지만 새 요구사항 흡수가 어려움. |
| Implementation focus | 새 ingestion/chat/eval surface를 다시 만들어야 함. | LangGraph graph, RAG citation, HITL, streaming을 기존 API/workflow에 추가하면 됨. | provider-quality 실패 remediation에 갇힐 위험. |
| Overclaim control | 새 기능의 proof를 처음부터 다시 쌓아야 함. | proven/pending/failing scope를 현재 문서 구조에 그대로 확장 가능. | Agentic RAG 최종목표와 불일치. |
| Extensibility | MCP/cloud/eval은 가능하지만 도메인 차별성이 약함. | MCP, SQL, web search, document retrieval, internal API tools를 광고 workflow 도구로 자연스럽게 연결. | 확장 시 아키텍처 재정의가 반복됨. |

## 결정 (Decision)

후보 B를 채택한다. 최종 산출물은 `Dessert Ad Studio`를 폐기한 새 RAG
챗봇이 아니라, **small-business ad generation 도메인 위의
Production-grade Agentic RAG workflow**다.

The final system should use an Agentic RAG control plane to retrieve business
evidence, orchestrate tools, enforce guardrails, request human approval, stream
execution state, and produce cited ad assets with eval, trace, cost, failure,
and deployability evidence.

## 결과 및 재평가 조건 (Consequences)

- 이 선택으로 감수하는 것:
  - LangGraph, Ragas, promptfoo, SSE/WebSocket, MCP, and cloud deploy are not
    automatically proven by naming them; each needs implementation evidence.
  - Paid provider-quality image editing remains unproven and must stay framed
    as a failed downstream tool gate until remediated.
  - Further technology adoption still requires focused ADRs before
    implementation when candidates are non-trivial.
- 재평가 트리거:
  - A generic RAG/chat requirement becomes mandatory for a target role and the
    ad workflow weakens the story.
  - LangGraph implementation cannot integrate cleanly with the existing
    FastAPI/job/history/eval surfaces.
  - A cloud deployment target imposes constraints that invalidate the current
    Docker/Kubernetes evidence path.
