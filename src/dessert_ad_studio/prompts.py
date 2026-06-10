from __future__ import annotations

from dessert_ad_studio.schemas import GenerationRequest

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


def build_copy_prompt(request: GenerationRequest) -> str:
    price_line = f"- 가격/혜택: {request.price_text}" if request.price_text else "- 가격/혜택: 입력 없음"
    constraint_line = (
        f"- 사용자 제약: {request.user_constraints}"
        if request.user_constraints
        else "- 사용자 제약: 과장 광고 없이 자연스럽게"
    )
    return "\n".join(
        [
            "카페/디저트 소상공인을 위한 한국어 SNS 광고 문구를 작성한다.",
            f"- 목적: {PURPOSE_LABELS[request.campaign_purpose]}",
            f"- 상품명: {request.product_name}",
            f"- 톤: {TONE_LABELS[request.tone]}",
            f"- 선호 템플릿: {TEMPLATE_LABELS[request.template_hint]}",
            price_line,
            constraint_line,
            f"출력은 헤드라인, 본문, 행동유도문구를 가진 후보 {COPY_OPTION_COUNT}개로 제한한다.",
        ]
    )


def build_image_prompt(
    request: GenerationRequest,
    ranked_template: str,
    has_reference: bool = False,
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
