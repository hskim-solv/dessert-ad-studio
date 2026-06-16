from __future__ import annotations

from app import streamlit_app
from dessert_ad_studio.schemas import GenerationRequest


def sample_request(product_name: str = "말차 푸딩") -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="new_menu",
        product_name=product_name,
        tone="clean",
        template_hint="minimal_premium",
        price_text="5,500원",
        user_constraints="프리미엄 느낌",
    )


def test_upsert_generation_job_adds_newest_first_and_updates_existing() -> None:
    request = sample_request()
    jobs = streamlit_app._upsert_generation_job(
        [],
        request,
        {
            "job_id": "job-1",
            "status": "queued",
            "status_url": "/generation-jobs/job-1",
            "queue_backend": "rq",
        },
    )

    assert jobs[0]["job_id"] == "job-1"
    assert jobs[0]["status"] == "queued"
    assert jobs[0]["request"]["product_name"] == "말차 푸딩"

    jobs = streamlit_app._upsert_generation_job(
        jobs,
        request,
        {
            "job_id": "job-1",
            "status": "running",
            "status_url": "/generation-jobs/job-1",
            "queue_backend": "rq",
        },
    )

    assert len(jobs) == 1
    assert jobs[0]["status"] == "running"


def test_merge_generation_job_status_preserves_request_and_redacted_summary() -> None:
    request = sample_request()
    jobs = streamlit_app._upsert_generation_job(
        [],
        request,
        {
            "job_id": "job-1",
            "status": "queued",
            "status_url": "/generation-jobs/job-1",
            "queue_backend": "rq",
        },
    )

    updated = streamlit_app._merge_generation_job_status(
        jobs[0],
        {
            "job_id": "job-1",
            "status": "succeeded",
            "queue_backend": "rq",
            "queue_job_id": "rq-1",
            "response_summary": {
                "copy_options_count": 3,
                "template_scorer": "triton-template-scorer",
                "has_image_path": True,
                "image_path_sha256": "a" * 64,
            },
            "error_detail": None,
            "created_at": "2026-06-16T00:00:00+00:00",
            "updated_at": "2026-06-16T00:00:01+00:00",
            "started_at": "2026-06-16T00:00:00+00:00",
            "finished_at": "2026-06-16T00:00:01+00:00",
        },
    )

    assert updated["request"]["product_name"] == "말차 푸딩"
    assert updated["status"] == "succeeded"
    assert updated["response_summary"]["copy_options_count"] == 3
    assert "copy_options" not in updated["response_summary"]
    assert "image_path" not in updated["response_summary"]


def test_generation_job_status_helpers() -> None:
    assert streamlit_app._is_generation_job_pending({"status": "queued"}) is True
    assert streamlit_app._is_generation_job_pending({"status": "running"}) is True
    assert streamlit_app._is_generation_job_pending({"status": "succeeded"}) is False
    assert streamlit_app._generation_job_status_label("failed") == "실패"
