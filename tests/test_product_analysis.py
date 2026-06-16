import base64
from types import SimpleNamespace
from typing import cast

import pytest

from dessert_ad_studio.banner_overlay import build_demo_product_analysis
from dessert_ad_studio.backends.base import AdBackendError
from dessert_ad_studio.product_analysis import (
    MockProductAnalyzer,
    OpenAIProductAnalysisPayload,
    OpenAIProductAnalyzer,
)
from dessert_ad_studio.schemas import GenerationRequest


def _request(reference_image_name: str | None = "cake.jpg") -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="discount",
        product_name="딸기 생크림 케이크",
        tone="warm",
        template_hint="cozy_cafe",
        price_text="주말 10% 할인",
        user_constraints="20대 여성 타깃, 감성적인 문구",
        reference_image_name=reference_image_name,
    )


def test_mock_product_analyzer_returns_display_fields_with_reference() -> None:
    analysis = MockProductAnalyzer().analyze(_request(), reference_image=b"png")

    assert analysis.label == "Product analysis"
    assert analysis.analyzer_backend == "mock"
    assert analysis.product_context == "딸기 생크림 케이크 / 디저트 카페 상품"
    assert analysis.detected_product_name == "딸기 생크림 케이크"
    assert analysis.dominant_colors == ["상품 대표색", "크림색", "따뜻한 배경색"]
    assert "디저트 카페 상품" in analysis.selling_points
    assert "상품 형태와 색감 보존" in analysis.preservation_notes
    assert "코지 카페" in analysis.recommended_background
    assert "할인/프로모션" in analysis.ad_goal
    assert "따뜻한" in analysis.visual_strategy
    assert "업로드된 제품 사진" in analysis.photo_strategy
    assert "오버레이" in analysis.rendering_strategy


def test_mock_product_analyzer_handles_missing_reference_image() -> None:
    analysis = MockProductAnalyzer().analyze(
        _request(reference_image_name=None),
        reference_image=None,
    )

    assert "참고 이미지 없음" in analysis.photo_strategy


def test_mock_product_analyzer_ignores_reference_name_without_image_bytes() -> None:
    analysis = MockProductAnalyzer().analyze(
        _request(reference_image_name="cake.jpg"),
        reference_image=None,
    )

    assert "참고 이미지 없음" in analysis.photo_strategy


def test_build_demo_product_analysis_uses_mock_analyzer_fields() -> None:
    analysis = build_demo_product_analysis(_request())

    assert analysis["label"] == "Product analysis"
    assert analysis["analyzer_backend"] == "mock"
    assert analysis["product_context"] == "딸기 생크림 케이크 / 디저트 카페 상품"


def _openai_payload() -> OpenAIProductAnalysisPayload:
    return OpenAIProductAnalysisPayload(
        label="Product analysis",
        product_context="딸기 생크림 케이크 / 신선한 딸기와 크림을 강조한 디저트",
        ad_goal="주말 할인 방문 전환을 유도합니다.",
        visual_strategy="따뜻한 조명과 붉은 딸기 포인트를 살립니다.",
        photo_strategy="제품 형태와 크림 질감을 유지합니다.",
        copy_focus="딸기, 생크림, 주말 할인 혜택을 중심으로 씁니다.",
        rendering_strategy="한글 헤드라인과 가격 배지는 후처리 오버레이로 렌더링합니다.",
        detected_product_name="딸기 생크림 케이크",
        dominant_colors=["red", "cream", "warm beige"],
        mood_keywords=["warm", "cozy"],
        selling_points=["생딸기", "부드러운 크림", "주말 할인"],
        quality_notes=["제품 윤곽 보존 필요"],
        recommended_background="밝은 카페 테이블",
        preservation_notes=["제품 모양과 토핑 위치를 유지"],
    )


class FakeResponses:
    def __init__(self, payload: OpenAIProductAnalysisPayload | None) -> None:
        self._payload = payload
        self.last_kwargs: dict | None = None

    def parse(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(output_parsed=self._payload)


_DEFAULT_OPENAI_PAYLOAD = object()


def make_fake_openai_client(
    payload: OpenAIProductAnalysisPayload | None | object = _DEFAULT_OPENAI_PAYLOAD,
) -> SimpleNamespace:
    parsed_payload = (
        _openai_payload()
        if payload is _DEFAULT_OPENAI_PAYLOAD
        else cast(OpenAIProductAnalysisPayload | None, payload)
    )
    return SimpleNamespace(responses=FakeResponses(parsed_payload))


def test_openai_product_analyzer_uses_responses_structured_output_without_reference() -> None:
    client = make_fake_openai_client()
    analyzer = OpenAIProductAnalyzer(model_id="gpt-vision-test", client=client)

    analysis = analyzer.analyze(_request(reference_image_name=None), reference_image=None)

    assert analysis.analyzer_backend == "openai"
    assert analysis.detected_product_name == "딸기 생크림 케이크"
    assert analysis.dominant_colors == ["red", "cream", "warm beige"]
    kwargs = client.responses.last_kwargs
    assert kwargs["model"] == "gpt-vision-test"
    assert kwargs["text_format"] is OpenAIProductAnalysisPayload
    assert kwargs["store"] is False
    assert kwargs["input"][0]["role"] == "system"
    user_content = kwargs["input"][1]["content"]
    assert user_content[0]["type"] == "input_text"
    assert "딸기 생크림 케이크" in user_content[0]["text"]
    assert not any(part["type"] == "input_image" for part in user_content)


def test_openai_product_analyzer_sends_reference_as_data_url() -> None:
    client = make_fake_openai_client()
    analyzer = OpenAIProductAnalyzer(model_id="gpt-vision-test", client=client)
    reference_image = b"normalized-png-bytes"

    analyzer.analyze(_request(), reference_image=reference_image)

    user_content = client.responses.last_kwargs["input"][1]["content"]
    image_part = next(part for part in user_content if part["type"] == "input_image")
    encoded = base64.b64encode(reference_image).decode("ascii")
    assert image_part == {
        "type": "input_image",
        "image_url": f"data:image/png;base64,{encoded}",
        "detail": "low",
    }


def test_openai_product_analyzer_rejects_unparsed_response() -> None:
    analyzer = OpenAIProductAnalyzer(client=make_fake_openai_client(None))

    with pytest.raises(AdBackendError, match="해석하지"):
        analyzer.analyze(_request())


def test_openai_product_analyzer_requires_api_key_without_injected_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(AdBackendError, match="OPENAI_API_KEY"):
        OpenAIProductAnalyzer()
