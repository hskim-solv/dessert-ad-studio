# 0014. Agentic RAG Durable Checkpointer

- 날짜: 2026-06-17
- 상태: 채택됨

## 배경 (Context)

Agentic RAG control plane은 ADR 0012에서 LangGraph `StateGraph`와
`InMemorySaver`로 첫 증거를 만들었다. 그러나 최종 산출물은
SQLite/Postgres checkpointer를 요구하며, run replay, HITL 승인(audit), 실패
분석을 주장하려면 node 사이 상태가 프로세스 종료 뒤에도 남아야 한다.

민감정보 정책상 checkpoint에는 raw product name, raw prompt, reference image,
provider response를 저장하지 않는다. `build_agentic_rag_initial_state`는
`request_summary`에 hash/boolean/safe retrieval term만 저장하고, worker result도
allowlist summary만 저장한다. SQLite 파일은 기본 local/dev/demo artifact로
`outputs/agentic-rag-checkpoints/` 아래에 두며 gitignored 상태를 유지한다. 보존은
수동 삭제 또는 demo cleanup 기준이고, 고객/운영 데이터의 장기 보존 저장소로 쓰지
않는다.

## 선택 기준 (Criteria)

- 목표 정합성: 최종 목표의 SQLite/Postgres checkpoint 요구를 직접 충족해야 한다.
- 로컬 재현성: GitHub Actions와 로컬 smoke에서 cloud/service 없이 실행되어야 한다.
- LangGraph 호환성: `thread_id`, checkpoint list/replay, HITL 확장 경로를 유지해야 한다.
- 민감정보 통제: raw inputs가 checkpoint DB에 들어가지 않는지 테스트할 수 있어야 한다.
- 운영 확장성: 나중에 Postgres로 올릴 때 API와 state schema를 크게 바꾸지 않아야 한다.

## 후보 비교 (Comparison)

| 기준 | `InMemorySaver` 유지 | SQLite `SqliteSaver` | Postgres checkpointer | Custom JSONL checkpoint |
|---|---|---|---|---|
| 목표 정합성 | 낮음. checkpoint proof는 되지만 durable이 아님 | 높음. SQLite 요구를 직접 충족 | 높음. 운영형 durable store | 중간. durable file은 가능하지만 LangGraph 표준 checkpoint가 아님 |
| 로컬 재현성 | 높음 | 높음. 별도 service 불필요 | 중간. DB/container/DSN 필요 | 높음 |
| LangGraph 호환성 | 높음 | 높음. `langgraph-checkpoint-sqlite` 표준 saver | 높음. Postgres saver 표준 경로 | 낮음. replay/list semantics 직접 구현 필요 |
| 민감정보 통제 | 테스트 쉬움 | 파일 byte scan과 reopened list로 검증 가능 | DB inspection 필요, 운영 보안 정책 선행 필요 | 직접 통제 가능하지만 표준성 낮음 |
| 운영 확장성 | 낮음 | 중간. schema/state contract를 Postgres로 재사용 가능 | 높음 | 낮음 |
| 도입 비용 | 없음 | 낮음. Python dependency 하나 | 중간. service/storage policy 필요 | 중간. 자체 구현과 유지보수 필요 |

## 결정 (Decision)

첫 durable gate는 `langgraph-checkpoint-sqlite`의 SQLite `SqliteSaver`로 구현한다.

선택 이유는 SQLite가 최종 목표의 SQLite/Postgres 범위를 직접 만족하면서도, 새 cloud
service나 broad retention 결정을 요구하지 않고 로컬/CI에서 바로 재현되기 때문이다.
Postgres checkpointer는 run history, 승인 audit, multi-instance worker 운영까지 묶어
검증할 때 별도 ADR로 재평가한다.

## 결과 및 재평가 조건 (Consequences)

- 이 선택으로 감수하는 것:
  - SQLite는 multi-writer production store가 아니므로 운영 배포의 최종 저장소라고
    주장하지 않는다.
  - checkpoint DB는 local/dev/demo artifact이며 raw 입력 저장 금지 테스트를 유지한다.
  - long-running replay UX와 reviewer approval audit은 별도 milestone에서 완성한다.
- 재평가 트리거:
  - FastAPI worker가 multi-process/multi-instance로 운영된다.
  - 승인 이력(audit)을 사용자/조직 단위로 보존해야 한다.
  - cloud deploy evidence에서 persistent volume 또는 managed DB가 필요해진다.
  - checkpoint row에 raw prompt, image, provider response가 들어가는 회귀가 발견된다.
