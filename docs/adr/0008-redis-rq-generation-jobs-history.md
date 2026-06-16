# 0008. Redis/RQ Generation Jobs And Postgres History

- 날짜: 2026-06-15
- 상태: 채택됨

## 배경 (Context)

M1/M2에서 retrieval baseline과 `pgvector_hybrid` lane은 측정 가능한 증거를
갖췄다. 다음 병목은 이미지 생성이 느리거나 실패할 때 `/generate` 동기 호출만으로는
사용자 경험과 운영 증거가 약하다는 점이다.

M3 Service workflow hardening은 다음을 요구한다.

- `202 Accepted -> job status polling -> result summary` 흐름
- slow image generation을 API request lifecycle 밖으로 분리
- 실패/재시도/worker 상태를 검증 가능한 구조로 노출
- generation history를 남기되 raw photo, raw prompt, raw model response, secrets는
  durable storage에 저장하지 않음

## 선택 기준 (Criteria)

- Portfolio signal: Korean AI backend/RAG 공고에서 반복되는 async job, Redis,
  backend operation 신호를 보여준다.
- Scope control: 현재 FastAPI workflow를 크게 재작성하지 않는다.
- Testability: Redis/Postgres 없이도 API contract를 테스트할 수 있어야 한다.
- Operational realism: local Docker Compose에서 Redis worker와 Postgres history를
  실제로 띄울 수 있어야 한다.
- Data policy: raw reference image, raw prompt, generated copy, full model response,
  secrets는 durable history에 남기지 않는다.
- Upgrade path: retries, artifact storage, object storage, authenticated user history로
  확장 가능해야 한다.

## 후보 비교 (Comparison)

| 기준 | FastAPI BackgroundTasks + Postgres | Redis/RQ + Postgres | Celery + Redis/Postgres |
|---|---|---|---|
| Portfolio signal | Basic async API signal only. | Strong enough Redis/job worker/backend ops signal. | Strong production queue signal. |
| Scope control | Smallest code change. | Moderate; one Redis service and worker entrypoint. | Largest config and operational surface. |
| Testability | Very good, but less realistic. | Good with inline queue adapter for tests. | Good but heavier fixtures/mocking. |
| Operational realism | Weak on process restart, retry, worker separation. | Good for local worker, queue depth, failure states. | Strong but overbuilt for current service size. |
| Data policy | Easy to keep only redacted DB history. | Redis stores transient job payload; Postgres stores redacted history. | Same policy burden as RQ with more moving parts. |
| Upgrade path | Limited once image generation grows. | Enough for retries, job status, worker smoke evidence. | Best for complex routing/scheduling later. |

## 결정 (Decision)

Adopt Redis/RQ for transient generation jobs and Postgres for redacted generation
history.

The deciding factor is portfolio sharpness without overbuilding. RQ gives a
clear worker/queue boundary for slow generation, while Postgres history connects
to the existing pgvector/Postgres operational story.

Implementation defaults:

- API supports a test/local `inline` queue backend and a Docker `rq` backend.
- Docker Compose runs Redis without durable persistence.
- RQ stores transient job payloads only long enough to execute jobs and retain
  short-lived status/result metadata.
- Postgres stores redacted request/response summaries, status, timestamps, and
  failure details.
- Async job API rejects `reference_image_b64` until object-storage retention and
  deletion policy are explicitly chosen.

## Storage, Retention, And Scope

- Redis location: project-local Docker service `redis`; no named volume.
- Redis persistence: disabled with `--save "" --appendonly no`.
- Redis retention: result TTL defaults to 1 hour; failed-job TTL defaults to 24
  hours; values are configurable via environment.
- Redis data scope: transient `GenerationRequest` payload needed to execute a
  job. Reference images are rejected, so raw image bytes are not queued.
- Postgres location: project-local `pgvector` service database
  `dessert_ad_studio`.
- Postgres table: `generation_jobs`.
- Postgres data scope: job id, status, redacted request summary, redacted
  response summary, redacted failure detail, timestamps, and queue metadata.
- Excluded from Postgres history: raw reference images, raw prompt text,
  `user_constraints`, generated copy text, full `GenerationResponse`, full model
  responses, API keys, and secrets.
- Project scope: this queue/history stack belongs only to Dessert Ad Studio; it
  is not a global daemon and not cross-project memory.

## 결과 및 재평가 조건 (Consequences)

- 이 선택으로 감수하는 것:
  - Redis becomes a runtime dependency for the Docker async path.
  - RQ job payloads are transient but still contain request fields required for
    execution; Redis persistence remains disabled.
  - Reference-image async generation is deferred until artifact/object storage is
    designed.
- 재평가 트리거:
  - Need multi-queue routing, scheduled retries, rate limiting, or complex
    orchestration beyond RQ.
  - Need durable queued payloads across Redis restarts.
  - Need reference-image async jobs, which requires explicit object storage,
    retention, and deletion policy.
  - Need user-authenticated history or multi-tenant data isolation.

## Source Notes

- RQ creates queues from a Redis connection, enqueues Python callables, and runs
  workers either via CLI or programmatic `Worker(...).work()`.
- RQ supports synchronous queues (`is_async=False`) for tests, but this project
  uses an explicit inline adapter for deterministic local API tests.
