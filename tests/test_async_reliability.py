from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from dessert_ad_studio.generation_jobs import InMemoryGenerationJobStore

client = TestClient(app)


class RecordingJobStore(InMemoryGenerationJobStore):
    def __init__(self) -> None:
        super().__init__()
        self.created_job_ids: list[str] = []

    def create_job(self, job_id: str, request_summary: dict, *, queue_backend: str):
        self.created_job_ids.append(job_id)
        return super().create_job(job_id, request_summary, queue_backend=queue_backend)


def base_payload(index: int = 0) -> dict:
    return {
        "campaign_purpose": "new_menu",
        "product_name": f"비공개 말차 푸딩 {index}",
        "tone": "clean",
        "template_hint": "minimal_premium",
        "price_text": "5,500원",
        "user_constraints": "VIP 고객에게만 보일 문구",
    }


def configure_inline_jobs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> RecordingJobStore:
    import api.main as api_main

    store = RecordingJobStore()
    monkeypatch.setattr(api_main, "get_generation_job_store", lambda: store)
    monkeypatch.setenv("GENERATION_QUEUE_BACKEND", "inline")
    monkeypatch.setenv("GENERATION_HISTORY_BACKEND", "memory")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("GENERATION_LOG_PATH", str(tmp_path / "generations.jsonl"))
    monkeypatch.setenv("REQUIRE_TRITON", "0")
    return store


def test_inline_generation_jobs_handle_burst_and_keep_status_redacted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_inline_jobs(monkeypatch, tmp_path)

    created = [client.post("/generation-jobs", json=base_payload(i)) for i in range(5)]

    assert [response.status_code for response in created] == [202] * 5
    for response in created:
        accepted = response.json()
        status = client.get(accepted["status_url"]).json()
        serialized = str(status)
        assert status["status"] == "succeeded"
        assert status["queue_backend"] == "inline"
        assert status["response_summary"]["copy_options_count"] == 3
        assert "비공개 말차 푸딩" not in serialized
        assert "VIP 고객" not in serialized
        assert "copy_options" not in status["response_summary"]
        assert "prompt_summary" not in status["response_summary"]


def test_inline_generation_job_failure_records_failed_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main
    from dessert_ad_studio.backends.base import AdBackendError

    configure_inline_jobs(monkeypatch, tmp_path)

    def fail_workflow(*args, **kwargs):
        raise AdBackendError("이미지 생성 API 호출에 실패했습니다: provider unavailable")

    monkeypatch.setattr(api_main, "run_generation_workflow", fail_workflow)

    response = client.post("/generation-jobs", json=base_payload())

    assert response.status_code == 202
    accepted = response.json()
    assert accepted["status"] == "failed"
    status = client.get(accepted["status_url"]).json()
    assert status["status"] == "failed"
    assert status["response_summary"] is None
    assert status["error_detail"] == "이미지 생성 API 호출에 실패했습니다: provider unavailable"


def test_generation_job_queue_failure_marks_created_job_failed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main

    store = configure_inline_jobs(monkeypatch, tmp_path)
    monkeypatch.setenv("GENERATION_QUEUE_BACKEND", "rq")

    def fail_enqueue(**kwargs):
        raise api_main.GenerationJobQueueError("generation queue is not ready: ConnectionError")

    monkeypatch.setattr(api_main, "enqueue_generation_job", fail_enqueue)

    response = client.post("/generation-jobs", json=base_payload())

    assert response.status_code == 503
    job_id = store.created_job_ids[-1]
    record = store.get_job(job_id)
    assert record is not None
    assert record.status == "failed"
    assert record.error_detail == "generation queue is not ready: ConnectionError"


def test_generation_job_duplicate_polling_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_inline_jobs(monkeypatch, tmp_path)
    accepted = client.post("/generation-jobs", json=base_payload()).json()

    first = client.get(accepted["status_url"]).json()
    second = client.get(accepted["status_url"]).json()

    assert first == second
    assert first["status"] == "succeeded"
