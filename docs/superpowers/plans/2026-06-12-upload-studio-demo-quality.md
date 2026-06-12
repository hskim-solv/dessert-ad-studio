# Upload Studio Demo Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a polished upload-centered Streamlit Studio that turns one generated image into a downloadable Korean ad banner with demo product analysis.

**Architecture:** Keep the existing FastAPI `/generate` contract unchanged. Add a focused `dessert_ad_studio.banner_overlay` helper module for deterministic Korean banner rendering and mock product analysis, then refactor `app/streamlit_app.py` into a two-column Studio UI that consumes those helpers.

**Tech Stack:** Python 3.11, Streamlit, FastAPI, Pillow, pytest, existing `dessert_ad_studio.schemas` models.

---

## File Structure

- Create `src/dessert_ad_studio/banner_overlay.py`
  - Owns PIL overlay rendering, font fallback, text wrapping, output path creation, and deterministic demo analysis.
  - Has no Streamlit dependency.
- Create `tests/test_banner_overlay.py`
  - Unit tests for overlay output, long Korean text handling, missing font fallback, and demo analysis fields.
- Modify `app/streamlit_app.py`
  - Converts the current centered form into a wide two-column Studio.
  - Calls the existing `/generate` endpoint.
  - Uses `banner_overlay.py` to create the downloadable completed banner.
  - Keeps technical details in expanders.
- No API schema changes.
- No backend generation-count changes.

## Execution Amendments From Review

The implementation followed the task sequence below with these review-driven amendments:

- Add a small-image regression test and clamp overlay geometry so valid tiny images do not raise inverted-coordinate errors.
- Persist the last successful Streamlit generation in `st.session_state` so download clicks and other reruns keep the result visible.
- Pass `on_click="ignore"` to `st.download_button` only for Streamlit versions that support it; older allowed versions fall back to rerun-safe session-state rendering.
- Use `width="stretch"` for Streamlit images to avoid visible sizing deprecation alerts in Streamlit 1.58.

## Task 1: Add Banner Overlay Helper Tests

**Files:**
- Create: `tests/test_banner_overlay.py`
- Later implementation: `src/dessert_ad_studio/banner_overlay.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_banner_overlay.py` with:

```python
from pathlib import Path

from PIL import Image

from dessert_ad_studio.banner_overlay import (
    BannerCopy,
    build_demo_product_analysis,
    create_banner_overlay,
)
from dessert_ad_studio.schemas import GenerationRequest


def _request(reference_image_name: str | None = "cake.jpg") -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="discount",
        product_name="딸기 생크림 케이크",
        tone="warm",
        template_hint="cozy_cafe",
        price_text="주말 10% 할인",
        user_constraints="20대 여성 타깃, 감성적인 인스타그램 홍보",
        reference_image_name=reference_image_name,
    )


def test_create_banner_overlay_writes_png(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (900, 900), color=(240, 220, 210)).save(source)
    copy = BannerCopy(
        headline="딸기 케이크 주말 할인",
        body="상큼한 딸기와 부드러운 생크림을 오늘 만나보세요.",
        call_to_action="지금 예약하기",
    )

    output = create_banner_overlay(
        image_path=source,
        copy=copy,
        price_text="주말 10% 할인",
        output_dir=tmp_path / "banners",
    )

    assert output.exists()
    assert output.suffix == ".png"
    assert output.parent == tmp_path / "banners"
    assert output.name == "source_banner.png"
    with Image.open(output) as image:
        assert image.size == (900, 900)
        assert image.mode == "RGBA"


def test_create_banner_overlay_handles_long_korean_text(tmp_path: Path) -> None:
    source = tmp_path / "long.png"
    Image.new("RGB", (720, 720), color=(245, 240, 232)).save(source)
    copy = BannerCopy(
        headline="매장에서 직접 만든 진한 딸기 생크림 케이크를 이번 주말 한정 특별한 가격으로 만나보세요",
        body="신선한 딸기와 부드러운 크림을 듬뿍 올린 선물용 디저트입니다. 예약 주문도 가능합니다.",
        call_to_action="프로필 링크에서 예약",
    )

    output = create_banner_overlay(
        image_path=source,
        copy=copy,
        price_text="2호 케이크 예약 시 아메리카노 증정",
        output_dir=tmp_path / "banners",
        font_paths=[tmp_path / "missing-font.ttf"],
    )

    assert output.exists()
    with Image.open(output) as image:
        assert image.size == (720, 720)


def test_build_demo_product_analysis_with_reference_image() -> None:
    analysis = build_demo_product_analysis(_request(reference_image_name="cake.jpg"))

    assert analysis["label"] == "Demo product analysis"
    assert analysis["product_context"] == "딸기 생크림 케이크 / 디저트 카페 상품"
    assert "할인/프로모션" in analysis["ad_goal"]
    assert "따뜻한" in analysis["visual_strategy"]
    assert "업로드된 제품 사진" in analysis["photo_strategy"]
    assert "오버레이" in analysis["rendering_strategy"]


def test_build_demo_product_analysis_without_reference_image() -> None:
    analysis = build_demo_product_analysis(_request(reference_image_name=None))

    assert "참고 이미지 없음" in analysis["photo_strategy"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_banner_overlay.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'dessert_ad_studio.banner_overlay'
```

## Task 2: Implement Banner Overlay Helper

**Files:**
- Create: `src/dessert_ad_studio/banner_overlay.py`
- Test: `tests/test_banner_overlay.py`

- [ ] **Step 1: Add helper implementation**

Create `src/dessert_ad_studio/banner_overlay.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from dessert_ad_studio.schemas import GenerationRequest


@dataclass(frozen=True)
class BannerCopy:
    headline: str
    body: str
    call_to_action: str


DEFAULT_FONT_PATHS = [
    Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
    Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
    Path("/Library/Fonts/AppleGothic.ttf"),
]

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


def create_banner_overlay(
    *,
    image_path: str | Path,
    copy: BannerCopy,
    price_text: str,
    output_dir: str | Path = "outputs/streamlit-banners",
    font_paths: list[Path] | None = None,
) -> Path:
    source_path = Path(image_path)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    destination = output_path / f"{source_path.stem}_banner.png"

    with Image.open(source_path) as source:
        image = source.convert("RGBA")

    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size
    margin = max(28, width // 24)
    panel_height = max(height // 3, 260)
    panel_top = height - panel_height - margin
    panel_left = margin
    panel_right = width - margin
    panel_bottom = height - margin

    draw.rounded_rectangle(
        (panel_left, panel_top, panel_right, panel_bottom),
        radius=max(18, width // 45),
        fill=(18, 18, 18, 178),
    )

    headline_font = _load_font(max(30, width // 18), font_paths)
    body_font = _load_font(max(20, width // 34), font_paths)
    meta_font = _load_font(max(18, width // 38), font_paths)
    cta_font = _load_font(max(20, width // 32), font_paths)

    text_left = panel_left + max(22, width // 36)
    text_right = panel_right - max(22, width // 36)
    y = panel_top + max(22, height // 36)

    if price_text.strip():
        badge = _ellipsize(price_text.strip(), 26)
        badge_box = _text_bbox(draw, badge, meta_font)
        badge_width = badge_box[2] - badge_box[0] + 28
        badge_height = badge_box[3] - badge_box[1] + 16
        draw.rounded_rectangle(
            (text_left, y, text_left + badge_width, y + badge_height),
            radius=badge_height // 2,
            fill=(255, 235, 180, 235),
        )
        draw.text((text_left + 14, y + 7), badge, fill=(30, 24, 18, 255), font=meta_font)
        y += badge_height + 14

    max_text_width = text_right - text_left
    for line in _wrap_text(draw, _ellipsize(copy.headline, 48), headline_font, max_text_width, 2):
        draw.text((text_left, y), line, fill=(255, 255, 255, 255), font=headline_font)
        y += _line_height(draw, line, headline_font) + 6

    y += 4
    for line in _wrap_text(draw, _ellipsize(copy.body, 86), body_font, max_text_width, 2):
        draw.text((text_left, y), line, fill=(242, 242, 242, 245), font=body_font)
        y += _line_height(draw, line, body_font) + 5

    cta = _ellipsize(copy.call_to_action or "방문하기", 24)
    cta_box = _text_bbox(draw, cta, cta_font)
    cta_width = cta_box[2] - cta_box[0] + 34
    cta_height = cta_box[3] - cta_box[1] + 20
    cta_x = text_left
    cta_y = min(panel_bottom - cta_height - 18, y + 16)
    draw.rounded_rectangle(
        (cta_x, cta_y, cta_x + cta_width, cta_y + cta_height),
        radius=cta_height // 2,
        fill=(255, 255, 255, 242),
    )
    draw.text((cta_x + 17, cta_y + 9), cta, fill=(25, 25, 25, 255), font=cta_font)

    image.save(destination)
    return destination


def build_demo_product_analysis(request: GenerationRequest) -> dict[str, str]:
    purpose = PURPOSE_LABELS[request.campaign_purpose]
    tone = TONE_LABELS[request.tone]
    template = TEMPLATE_LABELS[request.template_hint]
    promotion = request.price_text.strip() or "별도 가격/혜택 없음"
    extra = request.user_constraints.strip() or "추가 요청 없음"
    photo_strategy = (
        "업로드된 제품 사진을 중심으로 상품이 잘 보이는 광고 배너 흐름을 구성합니다."
        if request.reference_image_name
        else "참고 이미지 없음: 상품명과 요청사항 중심으로 광고 비주얼을 구성합니다."
    )

    return {
        "label": "Demo product analysis",
        "product_context": f"{request.product_name} / 디저트 카페 상품",
        "ad_goal": f"{purpose} 목적, 혜택: {promotion}",
        "visual_strategy": f"{tone} 톤과 {template} 템플릿을 우선 적용합니다.",
        "photo_strategy": photo_strategy,
        "copy_focus": f"요청 반영: {extra}",
        "rendering_strategy": "한글 문구, 가격, CTA는 이미지 모델이 아니라 PIL 오버레이로 렌더링합니다.",
    }


def _load_font(size: int, font_paths: list[Path] | None = None) -> ImageFont.ImageFont:
    for path in font_paths or DEFAULT_FONT_PATHS:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if _text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == max_lines:
            break

    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) == max_lines and _text_width(draw, lines[-1], font) > max_width:
        lines[-1] = _shrink_to_width(draw, lines[-1], font, max_width)
    elif len(lines) == max_lines and len(" ".join(words)) > len(" ".join(lines)):
        lines[-1] = _shrink_to_width(draw, f"{lines[-1]}...", font, max_width)

    return lines


def _shrink_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> str:
    value = text.rstrip(". ")
    while value and _text_width(draw, f"{value}...", font) > max_width:
        value = value[:-1]
    return f"{value}..." if value else "..."


def _ellipsize(text: str, max_chars: int) -> str:
    value = text.strip()
    if len(value) <= max_chars:
        return value
    return f"{value[: max_chars - 1].rstrip()}..."


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = _text_bbox(draw, text, font)
    return box[2] - box[0]


def _line_height(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = _text_bbox(draw, text or "가", font)
    return box[3] - box[1]


def _text_bbox(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
) -> tuple[int, int, int, int]:
    return draw.textbbox((0, 0), text, font=font)
```

- [ ] **Step 2: Run helper tests**

Run:

```bash
pytest tests/test_banner_overlay.py -q
```

Expected:

```text
4 passed
```

- [ ] **Step 3: Commit helper and tests**

Run:

```bash
git add src/dessert_ad_studio/banner_overlay.py tests/test_banner_overlay.py
git commit -m "Add banner overlay helper"
```

Expected:

```text
[main <hash>] Add banner overlay helper
```

## Task 3: Refactor Streamlit Into Upload Studio UI

**Files:**
- Modify: `app/streamlit_app.py`
- Uses: `src/dessert_ad_studio/banner_overlay.py`

- [ ] **Step 1: Replace Streamlit app with two-column Studio**

Replace `app/streamlit_app.py` with:

```python
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

st.set_page_config(page_title="Dessert Ad Studio", page_icon="🍰", layout="wide")
st.title("Dessert Ad Studio")
st.caption("제품 사진 하나로 SNS 광고 문구와 다운로드 가능한 한글 배너를 만듭니다.")

left, right = st.columns([0.38, 0.62], gap="large")

with left:
    st.subheader("입력")
    with st.form("generation_form"):
        uploaded = st.file_uploader(
            "제품 사진",
            type=["png", "jpg", "jpeg", "webp"],
            help="OpenAI image backend에서는 참고 이미지로 사용됩니다. Flux2 backend는 참고 이미지를 지원하지 않습니다.",
        )
        if uploaded is not None:
            st.image(uploaded, caption="업로드한 제품 사진", width="stretch")

        product_name = st.text_input("상품명", value="딸기 크림 크루아상")
        campaign_label = st.selectbox("캠페인 목적", list(PURPOSE_OPTIONS))
        tone_label = st.selectbox("문구/이미지 톤", list(TONE_OPTIONS))
        template_label = st.selectbox("시각 템플릿", list(TEMPLATE_OPTIONS))
        price_text = st.text_input("가격/혜택", value="6,800원")
        user_constraints = st.text_area(
            "추가 요청",
            value="봄 시즌 한정 느낌, 따뜻한 카페 조명",
            height=96,
        )
        submitted = st.form_submit_button("광고 배너 만들기")

    st.caption(f"API: {API_BASE_URL}")

with right:
    st.subheader("결과")
    result_slot = st.container()

if not submitted:
    with result_slot:
        st.info("제품 사진과 광고 정보를 입력한 뒤 `광고 배너 만들기`를 누르면 결과가 여기에 표시됩니다.")
        st.markdown(
            """
            - 데모 제품 분석
            - 추천 광고 문구
            - 한글 오버레이가 적용된 대표 배너
            - 다운로드 가능한 PNG
            """
        )
else:
    reference_image_b64 = None
    if uploaded is not None:
        reference_image_b64 = base64.b64encode(uploaded.getvalue()).decode("ascii")

    request = GenerationRequest(
        campaign_purpose=PURPOSE_OPTIONS[campaign_label],
        product_name=product_name,
        tone=TONE_OPTIONS[tone_label],
        template_hint=TEMPLATE_OPTIONS[template_label],
        price_text=price_text,
        user_constraints=user_constraints,
        reference_image_b64=reference_image_b64,
        reference_image_name=uploaded.name if uploaded else None,
    )
    payload = request.model_dump()

    spinner_text = "광고 문구와 이미지를 생성하는 중입니다. 이미지 생성은 수십 초 걸릴 수 있어요."
    with result_slot, st.spinner(spinner_text):
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
            analysis = build_demo_product_analysis(request)
            _render_result(result=result, request=request, analysis=analysis)


def _render_result(
    *,
    result: dict,
    request: GenerationRequest,
    analysis: dict[str, str],
) -> None:
    st.markdown("#### Demo product analysis")
    st.caption("실제 VLM이 아니라 입력값 기반 데모 분석입니다.")
    analysis_cols = st.columns(2)
    items = [
        ("상품 맥락", analysis["product_context"]),
        ("광고 목표", analysis["ad_goal"]),
        ("시각 전략", analysis["visual_strategy"]),
        ("사진 전략", analysis["photo_strategy"]),
        ("문구 초점", analysis["copy_focus"]),
        ("렌더링 전략", analysis["rendering_strategy"]),
    ]
    for index, (label, value) in enumerate(items):
        with analysis_cols[index % 2]:
            st.markdown(f"**{label}**")
            st.write(value)

    copy_options = result["copy_options"]
    primary_copy = copy_options[0]
    image_path = Path(result["image_path"])
    banner_path = None

    if image_path.exists():
        try:
            banner_path = create_banner_overlay(
                image_path=image_path,
                copy=BannerCopy(
                    headline=primary_copy["headline"],
                    body=primary_copy["body"],
                    call_to_action=primary_copy["call_to_action"],
                ),
                price_text=request.price_text,
            )
        except Exception as exc:
            st.warning(f"한글 배너 오버레이 생성에 실패했습니다: {exc}")
    else:
        st.warning(f"이미지 파일을 찾지 못했습니다: {image_path}")

    st.markdown("#### 대표 완성 배너")
    if banner_path is not None and banner_path.exists():
        st.image(str(banner_path), caption="한글 오버레이 적용 배너", width="stretch")
        st.download_button(
            "완성 배너 다운로드",
            data=banner_path.read_bytes(),
            file_name=banner_path.name,
            mime="image/png",
            width="stretch",
        )
    elif image_path.exists():
        st.image(str(image_path), caption="원본 생성 이미지", width="stretch")

    st.markdown("#### 추천 광고 문구")
    copy_cols = st.columns(3)
    for index, option in enumerate(copy_options):
        with copy_cols[index % 3]:
            st.markdown(f"**Variant {index + 1}**")
            st.markdown(f"**{option['headline']}**")
            st.write(option["body"])
            st.caption(option["call_to_action"])

    used_reference = "예" if result["used_reference"] else "아니요"
    with st.expander("원본 생성 이미지"):
        if image_path.exists():
            st.image(str(image_path), caption=f"backend={result['image_backend']}")
        else:
            st.write(str(image_path))

    with st.expander("기술 정보"):
        st.caption(
            f"문구 백엔드: {result['copy_backend']} · "
            f"이미지 백엔드: {result['image_backend']} · "
            f"참고 이미지 반영: {used_reference} · "
            f"elapsed_ms: {result['elapsed_ms']:.1f}"
        )
        st.json(result["selected_template"])

    with st.expander("프롬프트 요약"):
        st.code(result["prompt_summary"])
```

- [ ] **Step 2: Fix function-order bug before running**

Move the `_render_result` function definition above the top-level `if not submitted: ... else: ...` block, because Streamlit executes the file top-to-bottom and `_render_result` must exist before it is called.

The final structure must be:

```python
API_BASE_URL = ...
PURPOSE_OPTIONS = ...
TONE_OPTIONS = ...
TEMPLATE_OPTIONS = ...


def _render_result(...):
    ...


st.set_page_config(...)
...
if not submitted:
    ...
else:
    ...
```

- [ ] **Step 3: Run lint on the modified files**

Run:

```bash
ruff check app/streamlit_app.py src/dessert_ad_studio/banner_overlay.py tests/test_banner_overlay.py
```

Expected:

```text
All checks passed!
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
pytest tests/test_banner_overlay.py tests/test_api.py -q
```

Expected:

```text
... passed
```

- [ ] **Step 5: Commit Streamlit UI**

Run:

```bash
git add app/streamlit_app.py
git commit -m "Improve upload studio demo UI"
```

Expected:

```text
[main <hash>] Improve upload studio demo UI
```

## Task 4: Verify Full Local Quality Gate

**Files:**
- No new files unless fixes are required.

- [ ] **Step 1: Run all tests**

Run:

```bash
pytest -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 2: Run full lint**

Run:

```bash
ruff check .
```

Expected:

```text
All checks passed!
```

- [ ] **Step 3: Smoke the API and Streamlit manually**

Terminal 1:

```bash
uvicorn api.main:app --reload --port 8000
```

Expected:

```text
Uvicorn running on http://127.0.0.1:8000
```

Terminal 2:

```bash
streamlit run app/streamlit_app.py
```

Expected:

```text
Local URL: http://localhost:8501
```

Manual check:

- Open `http://localhost:8501`.
- Generate with default mock backends.
- Confirm the right panel shows demo product analysis.
- Confirm a representative completed banner appears.
- Confirm `완성 배너 다운로드` downloads a PNG from `outputs/streamlit-banners/`.
- Confirm original image and technical details remain in expanders.

- [ ] **Step 4: Commit any verification fixes**

Only if the previous steps required fixes:

```bash
git add app/streamlit_app.py src/dessert_ad_studio/banner_overlay.py tests/test_banner_overlay.py
git commit -m "Fix upload studio verification issues"
```

Expected if fixes were needed:

```text
[main <hash>] Fix upload studio verification issues
```

Expected if no fixes were needed:

```text
No commit needed.
```

## Self-Review Notes

- Spec coverage: The plan covers wide Streamlit layout, unchanged API contract, one generated image, mock product analysis, PIL Korean overlay, downloadable overlaid banner, expanders for technical details, helper tests, and follow-up exclusion of FastMCP/VLM/RAG.
- Placeholder scan: The plan contains no TBD/TODO/fill-in placeholders. The only placeholder behavior is the intended pre-generation UI message from the spec.
- Type consistency: `BannerCopy`, `create_banner_overlay`, and `build_demo_product_analysis` are defined in Task 2 before being imported by Task 3. `GenerationRequest` fields match `src/dessert_ad_studio/schemas.py`.
