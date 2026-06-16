import json
from pathlib import Path
from types import SimpleNamespace

from dessert_ad_studio.schemas import ProductAnalysis
from scripts.openai_product_analysis_smoke import (
    build_sample_request,
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
