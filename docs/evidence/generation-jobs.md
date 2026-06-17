# Generation Jobs Evidence

Date: 2026-06-15, updated 2026-06-17

## Scope

This evidence covers the M3 service workflow hardening lane for asynchronous ad
generation jobs.

The implementation adds a job-oriented API on top of the existing synchronous
workflow:

- `POST /generation-jobs` returns HTTP 202 and a status URL.
- `GET /generation-jobs/{job_id}` returns status, redacted request summary, and
  redacted response/failure summary.
- Local tests use `GENERATION_QUEUE_BACKEND=inline` and
  `GENERATION_HISTORY_BACKEND=memory`.
- Docker Compose uses Redis/RQ for transient jobs and Postgres for redacted job
  history.
- Kubernetes async overlay now uses the same Redis/RQ worker and Postgres
  history path for local/test `kind` evidence.

## Local Storage Boundary

- Redis service: `redis`
- Redis persistence: disabled via `redis-server --save "" --appendonly no`
- Redis data: transient job payloads required for execution
- Redis retention: `GENERATION_JOB_RESULT_TTL_SECONDS=3600`,
  `GENERATION_JOB_FAILURE_TTL_SECONDS=86400`
- Worker logging: RQ job description logging is disabled in
  `scripts/run_generation_worker.py`; enqueue also sets a non-sensitive job
  description and metadata.
- Worker import boundary: `scripts/run_generation_worker.py` adds the repo root
  to `sys.path` before processing jobs so the containerized worker can import
  `api.main`.
- Worker healthcheck: Docker Compose overrides the inherited API HTTP
  healthcheck with a Redis ping check for the worker service.
- Postgres service: existing `pgvector` database `dessert_ad_studio`
- Postgres table: `generation_jobs`
- Postgres stored data: job id, status, queue metadata, timestamps, redacted
  request summary, redacted response summary, redacted failure detail
- Excluded from Postgres history: raw reference images, raw product names, raw
  `user_constraints`, generated copy text, prompt summary, model responses,
  raw image paths, secrets, and API keys

Async jobs reject `reference_image_b64` until object storage, retention, and
deletion policy are explicitly selected.

## Commands

Focused tests:

```bash
.venv/bin/pytest tests/test_generation_jobs.py -q
.venv/bin/pytest tests/test_streamlit_jobs.py -q
.venv/bin/pytest \
  tests/test_streamlit_jobs.py \
  tests/test_api.py::test_create_generation_job_runs_inline_and_status_is_redacted \
  tests/test_api.py::test_create_generation_job_rejects_reference_image_payload \
  tests/test_api.py::test_generation_job_status_returns_404_for_unknown_job \
  -q
```

Compose validation:

```bash
docker compose config -q
```

Redis/RQ enqueue + worker smoke:

```bash
docker compose up -d redis pgvector
.venv/bin/python - <<'PY'
import os
import tempfile
from redis import Redis
from rq import Queue, SimpleWorker
from fastapi.testclient import TestClient

os.environ["OUTPUT_DIR"] = tempfile.mkdtemp(prefix="part4-job-smoke-")
os.environ["GENERATION_QUEUE_BACKEND"] = "rq"
os.environ["GENERATION_QUEUE_NAME"] = "ad-generation-smoke-redacted"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["GENERATION_HISTORY_BACKEND"] = "memory"
os.environ["REQUIRE_TRITON"] = "0"

from api import main as api_main

api_main.get_generation_job_store.cache_clear()
redis = Redis.from_url(os.environ["REDIS_URL"])
queue = Queue(os.environ["GENERATION_QUEUE_NAME"], connection=redis)
queue.empty()
client = TestClient(api_main.app)
created = client.post("/generation-jobs", json={
    "campaign_purpose": "new_menu",
    "product_name": "말차 푸딩",
    "tone": "clean",
    "template_hint": "minimal_premium",
    "price_text": "5,500원",
    "user_constraints": "깔끔한 프리미엄 느낌",
}).json()
SimpleWorker([queue], connection=redis, log_job_description=False).work(burst=True)
status = client.get(created["status_url"]).json()
assert status["status"] == "succeeded"
assert status["response_summary"]["copy_options_count"] == 3
assert "product_name" not in status["request_summary"]
assert "user_constraints" not in status["request_summary"]
PY
```

Postgres history smoke:

```bash
.venv/bin/python - <<'PY'
from uuid import uuid4
from dessert_ad_studio.generation_jobs import PostgresGenerationJobStore

store = PostgresGenerationJobStore(
    "postgresql://dessert:dessert_dev_password@localhost:5433/dessert_ad_studio"
)
job_id = "smoke-" + str(uuid4())
store.create_job(job_id, {"campaign_purpose": "new_menu"}, queue_backend="rq")
store.mark_running(job_id)
store.mark_succeeded(job_id, {"copy_options_count": 3, "copy_backend": "mock"})
assert store.get_job(job_id).status == "succeeded"
PY
```

Full Docker API/worker smoke:

```bash
docker compose up -d redis pgvector triton api worker
curl -fsS http://localhost:8080/readyz
API_BASE_URL=http://localhost:8080 .venv/bin/python scripts/generation_job_smoke.py
docker compose logs --tail=80 worker
```

Streamlit UX smoke:

```bash
API_BASE_URL=http://localhost:8080 \
  .venv/bin/streamlit run app/streamlit_app.py \
  --server.port 8501 --server.headless true
bash "$PWCLI" open http://127.0.0.1:8501
bash "$PWCLI" click <광고 생성 button ref>
bash "$PWCLI" click <작업 상태 새로고침 button ref>
bash "$PWCLI" screenshot
```

Status:

- 2026-06-15: attempted, but stopped before API/worker startup because the
  Triton image pull was still in progress after downloading more than 1 GB of
  layers. Redis/RQ and Postgres history were verified separately as shown above.
- 2026-06-16: completed after freeing disk and restarting Docker Desktop. Triton
  pull/extract completed, API and worker images built, API `/readyz` returned
  ready with `generation_history_backend=postgres`,
  `generation_queue_backend=rq`, and
  `template_scorer=triton-template-scorer`.

Container smoke output:

- `scripts/generation_job_smoke.py` returned `status=succeeded`,
  `queue_backend=rq`, `copy_options_count=3`,
  `template_scorer=triton-template-scorer`, `has_image_path=True`, and
  `image_path_sha256` only.
- Additional leak check returned `raw_output_marker_found=0` for exact raw
  `image_path`, `outputs/`, and raw Korean product-name markers.
- Worker log check returned `worker_log_raw_marker_found=0`; logs showed job id,
  completion, and result TTL only.

Streamlit polling/history UX:

- `app/streamlit_app.py` submits no-reference requests through
  `POST /generation-jobs`.
- Uploaded reference-image requests stay on the synchronous `POST /generate`
  path because async jobs intentionally reject raw reference images until object
  storage, retention, and deletion policy are selected.
- The app stores recent job ids in Streamlit session state, polls pending jobs
  through `GET /generation-jobs/{job_id}`, and renders redacted status/history
  summaries without persisting raw generated copy or image paths.
- Playwright verified the no-reference UI flow against the running
  `localhost:8080` API/worker stack: initial caption showed
  `POST /generation-jobs`, the job panel rendered `대기`, and refresh rendered
  `완료 · 문구 3개 · scorer=triton-template-scorer`.
- Screenshot: `output/playwright/streamlit-generation-jobs.png`

## Current Result

Verified on 2026-06-15 and 2026-06-16:

| Check | Result |
|---|---|
| Focused job tests | `tests/test_generation_jobs.py`: `4 passed, 1 warning` |
| Streamlit job UX tests | `tests/test_streamlit_jobs.py`: `3 passed` |
| Focused Streamlit + API job tests | `6 passed` |
| Full test suite | Historical snapshot: `169 passed, 1 warning`. Current checkout regression snapshot is tracked in `docs/evidence/README.md`. |
| Ruff | pass |
| Compose config | pass |
| Redis/RQ enqueue + `SimpleWorker` burst | queued 1 job, processed to `succeeded`, `copy_options_count=3` |
| Worker log redaction | worker logs job id only, not raw request args |
| Postgres history smoke | `queued -> running -> succeeded`, loaded from `generation_jobs` |
| Full Docker API/worker smoke | passed through containerized API + worker with Triton scorer, Redis/RQ queue, and Postgres history |
| Kubernetes async overlay smoke | passed on `kind-dessert-ad-studio`: API ready with `generation_queue_backend=rq`, `generation_history_backend=postgres`, worker/Redis/pgvector pods ready, and `scripts/generation_job_smoke.py` returned `status=succeeded` |

The inline test path proves the API contract and redaction contract without
needing Redis/Postgres fixtures. The Redis/RQ smoke proves the queue adapter and
worker execution path. The Postgres smoke proves schema creation and durable
redacted history lifecycle. The full Docker smoke proves the same path across
container boundaries. The Streamlit tests prove the UI-side job history merge,
status labeling, and redacted summary handling.

## Interpretation

This is the first operationally credible job/status path:

- Slow generation can move out of the direct `/generate` request path.
- Job state is visible through a stable polling endpoint and a Streamlit status
  history panel.
- Durable history remains redacted and does not store raw prompts or generated
  copy.
- Redis/RQ is present as a real worker boundary in Docker Compose, while tests
  stay deterministic through the inline adapter.

The full Docker API/worker smoke with Triton enabled, the Streamlit
polling/history UX, and the Kubernetes async overlay smoke are now complete.
