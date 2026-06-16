from __future__ import annotations

from dessert_ad_studio.schemas import GenerationRequest, MarketingContext, ProductAnalysis

# Single source of truth for how many copy options one generation produces;
# the copy prompts and the response validation must agree on it.
COPY_OPTION_COUNT = 3

PURPOSE_LABELS = {
    "new_menu": "신메뉴",
    "seasonal_event": "시즌 이벤트",
    "discount": "할인 프로모션",
    "brand_awareness": "브랜드 인지도 SNS 게시물",
}

TONE_LABELS = {
    "warm": "따뜻한",
    "premium": "프리미엄",
    "playful": "발랄한",
    "clean": "깔끔한",
}

TEMPLATE_LABELS = {
    "cozy_cafe": "cozy cafe",
    "minimal_premium": "minimal premium",
    "cute_dessert": "cute dessert",
    "seasonal_event": "seasonal event",
}


def build_copy_prompt(
    request: GenerationRequest,
    product_analysis: ProductAnalysis | None = None,
    marketing_context: MarketingContext | None = None,
) -> str:
    price_line = (
        f"- 가격/혜택: {request.price_text}" if request.price_text else "- 가격/혜택: 입력 없음"
    )
    constraint_line = (
        f"- 사용자 제약: {request.user_constraints}"
        if request.user_constraints
        else "- 사용자 제약: 과장 광고 없이 자연스럽게"
    )
    lines = [
        "카페/디저트 소상공인을 위한 한국어 SNS 광고 문구를 작성한다.",
        f"- 목적: {PURPOSE_LABELS[request.campaign_purpose]}",
        f"- 상품명: {request.product_name}",
        f"- 톤: {TONE_LABELS[request.tone]}",
        f"- 선호 템플릿: {TEMPLATE_LABELS[request.template_hint]}",
        price_line,
        constraint_line,
    ]
    if product_analysis is not None:
        detected_product = product_analysis.detected_product_name or request.product_name
        selling_points = ", ".join(product_analysis.selling_points) or product_analysis.copy_focus
        lines.extend(
            [
                "제품 분석 요약",
                f"- 감지 상품: {detected_product}",
                f"- 카피 포인트: {selling_points}",
                f"- 광고 목표: {product_analysis.ad_goal}",
            ]
        )
    if marketing_context is not None and marketing_context.retrieved_docs_count > 0:
        lines.append("마케팅 가이드")
        _append_guidance(lines, "카피 가이드", marketing_context.copy_guidelines)
        _append_guidance(lines, "톤 예시", marketing_context.tone_examples)
        _append_guidance(lines, "플랫폼 노트", marketing_context.platform_notes)
        _append_guidance(lines, "금지/주의", marketing_context.prohibited_claims)
        _append_guidance(lines, "CTA 예시", marketing_context.cta_examples)
    lines.append(
        f"출력은 헤드라인, 본문, 행동유도문구를 가진 후보 {COPY_OPTION_COUNT}개로 제한한다."
    )
    return "\n".join(lines)


def _append_guidance(lines: list[str], label: str, values: list[str]) -> None:
    if values:
        lines.append(f"- {label}: {' / '.join(values)}")


def build_image_prompt(
    request: GenerationRequest,
    ranked_template: str,
    has_reference: bool = False,
    product_analysis: ProductAnalysis | None = None,
) -> str:
    lines: list[str] = []
    if has_reference:
        lines.append("업로드된 제품 사진의 피사체와 구도를 보존하면서 광고 이미지로 연출한다.")
    lines.extend(
        [
            "SNS 정사각형 광고 이미지 생성 지시문",
            f"상품: {request.product_name}",
            f"캠페인: {PURPOSE_LABELS[request.campaign_purpose]}",
            f"톤: {TONE_LABELS[request.tone]}",
            f"템플릿: {TEMPLATE_LABELS.get(ranked_template, ranked_template)}",
            "구도: 중앙에 디저트 상품, 하단 또는 우측에 읽기 쉬운 텍스트 여백",
            "스타일: 실제 카페 SNS에 올릴 수 있는 깔끔한 상업 사진 느낌",
            f"제약: {request.user_constraints or '브랜드 로고나 허위 수상 문구를 추가하지 않는다.'}",
        ]
    )
    if product_analysis is not None:
        detected_product = product_analysis.detected_product_name or request.product_name
        selling_points = ", ".join(product_analysis.selling_points) or product_analysis.copy_focus
        dominant_colors = ", ".join(product_analysis.dominant_colors) or "분석값 없음"
        preservation_notes = (
            ", ".join(product_analysis.preservation_notes) or product_analysis.photo_strategy
        )
        recommended_background = (
            product_analysis.recommended_background or product_analysis.visual_strategy
        )
        lines.extend(
            [
                "제품 분석 요약",
                f"감지 상품: {detected_product}",
                f"대표 색상: {dominant_colors}",
                f"광고 포인트: {selling_points}",
                f"추천 배경: {recommended_background}",
                f"제품 보존: {preservation_notes}",
            ]
        )
    return "\n".join(lines)


def template_features(request: GenerationRequest) -> list[float]:
    return [
        1.0 if request.campaign_purpose == "new_menu" else 0.0,
        1.0 if request.campaign_purpose == "seasonal_event" else 0.0,
        1.0 if request.campaign_purpose == "discount" else 0.0,
        1.0 if request.campaign_purpose == "brand_awareness" else 0.0,
        1.0 if request.tone == "warm" else 0.0,
        1.0 if request.tone == "premium" else 0.0,
        1.0 if request.tone == "playful" else 0.0,
        1.0 if request.tone == "clean" else 0.0,
    ]
