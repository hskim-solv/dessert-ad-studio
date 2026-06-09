from __future__ import annotations

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
    uploaded = st.file_uploader("참고 이미지", type=["png", "jpg", "jpeg"])
    submitted = st.form_submit_button("광고 생성")

if submitted:
    payload = {
        "campaign_purpose": PURPOSE_OPTIONS[campaign_label],
        "product_name": product_name,
        "tone": TONE_OPTIONS[tone_label],
        "template_hint": TEMPLATE_OPTIONS[template_label],
        "price_text": price_text,
        "user_constraints": user_constraints,
        "reference_image_path": uploaded.name if uploaded else None,
    }
    with st.spinner("FastAPI와 Triton 템플릿 스코어러를 호출하는 중입니다..."):
        try:
            response = httpx.post(f"{API_BASE_URL}/generate", json=payload, timeout=120)
            response.raise_for_status()
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
