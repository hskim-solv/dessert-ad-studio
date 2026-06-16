"""Manual OpenAI product-analysis smoke check.

Costs real money and sends the sample request plus optional reference image to
OpenAI. Intended for explicit local validation, not CI.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any

from dotenv import load_dotenv

from dessert_ad_studio.product_analysis import OpenAIProductAnalyzer
from dessert_ad_studio.reference_image import decode_reference_image
from dessert_ad_studio.schemas import GenerationRequest, ProductAnalysis


def build_sample_request() -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="new_menu",
        product_name="딸기 크림 크루아상",
        tone="warm",
        template_hint="cozy_cafe",
        price_text="6,800원",
        user_constraints="봄 시즌 한정 느낌, 제품 사진 보존",
    )


def load_reference_image(path: Path | None) -> bytes | None:
    if path is None:
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return decode_reference_image(encoded)


def summarize_analysis(
    analysis: ProductAnalysis,
    *,
    model_id: str | None,
    elapsed_ms: float,
    used_reference: bool,
    expected_product_name: str,
) -> dict[str, Any]:
    detected_product_name = analysis.detected_product_name.strip()
    expected_mentioned = expected_product_name in detected_product_name
    has_korean_overlay_strategy = any(
        marker in analysis.rendering_strategy for marker in ("한글", "오버레이", "후처리", "렌더링")
    )
    checklist_passed = all(
        [
            analysis.analyzer_backend == "openai",
            bool(detected_product_name),
            expected_mentioned,
            bool(analysis.dominant_colors),
            bool(analysis.selling_points),
            bool(analysis.quality_notes),
            bool(analysis.preservation_notes),
            has_korean_overlay_strategy,
        ]
    )
    return {
        "product_analysis_smoke": "passed" if checklist_passed else "failed",
        "analyzer_backend": analysis.analyzer_backend,
        "model_id": model_id,
        "elapsed_ms": round(elapsed_ms),
        "used_reference": used_reference,
        "detected_product_name_present": bool(detected_product_name),
        "expected_product_name_mentioned": expected_mentioned,
        "dominant_colors_count": len(analysis.dominant_colors),
        "mood_keywords_count": len(analysis.mood_keywords),
        "selling_points_count": len(analysis.selling_points),
        "quality_notes_count": len(analysis.quality_notes),
        "preservation_notes_count": len(analysis.preservation_notes),
        "has_korean_overlay_strategy": has_korean_overlay_strategy,
        "checklist_passed": checklist_passed,
    }


def run_smoke(
    *,
    analyzer: OpenAIProductAnalyzer,
    request: GenerationRequest,
    reference_image: bytes | None,
    output_path: Path | None,
) -> dict[str, Any]:
    started = perf_counter()
    analysis = analyzer.analyze(request, reference_image=reference_image)
    elapsed_ms = (perf_counter() - started) * 1000
    summary = summarize_analysis(
        analysis,
        model_id=analyzer.model_id,
        elapsed_ms=elapsed_ms,
        used_reference=reference_image is not None,
        expected_product_name=request.product_name,
    )
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    print(payload)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    return summary


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Smoke check OpenAI product analysis without persisting raw model output."
    )
    parser.add_argument("--reference-image", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise SystemExit("OPENAI_API_KEY가 없습니다. .env 또는 환경변수를 확인하세요.")

    summary = run_smoke(
        analyzer=OpenAIProductAnalyzer(),
        request=build_sample_request(),
        reference_image=load_reference_image(args.reference_image),
        output_path=args.output,
    )
    return 0 if summary["checklist_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
