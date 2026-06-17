# 0013. Agentic RAG Run Streaming Protocol

- 날짜: 2026-06-17
- 상태: 채택됨

## 배경 (Context)

The final Agentic RAG target requires a FastAPI async API that streams graph run
state. The current API has synchronous `/generate`, async job polling through
`/generation-jobs`, and an offline LangGraph control-plane proof. It does not
yet expose graph execution progress as a run stream.

The streaming surface should be local, deterministic, and no-paid for the first
gate. It should preserve the redaction boundary already used by graph evidence:
raw product text, customer constraints, prompt text, reference image bytes, and
raw provider errors must not be streamed or persisted.

## 선택 기준 (Criteria)

- Reviewer fit: a portfolio reviewer can call it with simple HTTP tooling and
  see graph progress.
- Operational simplicity: works through normal HTTP infrastructure and existing
  FastAPI tests without a new dependency.
- Directionality: current need is server-to-client progress events, not
  bidirectional chat control.
- Privacy: event payloads must use allowlisted redacted state only.
- Extensibility: can later add approval decisions, durable run IDs, or a
  WebSocket surface if bidirectional control becomes necessary.

## 후보 비교 (Comparison)

| 기준 | A. SSE over HTTP | B. WebSocket | C. Polling-only job status |
|---|---|---|---|
| Reviewer fit | `curl`/browser/EventSource style로 확인하기 쉽고 demo evidence가 단순함. | richer demo는 가능하지만 client ceremony가 더 큼. | 이미 job polling이 있어 새 신호가 약함. |
| Operational simplicity | FastAPI `StreamingResponse`로 구현 가능, 새 dependency 없음. | connection lifecycle, heartbeat, proxy timeout 처리가 더 필요함. | 가장 단순하지만 streaming requirement를 충족하지 못함. |
| Directionality | one-way graph progress에 정확히 맞음. | bidirectional approval/chat에는 강함. | 실시간성이 약함. |
| Privacy | allowlisted event payload만 stream하면 됨. | 동일하게 가능하지만 message types가 늘어날 가능성. | status snapshot만 보이므로 안전하지만 정보량이 부족. |
| Extensibility | approval event와 run id를 추가하기 쉬움. | 향후 HITL 실시간 approval에는 재평가 가치가 있음. | LangGraph node-level trace 표현이 불편함. |

## 결정 (Decision)

후보 A, **SSE over HTTP**를 첫 Agentic RAG run streaming protocol로 채택한다.

The first endpoint should:

- be an `async` FastAPI route
- return `text/event-stream`
- emit only allowlisted JSON event payloads
- stream the current offline graph route without paid providers
- include graph node progress, approval-required status, local mock worker
  completion, citations/checkpoint counts, and final status
- keep WebSocket as a later option only if reviewer approval needs
  bidirectional, low-latency interaction

## 결과 및 재평가 조건 (Consequences)

- 이 선택으로 감수하는 것:
  - SSE is one-way. It does not yet solve bidirectional human approval input.
  - The first stream is not durable run replay; it is a live local execution
    evidence surface.
  - Production run storage and resume still need durable checkpointing.
- 재평가 트리거:
  - HITL approval requires interactive client-to-server decisions inside a
    live stream.
  - Browser/proxy constraints make SSE unreliable for the deployment target.
  - Durable run resume becomes more important than live progress display.
