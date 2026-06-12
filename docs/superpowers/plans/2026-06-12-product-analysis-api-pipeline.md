# Product Analysis API Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move product analysis into the FastAPI generation pipeline with a typed mock analyzer that can later be replaced by a VLM backend.

**Architecture:** Add a `ProductAnalysis` response model and a focused `product_analysis` module. FastAPI owns analyzer selection and returns analysis in `/generate`; Streamlit renders the API result instead of rebuilding analysis locally.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, Streamlit, pytest, ruff.

---

## File Structure

- Modify `src/dessert_ad_studio/schemas.py`
  - Add `ProductAnalysis`.
  - Add `product_analysis` to `GenerationResponse`.
- Create `src/dessert_ad_studio/product_analysis.py`
  - Own analyzer protocol, mock analyzer, and analysis label maps.
- Modify `src/dessert_ad_studio/banner_overlay.py`
  - Keep `build_demo_product_analysis` as a compatibility wrapper that delegates to `MockProductAnalyzer`.
- Create `tests/test_product_analysis.py`
  - Unit tests for mock analyzer and wrapper compatibility.
- Modify `api/main.py`
  - Add analyzer factory and include analysis in `/generate`.
- Modify `tests/test_api.py`
  - Assert product analysis is returned and backend errors are handled.
- Modify `app/streamlit_app.py`
  - Render `product_analysis` from API response.

## Task 1: Product Analysis Schema And Module

**Files:**
- Modify: `src/dessert_ad_studio/schemas.py`
- Create: `src/dessert_ad_studio/product_analysis.py`
- Modify: `src/dessert_ad_studio/banner_overlay.py`
- Create: `tests/test_product_analysis.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_product_analysis.py`:

```python
from dessert_ad_studio.banner_overlay import build_demo_product_analysis
from dessert_ad_studio.product_analysis import MockProductAnalyzer
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


def test_build_demo_product_analysis_uses_mock_analyzer_fields() -> None:
    analysis = build_demo_product_analysis(_request())

    assert analysis["label"] == "Product analysis"
    assert analysis["analyzer_backend"] == "mock"
    assert analysis["product_context"] == "딸기 생크림 케이크 / 디저트 카페 상품"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_product_analysis.py -q
```

Expected: failure because `dessert_ad_studio.product_analysis` does not exist.

- [ ] **Step 3: Add schema model**

In `src/dessert_ad_studio/schemas.py`, add before `GenerationResponse`:

```python
class ProductAnalysis(BaseModel):
    label: str
    product_context: str
    ad_goal: str
    visual_strategy: str
    photo_strategy: str
    copy_focus: str
    rendering_strategy: str
    analyzer_backend: str
```

Then update `GenerationResponse`:

```python
class GenerationResponse(BaseModel):
    copy_options: list[CopyOption]
    selected_template: TemplateRanking
    image_path: str
    image_backend: str
    copy_backend: str
    used_reference: bool
    prompt_summary: str
    elapsed_ms: float
    product_analysis: ProductAnalysis
```

- [ ] **Step 4: Implement analyzer module**

Create `src/dessert_ad_studio/product_analysis.py`:

```python
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
```

- [ ] **Step 5: Replace banner overlay wrapper**

In `src/dessert_ad_studio/banner_overlay.py`:

1. Remove `GenerationRequest` import only if it becomes unused elsewhere, then re-add it for the wrapper signature if needed.
2. Import `MockProductAnalyzer`.
3. Replace `build_demo_product_analysis` body with:

```python
def build_demo_product_analysis(request: GenerationRequest) -> dict[str, str]:
    return MockProductAnalyzer().analyze(request).model_dump()
```

Do not remove overlay-related constants used by `create_banner_overlay`.

- [ ] **Step 6: Run focused tests and lint**

Run:

```bash
.venv/bin/pytest tests/test_product_analysis.py tests/test_banner_overlay.py -q
.venv/bin/ruff check src/dessert_ad_studio/product_analysis.py src/dessert_ad_studio/schemas.py src/dessert_ad_studio/banner_overlay.py tests/test_product_analysis.py
```

Expected: all selected tests pass; ruff passes.

- [ ] **Step 7: Commit**

```bash
git add src/dessert_ad_studio/schemas.py src/dessert_ad_studio/product_analysis.py src/dessert_ad_studio/banner_overlay.py tests/test_product_analysis.py
git commit -m "Add product analysis analyzer"
```

## Task 2: API Product Analysis Response

**Files:**
- Modify: `api/main.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Add failing API tests**

Add tests to `tests/test_api.py` near existing `/generate` tests:

```python
def test_generate_includes_product_analysis(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    response = client.post("/generate", json=base_payload())

    assert response.status_code == 200
    analysis = response.json()["product_analysis"]
    assert analysis["label"] == "Product analysis"
    assert analysis["analyzer_backend"] == "mock"
    assert "딸기 크림 크루아상" in analysis["product_context"]
    assert "참고 이미지 없음" in analysis["photo_strategy"]


def test_generate_product_analysis_reflects_reference_image(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    payload = {
        **base_payload(),
        "reference_image_b64": sample_png_b64(),
        "reference_image_name": "cake.png",
    }
    response = client.post("/generate", json=payload)

    assert response.status_code == 200
    assert "업로드된 제품 사진" in response.json()["product_analysis"]["photo_strategy"]


def test_generate_rejects_unknown_product_analysis_backend(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("PRODUCT_ANALYSIS_BACKEND", "vlm")

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 501
    assert response.json()["detail"] == "unknown product analysis backend: vlm"
```

Use the existing image helper name in `tests/test_api.py`; if it is not `sample_png_b64`, use the helper already present in that file.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_api.py -q
```

Expected: failures because `product_analysis` is not in the response and unknown analyzer handling is missing.

- [ ] **Step 3: Add API analyzer factory**

In `api/main.py`, import:

```python
from dessert_ad_studio.product_analysis import MockProductAnalyzer, ProductAnalyzer
```

Add:

```python
def _product_analyzer_for(name: str) -> ProductAnalyzer | None:
    if name == "mock":
        return MockProductAnalyzer()
    return None


def get_product_analyzer() -> ProductAnalyzer:
    name = os.getenv("PRODUCT_ANALYSIS_BACKEND", "mock")
    analyzer = _product_analyzer_for(name)
    if analyzer is None:
        raise HTTPException(
            status_code=501,
            detail=f"unknown product analysis backend: {name}",
        )
    return analyzer
```

- [ ] **Step 4: Wire analysis into `/generate`**

Inside `generate` after reference backend validation and before `image_prompt`:

```python
    product_analyzer = get_product_analyzer()
    product_analysis = product_analyzer.analyze(request, reference_image=reference_image)
```

Add to `log_record`:

```python
        "product_analysis_backend": product_analyzer.name,
```

Add to `GenerationResponse(...)`:

```python
        product_analysis=product_analysis,
```

- [ ] **Step 5: Run focused tests and lint**

Run:

```bash
.venv/bin/pytest tests/test_api.py tests/test_product_analysis.py -q
.venv/bin/ruff check api/main.py tests/test_api.py
```

Expected: selected tests pass; ruff passes.

- [ ] **Step 6: Commit**

```bash
git add api/main.py tests/test_api.py
git commit -m "Return product analysis from API"
```

## Task 3: Streamlit Uses API Product Analysis

**Files:**
- Modify: `app/streamlit_app.py`

- [ ] **Step 1: Update Streamlit persistence**

Remove `build_demo_product_analysis` from the `dessert_ad_studio.banner_overlay` import list.

Change `_save_generation` signature to:

```python
def _save_generation(
    request: GenerationRequest,
    result: dict,
) -> dict:
    saved_generation = {
        "request": request.model_dump(),
        "result": result,
        "analysis": result.get("product_analysis", {}),
    }
    st.session_state[LAST_GENERATION_KEY] = saved_generation
    return saved_generation
```

In `_render_saved_generation`, keep compatibility:

```python
        analysis = saved_generation.get("analysis") or result.get("product_analysis", {})
```

In the successful API response path, replace:

```python
                    analysis = build_demo_product_analysis(request)
                    saved_generation = _save_generation(request, result, analysis)
```

with:

```python
                    saved_generation = _save_generation(request, result)
```

- [ ] **Step 2: Make result rendering tolerant**

At the start of `_render_result`, before rendering fields:

```python
    if not analysis:
        st.warning("제품 분석 결과가 응답에 포함되지 않았습니다.")
        return
```

Use label dynamically:

```python
    st.subheader(analysis.get("label", "Product analysis"))
```

Keep the existing field rendering for:

- `product_context`
- `ad_goal`
- `visual_strategy`
- `photo_strategy`
- `copy_focus`
- `rendering_strategy`

- [ ] **Step 3: Run focused checks**

Run:

```bash
.venv/bin/ruff check app/streamlit_app.py
.venv/bin/pytest tests/test_api.py tests/test_product_analysis.py tests/test_banner_overlay.py -q
```

Expected: selected tests pass; ruff passes.

- [ ] **Step 4: Commit**

```bash
git add app/streamlit_app.py
git commit -m "Render API product analysis in Streamlit"
```

## Task 4: Full Verification

**Files:**
- No source changes unless verification finds issues.

- [ ] **Step 1: Run full tests**

```bash
.venv/bin/pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run full lint**

```bash
.venv/bin/ruff check .
```

Expected: all checks pass.

- [ ] **Step 3: Run API smoke**

```bash
.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
```

In another shell:

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS -X POST http://127.0.0.1:8000/generate \
  -H 'Content-Type: application/json' \
  -d '{"campaign_purpose":"new_menu","product_name":"딸기 크림 크루아상","tone":"warm","template_hint":"cozy_cafe","price_text":"6,800원","user_constraints":"봄 시즌 한정 느낌"}'
```

Expected:

- health returns `{"status":"ok"}`.
- generate response includes `product_analysis.analyzer_backend == "mock"`.

- [ ] **Step 4: Commit fixes if needed**

Only if fixes are required:

```bash
git add api/main.py app/streamlit_app.py src/dessert_ad_studio/schemas.py src/dessert_ad_studio/product_analysis.py tests/test_api.py tests/test_product_analysis.py
git commit -m "Fix product analysis verification issues"
```

Expected if no fixes were required:

```text
No commit needed.
```

## Self-Review Notes

- Spec coverage: schema, analyzer module, API response, Streamlit rendering, tests, and verification are covered.
- Placeholder scan: no TBD/TODO/fill-in placeholders.
- Type consistency: `ProductAnalysis` is the schema type returned by `ProductAnalyzer.analyze` and included in `GenerationResponse`.
