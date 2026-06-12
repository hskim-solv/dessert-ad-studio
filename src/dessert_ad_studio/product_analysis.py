from __future__ import annotations

from typing import Protocol, runtime_checkable

from dessert_ad_studio.schemas import GenerationRequest, ProductAnalysis


PURPOSE_LABELS = {
    "new_menu": "신메뉴 출시",
    "seasonal_event": "시즌 이벤트",
    "discount": "할인/프로모션",
    "brand_awareness": "브랜드 인지도",
}

TONE_LABELS = {
    "warm": "따뜻한",
    "premium": "프리미엄",
    "playful": "발랄한",
    "clean": "깔끔한",
}

TEMPLATE_LABELS = {
    "cozy_cafe": "코지 카페",
    "minimal_premium": "미니멀 프리미엄",
    "cute_dessert": "귀여운 디저트",
    "seasonal_event": "시즌 이벤트",
}


@runtime_checkable
class ProductAnalyzer(Protocol):
    name: str

    def analyze(
        self,
        request: GenerationRequest,
        reference_image: bytes | None = None,
    ) -> ProductAnalysis: ...


class MockProductAnalyzer:
    name = "mock"

    def analyze(
        self,
        request: GenerationRequest,
        reference_image: bytes | None = None,
    ) -> ProductAnalysis:
        purpose = PURPOSE_LABELS[request.campaign_purpose]
        tone = TONE_LABELS[request.tone]
        template = TEMPLATE_LABELS[request.template_hint]
        promotion = request.price_text.strip() or "별도 가격/혜택 없음"
        constraints = request.user_constraints.strip() or "추가 요청 없음"
        has_reference = reference_image is not None or bool(request.reference_image_name)
        photo_strategy = (
            "업로드된 제품 사진을 기준으로 상품 형태와 색감을 유지한 배너 구성을 제안합니다."
            if has_reference
            else "참고 이미지 없음: 상품명과 요청사항을 기준으로 디저트 광고 장면을 구성합니다."
        )

        return ProductAnalysis(
            label="Product analysis",
            product_context=f"{request.product_name} / 디저트 카페 상품",
            ad_goal=f"{purpose} 목적의 광고입니다. 혜택/가격: {promotion}",
            visual_strategy=f"{tone} 톤과 {template} 템플릿에 맞춰 카페 광고 무드를 정리합니다.",
            photo_strategy=photo_strategy,
            copy_focus=f"카피는 상품 매력, 방문 동기, 요청사항({constraints})을 중심으로 구성합니다.",
            rendering_strategy="한글 문구, 가격 배지, CTA는 이미지 위에 PIL 오버레이로 렌더링합니다.",
            analyzer_backend=self.name,
        )
