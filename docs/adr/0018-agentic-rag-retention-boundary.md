# 0018. Agentic RAG Retention Boundary

- 날짜: 2026-06-17
- 상태: 채택됨

## 배경 (Context)

Agentic RAG control plane은 local SQLite replay, HITL approval, reviewer UI,
same-process post-approval worker resume까지 첫 증거를 만들었다. 다음 단계는
production replay retention, approval audit retention, cross-process resume,
external trace retention을 주장할 수 있는지 결정하는 것이다.

하지만 raw product name, raw prompt, raw reviewer comment, reference image,
provider response를 durable storage에 넣는 순간 storage location, retention,
deletion, user/project/entity scope가 필요하다. 이 저장 정책은 broad retention
변경이므로 명시적 사용자 결정 없이 도입하지 않는다.

## 선택 기준 (Criteria)

- 민감정보 통제: raw customer input, reviewer note, prompt, image, provider
  response가 durable artifact에 들어가지 않아야 한다.
- 재현성: CI/local smoke에서 cloud/service 없이 검증 가능해야 한다.
- 포트폴리오 정직성: production claim과 local first gate를 분리해야 한다.
- 운영 확장성: 나중에 Postgres/object storage/external tracing을 붙일 수 있어야
  한다.
- 비용/승인 경계: paid API, cloud, external trace retention은 명시적 승인 전에는
  기본 경로가 아니어야 한다.

## 후보 비교 (Comparison)

| 기준 | 후보 A: redacted replay + ephemeral raw context | 후보 B: durable raw request store | 후보 C: no replay/resume retention |
|---|---|---|---|
| 민감정보 통제 | 높음. SQLite/evidence에는 hash, boolean, status만 남긴다. | 낮음. raw request/comment/image retention 정책이 선행되어야 한다. | 높음. 저장하지 않지만 기능 증거도 약하다. |
| 재현성 | 높음. local/CI에서 summary artifact로 검증 가능하다. | 중간. DB/object storage와 cleanup 정책이 필요하다. | 높음. 추가 runtime 없음. |
| 포트폴리오 정직성 | 높음. local first gate와 production pending을 분리한다. | 중간. 제대로 하면 강하지만 성급하면 overclaim 위험이 크다. | 낮음. 최종 목표의 replay/resume 요구를 설명하지 못한다. |
| 운영 확장성 | 중간. Postgres/audit store로 갈 경계를 보존한다. | 높음. 운영 저장소가 있으면 cross-process resume이 가능하다. | 낮음. 나중에 다시 설계해야 한다. |
| 비용/승인 경계 | 높음. 새 service, paid API, broad retention 없음. | 낮음. 명시적 사용자 결정이 필요하다. | 높음. 리스크는 낮지만 진전이 작다. |

## 결정 (Decision)

`redacted replay + ephemeral raw context`를 채택한다.

현재 production claim은 다음으로 제한한다.

- Local SQLite replay는 redacted checkpoint만 보존한다.
- Approval summary는 reviewer/comment hash와 decision/status metadata만 보존한다.
- Post-approval resume은 same-process ephemeral request context로만 수행한다.
- External trace에는 raw model input, raw image, raw provider response를 저장하지
  않는다.

다음 항목은 사용자 결정 전까지 pending이다.

- durable raw request storage
- cross-process resume store
- production approval audit retention
- external trace payload retention

## 결과 및 재평가 조건 (Consequences)

- 이 선택으로 감수하는 것:
  - API process가 재시작되면 approval 대기 run의 raw request context는 사라진다.
  - durable cross-process resume은 아직 production claim이 아니다.
  - production approval audit retention은 summary-level evidence만 있고 운영 보존
    정책은 없다.
- 재평가 트리거:
  - multi-instance API/worker에서 approval resume을 지원해야 한다.
  - user/project/entity 단위 audit 보존 기간과 삭제 정책이 정해진다.
  - managed Postgres, object storage, external tracing backend를 채택한다.
  - raw request/image/provider response를 보존해야 하는 제품 요구가 생긴다.
