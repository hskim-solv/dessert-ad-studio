from __future__ import annotations

import base64
import os
from pathlib import Path

import httpx
import streamlit as st
from dessert_ad_studio.banner_overlay import (
    BannerCopy,
    build_demo_product_analysis,
    create_banner_overlay,
)
from dessert_ad_studio.schemas import GenerationRequest
from pydantic import ValidationError

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

PURPOSE_OPTIONS = {
    "신메뉴 출시": "new_menu",
    "시즌 이벤트": "seasonal_event",
    "할인/프로모션": "discount",
    "브랜드 인지도": "brand_awareness",
}

TONE_OPTIONS = {
    "따뜻한": "warm",
    "프리미엄": "premium",
    "발랄한": "playful",
    "깔끔한": "clean",
}

TEMPLATE_OPTIONS = {
    "코지 카페": "cozy_cafe",
    "미니멀 프리미엄": "minimal_premium",
    "귀여운 디저트": "cute_dessert",
    "시즌 이벤트": "seasonal_event",
}


def _encode_uploaded_file(uploaded_file) -> str | None:
    if uploaded_file is None:
        return None
    return base64.b64encode(uploaded_file.getvalue()).decode("ascii")


def _render_result(result: dict, request: GenerationRequest, analysis: dict[str, str]) -> None:
    st.subheader("Demo product analysis")
    with st.container(border=True):
        st.markdown(f"**{analysis['product_context']}**")
        st.write(analysis["ad_goal"])
        st.write(analysis["visual_strategy"])
        st.write(analysis["photo_strategy"])
        st.write(analysis["copy_focus"])
        st.caption(analysis["rendering_strategy"])

    copy_options = result.get("copy_options", [])
    image_path_value = result.get("image_path")
    image_path = Path(str(image_path_value)) if image_path_value else None
    image_exists = image_path is not None and image_path.exists()

    st.subheader("대표 완성 배너")
    if image_path is None:
        st.warning("생성 이미지 경로가 응답에 포함되지 않았습니다.")
    elif not image_exists:
        st.warning(f"이미지 파일을 찾지 못했습니다: {image_path}")
    else:
        overlay_path = None
        if copy_options:
            primary = copy_options[0]
            primary_copy = BannerCopy(
                headline=primary["headline"],
                body=primary["body"],
                call_to_action=primary["call_to_action"],
            )
            try:
                overlay_path = create_banner_overlay(
                    image_path=image_path,
                    copy=primary_copy,
                    price_text=request.price_text,
                )
            except Exception as exc:
                st.warning(
                    "배너 오버레이 생성 중 문제가 발생했습니다. "
                    f"원본 이미지를 표시합니다: {exc}"
                )
        else:
            st.warning("배너 오버레이에 사용할 광고 문구를 찾지 못했습니다.")

        if overlay_path is not None and overlay_path.exists():
            st.image(str(overlay_path), caption="대표 완성 배너", use_column_width=True)
            st.download_button(
                "오버레이 배너 다운로드",
                data=overlay_path.read_bytes(),
                file_name=overlay_path.name,
                mime="image/png",
            )
        else:
            st.image(str(image_path), caption="원본 생성 이미지", use_column_width=True)

    st.subheader("추천 광고 문구")
    if copy_options:
        for index, option in enumerate(copy_options, start=1):
            with st.container(border=True):
                st.markdown(f"**{index}. {option['headline']}**")
                st.write(option["body"])
                st.caption(option["call_to_action"])
    else:
        st.warning("추천 광고 문구가 응답에 포함되지 않았습니다.")

    if image_exists and image_path is not None:
        with st.expander("원본 생성 이미지"):
            st.image(
                str(image_path),
                caption=f"backend={result.get('image_backend', 'unknown')}",
                use_column_width=True,
            )

    with st.expander("기술 정보"):
        used_reference = "예" if result.get("used_reference") else "아니요"
        st.write(f"문구 백엔드: {result.get('copy_backend', 'unknown')}")
        st.write(f"이미지 백엔드: {result.get('image_backend', 'unknown')}")
        st.write(f"참고 이미지 반영: {used_reference}")
        st.write(f"소요 시간(ms): {result.get('elapsed_ms', 'unknown')}")
        st.json(result.get("selected_template", {}))

    with st.expander("프롬프트 요약"):
        st.code(result.get("prompt_summary", ""))


st.set_page_config(page_title="Dessert Ad Studio", layout="wide")
st.title("Dessert Ad Studio")
st.caption("카페와 디저트 소상공인을 위한 SNS 광고 이미지와 문구 생성 스튜디오")

left_column, right_column = st.columns([0.38, 0.62], gap="large")

with left_column:
    st.subheader("Upload Studio")
    uploaded = st.file_uploader(
        "제품 이미지",
        type=["png", "jpg", "jpeg", "webp"],
        help="업로드하면 사진을 바탕으로 광고 이미지를 생성합니다.",
    )
    if uploaded is not None:
        st.image(uploaded, caption=uploaded.name, use_column_width=True)
    else:
        st.info("제품 사진을 업로드하면 생성 결과와 오버레이 배너를 함께 확인할 수 있습니다.")

    with st.form("generation_form"):
        product_name = st.text_input("상품명", value="딸기 크림 크루아상")
        campaign_label = st.selectbox("캠페인 목적", list(PURPOSE_OPTIONS))
        tone_label = st.selectbox("톤", list(TONE_OPTIONS))
        template_label = st.selectbox("시각 템플릿", list(TEMPLATE_OPTIONS))
        price_text = st.text_input("가격/혜택", value="6,800원")
        user_constraints = st.text_area(
            "추가 요청",
            value="봄 시즌 한정 느낌, 따뜻한 카페 조명",
        )
        submitted = st.form_submit_button("광고 생성")

    st.caption(f"API: POST {API_BASE_URL}/generate")

with right_column:
    if not submitted:
        st.info(
            "광고 생성 후 이 영역에서 데모 제품 분석, 대표 완성 배너, 추천 문구, "
            "오버레이 배너 다운로드, 원본 이미지와 기술 정보를 확인할 수 있습니다."
        )
    else:
        try:
            request = GenerationRequest(
                campaign_purpose=PURPOSE_OPTIONS[campaign_label],
                product_name=product_name,
                tone=TONE_OPTIONS[tone_label],
                template_hint=TEMPLATE_OPTIONS[template_label],
                price_text=price_text,
                user_constraints=user_constraints,
                reference_image_b64=_encode_uploaded_file(uploaded),
                reference_image_name=uploaded.name if uploaded else None,
            )
        except ValidationError as exc:
            st.error("입력값을 확인해 주세요.")
            st.json(exc.errors())
        else:
            spinner_text = (
                "광고 문구와 이미지를 생성하는 중입니다... "
                "(이미지 생성은 수십 초 걸릴 수 있어요)"
            )
            with st.spinner(spinner_text):
                try:
                    response = httpx.post(
                        f"{API_BASE_URL}/generate",
                        json=request.model_dump(),
                        timeout=120,
                    )
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    try:
                        detail = exc.response.json().get("detail")
                    except Exception:
                        detail = None
                    st.error(detail or f"생성 요청 실패: {exc}")
                except Exception as exc:
                    st.error(f"생성 요청 실패: {exc}")
                else:
                    result = response.json()
                    analysis = build_demo_product_analysis(request)
                    _render_result(result, request, analysis)
