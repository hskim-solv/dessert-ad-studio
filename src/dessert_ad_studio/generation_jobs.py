from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import hashlib
from threading import Lock
from typing import Any, Protocol

from dessert_ad_studio.schemas import GenerationRequest, GenerationResponse

JOB_STATUS_QUEUED = "queued"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_SUCCEEDED = "succeeded"
JOB_STATUS_FAILED = "failed"

_GENERATION_JOBS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS generation_jobs (
    job_id text PRIMARY KEY,
    status text NOT NULL,
    queue_backend text NOT NULL,
    queue_job_id text,
    request_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    response_summary jsonb,
    error_detail text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz
);

CREATE INDEX IF NOT EXISTS generation_jobs_status_created_at_idx
    ON generation_jobs (status, created_at DESC);
"""


@dataclass(frozen=True)
class GenerationJobRecord:
    job_id: str
    status: str
    queue_backend: str
    request_summary: dict[str, Any]
    response_summary: dict[str, Any] | None = None
    error_detail: str | None = None
    queue_job_id: str | None = None
    created_at: str = field(default_factory=lambda: _utc_now().isoformat())
    updated_at: str = field(default_factory=lambda: _utc_now().isoformat())
    started_at: str | None = None
    finished_at: str | None = None

    def to_status_response(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "queue_backend": self.queue_backend,
            "queue_job_id": self.queue_job_id,
            "request_summary": self.request_summary,
            "response_summary": self.response_summary,
            "error_detail": self.error_detail,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class GenerationJobStore(Protocol):
    name: str

    def create_job(
        self,
        job_id: str,
        request_summary: dict[str, Any],
        *,
        queue_backend: str,
    ) -> GenerationJobRecord: ...

    def set_queue_job_id(self, job_id: str, queue_job_id: str) -> GenerationJobRecord: ...

    def mark_running(self, job_id: str) -> GenerationJobRecord: ...

    def mark_succeeded(
        self,
        job_id: str,
        response_summary: dict[str, Any],
    ) -> GenerationJobRecord: ...

    def mark_failed(self, job_id: str, error_detail: str) -> GenerationJobRecord: ...

    def get_job(self, job_id: str) -> GenerationJobRecord | None: ...


class InMemoryGenerationJobStore:
    name = "memory"

    def __init__(self) -> None:
        self._records: dict[str, GenerationJobRecord] = {}
        self._lock = Lock()

    def create_job(
        self,
        job_id: str,
        request_summary: dict[str, Any],
        *,
        queue_backend: str,
    ) -> GenerationJobRecord:
        with self._lock:
            record = GenerationJobRecord(
                job_id=job_id,
                status=JOB_STATUS_QUEUED,
                queue_backend=queue_backend,
                request_summary=dict(request_summary),
            )
            self._records[job_id] = record
            return record

    def set_queue_job_id(self, job_id: str, queue_job_id: str) -> GenerationJobRecord:
        return self._update(job_id, queue_job_id=queue_job_id)

    def mark_running(self, job_id: str) -> GenerationJobRecord:
        now = _utc_now().isoformat()
        return self._update(job_id, status=JOB_STATUS_RUNNING, started_at=now)

    def mark_succeeded(
        self,
        job_id: str,
        response_summary: dict[str, Any],
    ) -> GenerationJobRecord:
        now = _utc_now().isoformat()
        return self._update(
            job_id,
            status=JOB_STATUS_SUCCEEDED,
            response_summary=dict(response_summary),
            error_detail=None,
            finished_at=now,
        )

    def mark_failed(self, job_id: str, error_detail: str) -> GenerationJobRecord:
        now = _utc_now().isoformat()
        return self._update(
            job_id,
            status=JOB_STATUS_FAILED,
            error_detail=_truncate(error_detail, 300),
            finished_at=now,
        )

    def get_job(self, job_id: str) -> GenerationJobRecord | None:
        with self._lock:
            return self._records.get(job_id)

    def _update(self, job_id: str, **changes: Any) -> GenerationJobRecord:
        with self._lock:
            record = self._records[job_id]
            updated = replace(record, updated_at=_utc_now().isoformat(), **changes)
            self._records[job_id] = updated
            return updated


class PostgresGenerationJobStore:
    name = "postgres"

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise RuntimeError("GENERATION_HISTORY_DSN is required for postgres job history")
        self._dsn = dsn
        self._ensure_schema()

    def create_job(
        self,
        job_id: str,
        request_summary: dict[str, Any],
        *,
        queue_backend: str,
    ) -> GenerationJobRecord:
        from psycopg.types.json import Jsonb

        self._execute(
            """
            INSERT INTO generation_jobs (job_id, status, queue_backend, request_summary)
            VALUES (%s, %s, %s, %s)
            """,
            (job_id, JOB_STATUS_QUEUED, queue_backend, Jsonb(request_summary)),
        )
        record = self.get_job(job_id)
        if record is None:
            raise RuntimeError("generation job history insert failed")
        return record

    def set_queue_job_id(self, job_id: str, queue_job_id: str) -> GenerationJobRecord:
        return self._update_and_get(
            """
            UPDATE generation_jobs
            SET queue_job_id = %s, updated_at = now()
            WHERE job_id = %s
            """,
            (queue_job_id, job_id),
        )

    def mark_running(self, job_id: str) -> GenerationJobRecord:
        return self._update_and_get(
            """
            UPDATE generation_jobs
            SET status = %s, started_at = COALESCE(started_at, now()), updated_at = now()
            WHERE job_id = %s
            """,
            (JOB_STATUS_RUNNING, job_id),
        )

    def mark_succeeded(
        self,
        job_id: str,
        response_summary: dict[str, Any],
    ) -> GenerationJobRecord:
        from psycopg.types.json import Jsonb

        return self._update_and_get(
            """
            UPDATE generation_jobs
            SET status = %s,
                response_summary = %s,
                error_detail = NULL,
                finished_at = now(),
                updated_at = now()
            WHERE job_id = %s
            """,
            (JOB_STATUS_SUCCEEDED, Jsonb(response_summary), job_id),
        )

    def mark_failed(self, job_id: str, error_detail: str) -> GenerationJobRecord:
        return self._update_and_get(
            """
            UPDATE generation_jobs
            SET status = %s,
                error_detail = %s,
                finished_at = now(),
                updated_at = now()
            WHERE job_id = %s
            """,
            (JOB_STATUS_FAILED, _truncate(error_detail, 300), job_id),
        )

    def get_job(self, job_id: str) -> GenerationJobRecord | None:
        rows = self._fetch(
            """
            SELECT job_id, status, queue_backend, request_summary, response_summary,
                   error_detail, queue_job_id, created_at, updated_at, started_at,
                   finished_at
            FROM generation_jobs
            WHERE job_id = %s
            """,
            (job_id,),
        )
        if not rows:
            return None
        return _record_from_row(rows[0])

    def _ensure_schema(self) -> None:
        self._execute(_GENERATION_JOBS_SCHEMA_SQL, ())

    def _update_and_get(self, sql: str, params: tuple[Any, ...]) -> GenerationJobRecord:
        self._execute(sql, params)
        job_id = params[-1]
        record = self.get_job(str(job_id))
        if record is None:
            raise KeyError(str(job_id))
        return record

    def _execute(self, sql: str, params: tuple[Any, ...]) -> None:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg is required for postgres job history") from exc

        try:
            with psycopg.connect(self._dsn) as conn:
                conn.execute(sql, params)
                conn.commit()
        except psycopg.Error as exc:
            raise RuntimeError(
                f"generation job history is not ready: {exc.__class__.__name__}"
            ) from exc

    def _fetch(self, sql: str, params: tuple[Any, ...]) -> list[tuple[Any, ...]]:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg is required for postgres job history") from exc

        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, params)
                    return list(cursor.fetchall())
        except psycopg.Error as exc:
            raise RuntimeError(
                f"generation job history is not ready: {exc.__class__.__name__}"
            ) from exc


class GenerationJobQueueError(RuntimeError):
    pass


def redacted_request_summary(request: GenerationRequest) -> dict[str, Any]:
    return {
        "campaign_purpose": request.campaign_purpose,
        "tone": request.tone,
        "template_hint": request.template_hint,
        "has_price_text": bool(request.price_text),
        "has_user_constraints": bool(request.user_constraints),
        "has_reference_image": bool(request.reference_image_b64),
        "has_reference_image_name": bool(request.reference_image_name),
        "product_name_sha256": hashlib.sha256(request.product_name.encode("utf-8")).hexdigest(),
    }


def redacted_response_summary(response: GenerationResponse) -> dict[str, Any]:
    return {
        "copy_options_count": len(response.copy_options),
        "selected_template": response.selected_template.template_name,
        "template_scorer": response.selected_template.scorer,
        "has_image_path": bool(response.image_path),
        "image_path_sha256": hashlib.sha256(response.image_path.encode("utf-8")).hexdigest()
        if response.image_path
        else None,
        "image_backend": response.image_backend,
        "copy_backend": response.copy_backend,
        "used_reference": response.used_reference,
        "elapsed_ms": response.elapsed_ms,
        "product_analysis_backend": response.product_analysis.analyzer_backend,
        "marketing_context_backend": response.marketing_context.retriever_backend,
        "marketing_context_categories": list(response.marketing_context.guide_categories),
        "marketing_context_retrieved_docs_count": response.marketing_context.retrieved_docs_count,
    }


def enqueue_generation_job(
    *,
    job_id: str,
    request: GenerationRequest,
    queue_backend: str,
    redis_url: str,
    queue_name: str,
    result_ttl_seconds: int,
    failure_ttl_seconds: int,
) -> str | None:
    payload = request.model_dump(mode="json")
    if queue_backend == "inline":
        try:
            run_generation_job(job_id, payload)
        except Exception:
            pass
        return None

    if queue_backend != "rq":
        raise GenerationJobQueueError(f"unknown generation queue backend: {queue_backend}")

    try:
        from redis import Redis
        from rq import Queue
    except ImportError as exc:
        raise GenerationJobQueueError(
            "redis and rq are required for GENERATION_QUEUE_BACKEND=rq"
        ) from exc

    try:
        queue = Queue(queue_name, connection=Redis.from_url(redis_url))
        job = queue.enqueue(
            run_generation_job,
            job_id,
            payload,
            result_ttl=result_ttl_seconds,
            failure_ttl=failure_ttl_seconds,
            description=f"Dessert Ad Studio generation job {job_id}",
            meta={"source": "api", "payload_policy": "transient-no-reference-image"},
        )
    except Exception as exc:
        raise GenerationJobQueueError(
            f"generation queue is not ready: {exc.__class__.__name__}"
        ) from exc
    return str(job.id)


def run_generation_job(job_id: str, request_payload: dict[str, Any]) -> dict[str, str]:
    from api import main as api_main
    from dessert_ad_studio.backends.base import AdBackendError
    from dessert_ad_studio.reference_image import ReferenceImageError

    store = api_main.get_generation_job_store()
    store.mark_running(job_id)
    request = GenerationRequest.model_validate(request_payload)

    try:
        output = api_main.run_generation_workflow(
            request,
            api_main.build_workflow_dependencies(request),
        )
    except (AdBackendError, ReferenceImageError, RuntimeError) as exc:
        store.mark_failed(job_id, _redacted_error_detail(exc))
        raise
    except Exception as exc:
        store.mark_failed(job_id, f"Generation job failed: {exc.__class__.__name__}")
        raise

    store.mark_succeeded(job_id, redacted_response_summary(output.response))
    return {"job_id": job_id, "status": JOB_STATUS_SUCCEEDED}


def _record_from_row(row: tuple[Any, ...]) -> GenerationJobRecord:
    (
        job_id,
        status,
        queue_backend,
        request_summary,
        response_summary,
        error_detail,
        queue_job_id,
        created_at,
        updated_at,
        started_at,
        finished_at,
    ) = row
    return GenerationJobRecord(
        job_id=job_id,
        status=status,
        queue_backend=queue_backend,
        request_summary=dict(request_summary or {}),
        response_summary=dict(response_summary) if response_summary is not None else None,
        error_detail=error_detail,
        queue_job_id=queue_job_id,
        created_at=_isoformat(created_at),
        updated_at=_isoformat(updated_at),
        started_at=_isoformat(started_at) if started_at is not None else None,
        finished_at=_isoformat(finished_at) if finished_at is not None else None,
    )


def _redacted_error_detail(exc: Exception) -> str:
    detail = getattr(exc, "detail", None)
    if not detail:
        detail = str(exc) or exc.__class__.__name__
    return _truncate(str(detail).replace("\n", " "), 300)


def _truncate(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 3] + "..."


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)
