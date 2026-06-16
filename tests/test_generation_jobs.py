from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from dessert_ad_studio.generation_jobs import (
    InMemoryGenerationJobStore,
    redacted_request_summary,
    redacted_response_summary,
)
from dessert_ad_studio.schemas import (
    CopyOption,
    GenerationRequest,
    GenerationResponse,
    MarketingContext,
    ProductAnalysis,
    TemplateRanking,
)


def sample_request() -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="new_menu",
        product_name="말차 푸딩",
        tone="clean",
        template_hint="minimal_premium",
        price_text="5,500원",
        user_constraints="VIP 고객에게만 보일 문구",
        reference_image_name="secret-cake.png",
    )


def sample_response() -> GenerationResponse:
    return GenerationResponse(
        copy_options=[
            CopyOption(headline="비공개 헤드라인", body="비공개 본문", call_to_action="구매하기")
        ],
        selected_template=TemplateRanking(
            template_name="minimal_premium",
            score=0.9,
            scorer="local-template-scorer",
            latency_ms=1.2,
        ),
        image_path="outputs/demo.png",
        image_backend="mock",
        copy_backend="mock",
        used_reference=False,
        prompt_summary="비공개 이미지 프롬프트",
        elapsed_ms=12.3,
        product_analysis=ProductAnalysis(
            label="Product analysis",
            product_context="말차 푸딩 분석",
            ad_goal="신메뉴",
            visual_strategy="프리미엄",
            photo_strategy="참고 이미지 없음",
            copy_focus="깔끔함",
            rendering_strategy="overlay",
            analyzer_backend="mock",
        ),
        marketing_context=MarketingContext(
            retriever_backend="keyword",
            guide_categories=["premium", "prohibited_claims"],
            source_doc_ids=["guide-premium-tone-v1", "guide-ad-claims-safety-v1"],
            retrieved_docs_count=2,
        ),
    )


def test_redacted_request_summary_excludes_raw_prompt_and_product_text() -> None:
    summary = redacted_request_summary(sample_request())

    serialized = str(summary)
    assert "말차 푸딩" not in serialized
    assert "VIP 고객" not in serialized
    assert "secret-cake.png" not in serialized
    assert "reference_image_b64" not in summary
    assert "user_constraints" not in summary
    assert summary["campaign_purpose"] == "new_menu"
    assert summary["tone"] == "clean"
    assert summary["template_hint"] == "minimal_premium"
    assert summary["has_price_text"] is True
    assert summary["has_user_constraints"] is True
    assert summary["has_reference_image"] is False
    assert len(summary["product_name_sha256"]) == 64


def test_redacted_response_summary_excludes_generated_copy_and_prompt() -> None:
    summary = redacted_response_summary(sample_response())

    serialized = str(summary)
    assert "비공개 헤드라인" not in serialized
    assert "비공개 이미지 프롬프트" not in serialized
    assert "outputs/demo.png" not in serialized
    assert "copy_options" not in summary
    assert "prompt_summary" not in summary
    assert "image_path" not in summary
    assert summary["copy_options_count"] == 1
    assert summary["has_image_path"] is True
    assert len(summary["image_path_sha256"]) == 64
    assert summary["selected_template"] == "minimal_premium"
    assert summary["copy_backend"] == "mock"
    assert summary["image_backend"] == "mock"
    assert summary["marketing_context_backend"] == "keyword"
    assert summary["marketing_context_categories"] == ["premium", "prohibited_claims"]


def test_in_memory_generation_job_store_tracks_lifecycle() -> None:
    store = InMemoryGenerationJobStore()
    request_summary = redacted_request_summary(sample_request())

    record = store.create_job("job-test", request_summary, queue_backend="inline")
    assert record.status == "queued"

    running = store.mark_running("job-test")
    assert running.status == "running"

    succeeded = store.mark_succeeded("job-test", redacted_response_summary(sample_response()))
    assert succeeded.status == "succeeded"
    assert succeeded.response_summary["copy_options_count"] == 1
    assert store.get_job("job-test") == succeeded


def test_generation_worker_adds_repo_root_to_python_path(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "run_generation_worker.py"
    original_path = [
        path
        for path in sys.path
        if path not in {str(repo_root), "", str(script_path.parent)}
    ]
    monkeypatch.setattr(sys, "path", [str(script_path.parent), *original_path])

    spec = importlib.util.spec_from_file_location(
        "_test_run_generation_worker",
        script_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module._ensure_repo_root_on_path()

    assert sys.path[0] == str(repo_root)
