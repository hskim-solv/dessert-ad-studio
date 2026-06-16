"""Manual OpenAI product-analysis smoke check.

Costs real money and sends the sample request plus optional reference image to
OpenAI. Intended for explicit local validation, not CI.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol, Sequence

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from dessert_ad_studio.product_analysis import OpenAIProductAnalyzer
from dessert_ad_studio.reference_image import decode_reference_image
from dessert_ad_studio.schemas import GenerationRequest, ProductAnalysis


@dataclass(frozen=True)
class ProductAnalysisEvalCase:
    label: str
    request: GenerationRequest
    background_rgb: tuple[int, int, int]
    product_rgb: tuple[int, int, int]
    accent_rgb: tuple[int, int, int]


class ProductAnalyzer(Protocol):
    model_id: str | None

    def analyze(
        self,
        request: GenerationRequest,
        *,
        reference_image: bytes | None = None,
    ) -> ProductAnalysis: ...


def build_sample_request() -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="new_menu",
        product_name="딸기 크림 크루아상",
        tone="warm",
        template_hint="cozy_cafe",
        price_text="6,800원",
        user_constraints="봄 시즌 한정 느낌, 제품 사진 보존",
    )


def build_eval_cases() -> list[ProductAnalysisEvalCase]:
    return [
        ProductAnalysisEvalCase(
            label="strawberry-cream-croissant",
            request=GenerationRequest(
                campaign_purpose="new_menu",
                product_name="딸기 크림 크루아상",
                tone="warm",
                template_hint="cozy_cafe",
                price_text="6,800원",
                user_constraints="인스타그램 피드, 봄 시즌 신메뉴, 제품 사진 보존",
            ),
            background_rgb=(252, 238, 230),
            product_rgb=(224, 86, 112),
            accent_rgb=(255, 247, 220),
        ),
        ProductAnalysisEvalCase(
            label="matcha-pudding-seasonal",
            request=GenerationRequest(
                campaign_purpose="seasonal_event",
                product_name="말차 푸딩",
                tone="clean",
                template_hint="minimal_premium",
                price_text="2개 세트 9,900원",
                user_constraints="시즌 한정 선물용, 진한 말차 컬러와 매끈한 질감 강조",
            ),
            background_rgb=(235, 241, 226),
            product_rgb=(94, 139, 79),
            accent_rgb=(245, 238, 200),
        ),
        ProductAnalysisEvalCase(
            label="basque-cheesecake-brand",
            request=GenerationRequest(
                campaign_purpose="brand_awareness",
                product_name="바스크 치즈케이크",
                tone="premium",
                template_hint="minimal_premium",
                price_text="조각 7,500원",
                user_constraints="프리미엄 카페 시그니처, 그을린 윗면과 크림 질감 보존",
            ),
            background_rgb=(242, 234, 221),
            product_rgb=(166, 92, 48),
            accent_rgb=(250, 221, 145),
        ),
        ProductAnalysisEvalCase(
            label="lemon-madeleine-discount",
            request=GenerationRequest(
                campaign_purpose="discount",
                product_name="레몬 마들렌",
                tone="playful",
                template_hint="cute_dessert",
                price_text="3개 세트 7,500원",
                user_constraints="주말 할인, 밝은 노란색과 귀여운 디저트 톤",
            ),
            background_rgb=(255, 248, 213),
            product_rgb=(237, 190, 72),
            accent_rgb=(128, 182, 95),
        ),
        ProductAnalysisEvalCase(
            label="chocolate-financier-new-menu",
            request=GenerationRequest(
                campaign_purpose="new_menu",
                product_name="초콜릿 휘낭시에",
                tone="premium",
                template_hint="minimal_premium",
                price_text="4개 박스 12,000원",
                user_constraints="진한 초콜릿 색감, 선물 박스 느낌, 제품 형태 보존",
            ),
            background_rgb=(236, 225, 217),
            product_rgb=(83, 45, 35),
            accent_rgb=(196, 160, 105),
        ),
        ProductAnalysisEvalCase(
            label="peach-yogurt-cake-seasonal",
            request=GenerationRequest(
                campaign_purpose="seasonal_event",
                product_name="복숭아 요거트 케이크",
                tone="warm",
                template_hint="seasonal_event",
                price_text="홀케이크 32,000원",
                user_constraints="여름 시즌 한정, 과일 토핑 위치와 케이크 단면 보존",
            ),
            background_rgb=(255, 237, 226),
            product_rgb=(246, 154, 128),
            accent_rgb=(255, 249, 238),
        ),
        ProductAnalysisEvalCase(
            label="salt-butter-roll-brand",
            request=GenerationRequest(
                campaign_purpose="brand_awareness",
                product_name="소금 버터롤",
                tone="clean",
                template_hint="cozy_cafe",
                price_text="3,800원",
                user_constraints="매장 대표 베이커리, 담백한 색감과 바삭한 결 보존",
            ),
            background_rgb=(244, 238, 226),
            product_rgb=(210, 146, 79),
            accent_rgb=(255, 255, 246),
        ),
        ProductAnalysisEvalCase(
            label="blueberry-macaron-discount",
            request=GenerationRequest(
                campaign_purpose="discount",
                product_name="블루베리 마카롱",
                tone="playful",
                template_hint="cute_dessert",
                price_text="5개 세트 13,000원",
                user_constraints="포장 할인, 파스텔 컬러와 둥근 형태 보존",
            ),
            background_rgb=(232, 237, 255),
            product_rgb=(101, 110, 196),
            accent_rgb=(242, 196, 221),
        ),
        ProductAnalysisEvalCase(
            label="tiramisu-cup-new-menu",
            request=GenerationRequest(
                campaign_purpose="new_menu",
                product_name="티라미수 컵",
                tone="premium",
                template_hint="cozy_cafe",
                price_text="6,200원",
                user_constraints="신메뉴 출시, 코코아 파우더와 컵 레이어 보존",
            ),
            background_rgb=(238, 229, 218),
            product_rgb=(122, 78, 58),
            accent_rgb=(245, 239, 222),
        ),
        ProductAnalysisEvalCase(
            label="earl-grey-scone-seasonal",
            request=GenerationRequest(
                campaign_purpose="seasonal_event",
                product_name="얼그레이 스콘",
                tone="clean",
                template_hint="minimal_premium",
                price_text="2개 세트 8,500원",
                user_constraints="티타임 시즌 프로모션, 담백한 베이커리 질감 보존",
            ),
            background_rgb=(238, 239, 232),
            product_rgb=(177, 139, 95),
            accent_rgb=(104, 123, 105),
        ),
    ]


def load_reference_image(path: Path | None) -> bytes | None:
    if path is None:
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return decode_reference_image(encoded)


def _normalize_product_name(value: str) -> str:
    return "".join(value.casefold().split())


def summarize_analysis(
    analysis: ProductAnalysis,
    *,
    model_id: str | None,
    elapsed_ms: float,
    used_reference: bool,
    expected_product_name: str,
) -> dict[str, Any]:
    detected_product_name = analysis.detected_product_name.strip()
    expected_mentioned = _normalize_product_name(expected_product_name) in _normalize_product_name(
        detected_product_name
    )
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


def _write_synthetic_reference_image(case: ProductAnalysisEvalCase, image_dir: Path) -> Path:
    image_dir.mkdir(parents=True, exist_ok=True)
    path = image_dir / f"{case.label}.png"

    image = Image.new("RGB", (768, 768), color=case.background_rgb)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    draw.rounded_rectangle((86, 96, 682, 666), radius=42, fill=(255, 252, 246), width=0)
    draw.ellipse((214, 192, 554, 532), fill=case.product_rgb, outline=(82, 66, 58), width=5)
    draw.ellipse((290, 246, 478, 434), fill=case.accent_rgb, outline=(120, 94, 78), width=3)
    draw.rectangle((96, 602, 672, 666), fill=(70, 54, 48))
    draw.text((124, 618), f"{case.label} / {case.request.tone}", fill=(255, 255, 255), font=font)
    draw.text(
        (124, 642),
        f"{case.request.campaign_purpose} / {case.request.template_hint}",
        fill=(234, 224, 214),
        font=font,
    )

    image.save(path, format="PNG")
    return path


def run_eval(
    *,
    analyzer: ProductAnalyzer,
    cases: Sequence[ProductAnalysisEvalCase],
    image_dir: Path,
    output_path: Path | None,
    threshold: float,
    latency_target_ms: int,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in cases:
        image_path = _write_synthetic_reference_image(case, image_dir)
        reference_image = load_reference_image(image_path)
        started = perf_counter()
        analysis = analyzer.analyze(case.request, reference_image=reference_image)
        elapsed_ms = (perf_counter() - started) * 1000
        result = summarize_analysis(
            analysis,
            model_id=analyzer.model_id,
            elapsed_ms=elapsed_ms,
            used_reference=reference_image is not None,
            expected_product_name=case.request.product_name,
        )
        results.append(
            {
                "case_label": case.label,
                "campaign_purpose": case.request.campaign_purpose,
                "tone": case.request.tone,
                "template_hint": case.request.template_hint,
                **result,
            }
        )

    summary = summarize_eval_results(
        results,
        threshold=threshold,
        latency_target_ms=latency_target_ms,
    )
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    print(payload)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    return summary


def summarize_eval_results(
    results: list[dict[str, Any]],
    *,
    threshold: float,
    latency_target_ms: int,
) -> dict[str, Any]:
    sample_count = len(results)
    passed_count = sum(1 for result in results if result.get("checklist_passed") is True)
    pass_rate = round(passed_count / sample_count, 3) if sample_count else 0.0
    latencies = sorted(int(result.get("elapsed_ms", 0)) for result in results)
    latency_p95_ms = (
        latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))] if latencies else 0
    )
    latency_target_passed = latency_p95_ms <= latency_target_ms if sample_count else False
    passed = pass_rate >= threshold and latency_target_passed
    return {
        "product_analysis_eval": "passed" if passed else "failed",
        "sample_count": sample_count,
        "passed_count": passed_count,
        "pass_rate": pass_rate,
        "threshold": threshold,
        "latency_p95_ms": latency_p95_ms,
        "latency_target_ms": latency_target_ms,
        "latency_target_passed": latency_target_passed,
        "passed": passed,
        "results": results,
    }


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Smoke check OpenAI product analysis without persisting raw model output."
    )
    parser.add_argument("--reference-image", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--eval", action="store_true", help="Run the fixed multi-case eval set.")
    parser.add_argument(
        "--eval-count",
        type=int,
        default=0,
        help="Limit eval cases for pilot runs. Defaults to all cases.",
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=Path("outputs/product-analysis-eval"),
        help="Directory for synthetic eval reference images.",
    )
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument("--latency-target-ms", type=int, default=30_000)
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise SystemExit("OPENAI_API_KEY가 없습니다. .env 또는 환경변수를 확인하세요.")

    analyzer = OpenAIProductAnalyzer()
    if args.eval:
        cases = build_eval_cases()
        if args.eval_count < 0:
            raise SystemExit("--eval-count는 0 이상이어야 합니다.")
        if args.eval_count:
            cases = cases[: args.eval_count]
        summary = run_eval(
            analyzer=analyzer,
            cases=cases,
            image_dir=args.image_dir,
            output_path=args.output,
            threshold=args.threshold,
            latency_target_ms=args.latency_target_ms,
        )
        return 0 if summary["passed"] else 1

    summary = run_smoke(
        analyzer=analyzer,
        request=build_sample_request(),
        reference_image=load_reference_image(args.reference_image),
        output_path=args.output,
    )
    return 0 if summary["checklist_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
