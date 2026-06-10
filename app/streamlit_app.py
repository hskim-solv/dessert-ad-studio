from __future__ import annotations

import base64
import os
from pathlib import Path

import httpx
import streamlit as st

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

st.set_page_config(page_title="Dessert Ad Studio", page_icon="🍰", layout="centered")
st.title("🍰 Dessert Ad Studio")
st.caption("카페/디저트 소상공인을 위한 SNS 광고 이미지와 문구 생성")

with st.form("generation_form"):
    product_name = st.text_input("상품명", value="딸기 크림 크루아상")
    campaign_label = st.selectbox("캠페인 목적", list(PURPOSE_OPTIONS))
    tone_label = st.selectbox("문구/이미지 톤", list(TONE_OPTIONS))
    template_label = st.selectbox("시각 템플릿", list(TEMPLATE_OPTIONS))
    price_text = st.text_input("가격/혜택", value="6,800원")
    user_constraints = st.text_area("추가 요청", value="봄 시즌 한정 느낌, 따뜻한 카페 조명")
    uploaded = st.file_uploader(
        "참고 이미지 (업로드하면 사진을 바탕으로 광고 이미지를 만들어요)",
        type=["png", "jpg", "jpeg", "webp"],
    )
    submitted = st.form_submit_button("광고 생성")

if submitted:
    reference_image_b64 = None
    if uploaded is not None:
        reference_image_b64 = base64.b64encode(uploaded.getvalue()).decode("ascii")
    payload = {
        "campaign_purpose": PURPOSE_OPTIONS[campaign_label],
        "product_name": product_name,
        "tone": TONE_OPTIONS[tone_label],
        "template_hint": TEMPLATE_OPTIONS[template_label],
        "price_text": price_text,
        "user_constraints": user_constraints,
        "reference_image_b64": reference_image_b64,
        "reference_image_name": uploaded.name if uploaded else None,
    }
    spinner_text = "광고 문구와 이미지를 생성하는 중입니다... (이미지 생성은 수십 초 걸릴 수 있어요)"
    with st.spinner(spinner_text):
        try:
            response = httpx.post(f"{API_BASE_URL}/generate", json=payload, timeout=120)
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
            st.subheader("추천 광고 문구")
            for index, option in enumerate(result["copy_options"], start=1):
                st.markdown(f"**{index}. {option['headline']}**")
                st.write(option["body"])
                st.caption(option["call_to_action"])

            st.subheader("Triton 템플릿 선택")
            ranking = result["selected_template"]
            st.json(ranking)

            st.subheader("생성 이미지")
            used_reference = "예" if result["used_reference"] else "아니요"
            st.caption(
                f"문구 백엔드: {result['copy_backend']} · "
                f"이미지 백엔드: {result['image_backend']} · "
                f"참고 이미지 반영: {used_reference}"
            )
            image_path = Path(result["image_path"])
            if image_path.exists():
                st.image(str(image_path), caption=f"backend={result['image_backend']}")
                st.download_button(
                    "이미지 다운로드",
                    data=image_path.read_bytes(),
                    file_name=image_path.name,
                    mime="image/png",
                )
            else:
                st.warning(f"이미지 파일을 찾지 못했습니다: {image_path}")

            st.subheader("프롬프트 요약")
            st.code(result["prompt_summary"])
