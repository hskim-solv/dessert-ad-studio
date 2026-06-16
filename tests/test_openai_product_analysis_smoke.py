import json
from pathlib import Path
from types import SimpleNamespace

from dessert_ad_studio.schemas import ProductAnalysis
from scripts.openai_product_analysis_smoke import (
    build_eval_cases,
    build_sample_request,
    summarize_eval_results,
    run_eval,
    run_smoke,
    summarize_analysis,
)


def _analysis() -> ProductAnalysis:
    return ProductAnalysis(
        label="Product analysis",
        product_context="딸기 크림 크루아상 분석",
        ad_goal="신메뉴 출시",
        visual_strategy="밝은 카페 조명",
        photo_strategy="제품 형태와 토핑을 보존",
        copy_focus="딸기와 크림",
        rendering_strategy="한글 오버레이는 후처리로 렌더링",
        analyzer_backend="openai",
        detected_product_name="딸기 크림 크루아상",
        dominant_colors=["red", "cream"],
        mood_keywords=["warm"],
        selling_points=["딸기", "크림"],
        quality_notes=["윤곽 보존"],
        recommended_background="카페 테이블",
        preservation_notes=["토핑 위치 유지"],
    )


def test_summarize_analysis_is_redacted_and_scores_required_fields() -> None:
    summary = summarize_analysis(
        _analysis(),
        model_id="gpt-test",
        elapsed_ms=1234.5,
        used_reference=True,
        expected_product_name="딸기 크림 크루아상",
    )

    assert summary == {
        "product_analysis_smoke": "passed",
        "analyzer_backend": "openai",
        "model_id": "gpt-test",
        "elapsed_ms": 1234,
        "used_reference": True,
        "detected_product_name_present": True,
        "expected_product_name_mentioned": True,
        "dominant_colors_count": 2,
        "mood_keywords_count": 1,
        "selling_points_count": 2,
        "quality_notes_count": 1,
        "preservation_notes_count": 1,
        "has_korean_overlay_strategy": True,
        "checklist_passed": True,
    }
    assert "product_context" not in summary
    assert "photo_strategy" not in summary
    assert "copy_focus" not in summary


def test_summarize_analysis_accepts_whitespace_variant_product_name() -> None:
    analysis = ProductAnalysis(
        **{
            **_analysis().model_dump(),
            "detected_product_name": "딸기크림크루아상",
        }
    )

    summary = summarize_analysis(
        analysis,
        model_id="gpt-test",
        elapsed_ms=1234.5,
        used_reference=True,
        expected_product_name="딸기 크림 크루아상",
    )

    assert summary["expected_product_name_mentioned"] is True
    assert summary["checklist_passed"] is True


def test_run_smoke_writes_redacted_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "summary.json"

    fake_analyzer = SimpleNamespace(
        name="openai",
        model_id="gpt-test",
        analyze=lambda request, reference_image=None: _analysis(),
    )

    summary = run_smoke(
        analyzer=fake_analyzer,
        request=build_sample_request(),
        reference_image=b"png",
        output_path=output_path,
    )

    assert summary["product_analysis_smoke"] == "passed"
    assert summary["used_reference"] is True
    assert json.loads(output_path.read_text(encoding="utf-8")) == summary


def test_summarize_eval_results_computes_pass_rate_and_p95_latency() -> None:
    passed = summarize_analysis(
        _analysis(),
        model_id="gpt-test",
        elapsed_ms=1000,
        used_reference=True,
        expected_product_name="딸기 크림 크루아상",
    )
    slower = {**passed, "elapsed_ms": 2000}
    failed = {**passed, "elapsed_ms": 9000, "checklist_passed": False}

    summary = summarize_eval_results(
        [passed, slower, failed],
        threshold=0.8,
        latency_target_ms=30_000,
    )

    assert summary == {
        "product_analysis_eval": "failed",
        "sample_count": 3,
        "passed_count": 2,
        "pass_rate": 0.667,
        "threshold": 0.8,
        "latency_p95_ms": 9000,
        "latency_target_ms": 30000,
        "latency_target_passed": True,
        "passed": False,
        "results": [passed, slower, failed],
    }


def test_build_eval_cases_are_representative_and_unique() -> None:
    cases = build_eval_cases()

    assert len(cases) >= 10
    assert len({case.label for case in cases}) == len(cases)
    assert all(case.request.product_name for case in cases)
    assert {case.request.campaign_purpose for case in cases} >= {
        "new_menu",
        "seasonal_event",
        "discount",
        "brand_awareness",
    }
    assert {case.request.tone for case in cases} >= {"warm", "premium", "playful", "clean"}


def test_run_eval_writes_redacted_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "eval-summary.json"
    cases = build_eval_cases()[:2]

    fake_analyzer = SimpleNamespace(
        name="openai",
        model_id="gpt-test",
        analyze=lambda request, reference_image=None: ProductAnalysis(
            **{
                **_analysis().model_dump(),
                "detected_product_name": request.product_name,
            }
        ),
    )

    summary = run_eval(
        analyzer=fake_analyzer,
        cases=cases,
        image_dir=tmp_path / "images",
        output_path=output_path,
        threshold=0.8,
        latency_target_ms=30_000,
    )

    assert summary["product_analysis_eval"] == "passed"
    assert summary["sample_count"] == 2
    assert summary["pass_rate"] == 1.0
    assert json.loads(output_path.read_text(encoding="utf-8")) == summary
    for result in summary["results"]:
        assert result["product_analysis_smoke"] == "passed"
        assert "product_context" not in result
        assert "photo_strategy" not in result
