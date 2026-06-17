# Async Reliability Matrix Evidence

Date: 2026-06-17

## Scope

This evidence covers the first reliability matrix for the generation job path:
API acceptance, status polling, failure state, queue enqueue failure, worker
startup, and K8s async overlay smoke.

This is not a production queue reliability claim. Retry, timeout, cancellation,
dead-letter handling, and multi-worker failure injection remain pending.

## Command

```bash
.venv/bin/pytest \
  tests/test_async_reliability.py \
  tests/test_generation_jobs.py::test_generation_worker_waits_for_redis_until_ready \
  -q
```

Result:

```text
5 passed, 1 warning
```

The machine-readable summary is stored at
`docs/evidence/async-reliability-matrix.json`.

## Matrix

| Case | Status | Evidence |
|---|---|---|
| Burst submit | Passed | 5 inline jobs returned `succeeded` and redacted summaries. |
| Workflow failure state | Passed | Accepted job moved to `failed`, with `response_summary=null` and a bounded user-facing `error_detail`. |
| Queue enqueue failure | Passed | Queue failure returned HTTP 503 and marked the created job `failed`. |
| Duplicate polling | Passed | Two `GET /generation-jobs/{job_id}` calls returned identical status payloads. |
| Worker starts before Redis | Passed | Worker waits for Redis readiness before constructing the RQ Worker; K8s worker restarted with `restartCount=0` after the fix. |
| K8s async path | Passed | `kind` async overlay smoke passed Redis/RQ worker plus Postgres history. |
| Reference-image async payload | Explicit non-support | `POST /generation-jobs` rejects `reference_image_b64` until object storage and retention policy are selected. |
| Cancel endpoint | Not supported | No cancellation API is claimed yet. |
| Retry/timeout policy | Pending | Needs live worker failure injection, retry policy, and timeout/dead-letter evidence. |

## Privacy Boundary

The matrix artifacts do not persist raw product names, raw user constraints,
generated copy text, prompt summaries, raw reference images, or raw image paths.
