from __future__ import annotations

import base64
import os
from typing import Any, Protocol, runtime_checkable

from openai import (
    APIError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)
from pydantic import BaseModel

from dessert_ad_studio.backends.base import AdBackendError
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

PRODUCT_ANALYSIS_SYSTEM_PROMPT = (
    "너는 카페/디저트 소상공인을 위한 한국어 광고 제품 분석가다. "
    "입력된 상품 정보와 선택적으로 제공되는 제품 사진을 바탕으로 "
    "제품 보존형 광고 배너 제작에 필요한 분석만 반환한다. "
    "모든 문장 필드는 한국어로 작성하고, 근거 없는 효능/수상/인증 주장은 만들지 않는다. "
    "이미지를 새로 생성하지 말고, 사진 보존/카피/오버레이 전략을 구조화한다."
)


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
        has_reference = reference_image is not None
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
            detected_product_name=request.product_name,
            dominant_colors=["상품 대표색", "크림색", "따뜻한 배경색"],
            mood_keywords=[tone, template],
            selling_points=["디저트 카페 상품", purpose, promotion],
            quality_notes=[
                "업로드 이미지 기반 분석 가능" if has_reference else "이미지 없이 요청값 기반 분석",
            ],
            recommended_background=f"{template} 무드의 밝고 정돈된 광고 배경",
            preservation_notes=[
                "상품 형태와 색감 보존" if has_reference else "상품명 기반 시각 일관성 유지",
            ],
        )


class OpenAIProductAnalysisPayload(BaseModel):
    label: str
    product_context: str
    ad_goal: str
    visual_strategy: str
    photo_strategy: str
    copy_focus: str
    rendering_strategy: str
    detected_product_name: str
    dominant_colors: list[str]
    mood_keywords: list[str]
    selling_points: list[str]
    quality_notes: list[str]
    recommended_background: str
    preservation_notes: list[str]


class OpenAIProductAnalyzer:
    name = "openai"

    def __init__(self, model_id: str | None = None, client: Any | None = None) -> None:
        if client is None and not os.getenv("OPENAI_API_KEY", "").strip():
            raise AdBackendError(
                "OpenAI API 키가 설정되지 않았습니다. .env의 OPENAI_API_KEY를 확인해주세요."
            )
        self.model_id = model_id or os.getenv("PRODUCT_ANALYSIS_MODEL_ID", "gpt-5.4-mini")
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            if not os.getenv("OPENAI_API_KEY", "").strip():
                raise AdBackendError(
                    "OpenAI API 키가 설정되지 않았습니다. .env의 OPENAI_API_KEY를 확인해주세요."
                )
            try:
                self._client = OpenAI(timeout=120.0)
            except OpenAIError as exc:
                raise AdBackendError(
                    "OpenAI API 키가 설정되지 않았습니다. .env의 OPENAI_API_KEY를 확인해주세요."
                ) from exc
        return self._client

    def analyze(
        self,
        request: GenerationRequest,
        reference_image: bytes | None = None,
    ) -> ProductAnalysis:
        client = self._get_client()
        try:
            response = client.responses.parse(
                model=self.model_id,
                input=[
                    {
                        "role": "system",
                        "content": PRODUCT_ANALYSIS_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": self._build_user_content(request, reference_image),
                    },
                ],
                text_format=OpenAIProductAnalysisPayload,
                store=False,
            )
        except AuthenticationError as exc:
            raise AdBackendError(
                "OpenAI API 키가 유효하지 않습니다. 키 값을 확인해주세요."
            ) from exc
        except RateLimitError as exc:
            raise AdBackendError(
                "OpenAI API 호출 한도를 초과했습니다. 잠시 후 다시 시도하거나 팀 사용량을 확인해주세요."
            ) from exc
        except BadRequestError as exc:
            raise AdBackendError(
                f"제품 분석 요청이 거부되었습니다: {exc}",
                status_code=422,
            ) from exc
        except APIError as exc:
            raise AdBackendError(f"제품 분석 API 호출에 실패했습니다: {exc}") from exc
        except OpenAIError as exc:
            raise AdBackendError(f"제품 분석 API 호출에 실패했습니다: {exc}") from exc

        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise AdBackendError("제품 분석 응답을 해석하지 못했습니다. 다시 시도해주세요.")
        return ProductAnalysis(
            analyzer_backend=self.name,
            **parsed.model_dump(),
        )

    def _build_user_content(
        self,
        request: GenerationRequest,
        reference_image: bytes | None,
    ) -> list[dict[str, str]]:
        content = [
            {
                "type": "input_text",
                "text": _build_openai_product_analysis_prompt(
                    request,
                    has_reference=reference_image is not None,
                ),
            }
        ]
        if reference_image is not None:
            content.append(
                {
                    "type": "input_image",
                    "image_url": _image_data_url(reference_image),
                    "detail": "low",
                }
            )
        return content


def _image_data_url(reference_image: bytes) -> str:
    encoded = base64.b64encode(reference_image).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _build_openai_product_analysis_prompt(
    request: GenerationRequest,
    *,
    has_reference: bool,
) -> str:
    purpose = PURPOSE_LABELS[request.campaign_purpose]
    tone = TONE_LABELS[request.tone]
    template = TEMPLATE_LABELS[request.template_hint]
    promotion = request.price_text.strip() or "별도 가격/혜택 없음"
    constraints = request.user_constraints.strip() or "추가 요청 없음"
    reference_status = (
        "제품 사진이 함께 제공되었습니다. 사진 속 실제 상품의 형태, 색감, 토핑, "
        "패키징을 우선 보존하는 전략을 제안하세요."
        if has_reference
        else "제품 사진이 없습니다. 상품명과 요청값만으로 보수적인 광고 전략을 제안하세요."
    )

    return "\n".join(
        [
            "다음 정보를 바탕으로 ProductAnalysis schema를 채우세요.",
            f"- 상품명: {request.product_name}",
            f"- 광고 목적: {purpose}",
            f"- 톤: {tone}",
            f"- 템플릿: {template}",
            f"- 가격/혜택: {promotion}",
            f"- 사용자 요청: {constraints}",
            f"- 참고 이미지 상태: {reference_status}",
            "- label은 정확히 'Product analysis'로 작성하세요.",
            "- detected_product_name은 사진/요청에서 식별한 상품명을 쓰세요.",
            "- dominant_colors, mood_keywords, selling_points, quality_notes, "
            "preservation_notes는 각각 1개 이상 5개 이하로 작성하세요.",
            "- rendering_strategy에는 한글 오버레이를 후처리로 넣는 방향을 포함하세요.",
        ]
    )
