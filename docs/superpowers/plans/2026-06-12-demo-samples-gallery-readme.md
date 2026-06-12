# Demo Samples Gallery README Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reusable demo scenarios, expose them in Streamlit, and rewrite README so evaluators can understand and run the demo quickly.

**Architecture:** Keep the existing `/generate` API unchanged. Add a small Streamlit-free `demo_samples` module with typed sample data, wire those samples into the Streamlit form defaults, and make README the product-facing entry point while preserving advanced backend/GPU notes.

**Tech Stack:** Python 3.11, Streamlit, FastAPI, Pydantic, pytest, ruff.

---

## File Structure

- Create `src/dessert_ad_studio/demo_samples.py`
  - Owns reusable sample scenario data.
  - No Streamlit dependency.
- Create `tests/test_demo_samples.py`
  - Verifies sample count, uniqueness, schema compatibility, and display fields.
- Modify `app/streamlit_app.py`
  - Imports `DEMO_SAMPLES`.
  - Adds `데모 샘플` selectbox above the form.
  - Uses selected sample values as form defaults.
- Modify `README.md`
  - Rewrites project story and quick demo path.
  - Keeps backend, Docker, Triton, OpenAI, and Flux2/GCP details under later sections.

## Task 1: Demo Sample Data And Tests

**Files:**
- Create: `src/dessert_ad_studio/demo_samples.py`
- Create: `tests/test_demo_samples.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_demo_samples.py`:

```python
from dessert_ad_studio.demo_samples import DEMO_SAMPLES, DemoSample
from dessert_ad_studio.schemas import GenerationRequest


def test_demo_samples_include_at_least_three_scenarios() -> None:
    assert len(DEMO_SAMPLES) >= 3


def test_demo_sample_labels_are_unique() -> None:
    labels = [sample.label for sample in DEMO_SAMPLES]
    assert len(labels) == len(set(labels))


def test_demo_samples_convert_to_generation_requests() -> None:
    for sample in DEMO_SAMPLES:
        request = GenerationRequest(
            campaign_purpose=sample.campaign_purpose,
            product_name=sample.product_name,
            tone=sample.tone,
            template_hint=sample.template_hint,
            price_text=sample.price_text,
            user_constraints=sample.user_constraints,
        )
        assert request.product_name == sample.product_name


def test_demo_samples_have_display_context() -> None:
    for sample in DEMO_SAMPLES:
        assert isinstance(sample, DemoSample)
        assert sample.business_type.strip()
        assert sample.platform.strip()
        assert sample.user_constraints.strip()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_demo_samples.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'dessert_ad_studio.demo_samples'
```

- [ ] **Step 3: Implement sample module**

Create `src/dessert_ad_studio/demo_samples.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from dessert_ad_studio.schemas import CampaignPurpose, TemplateHint, Tone


@dataclass(frozen=True)
class DemoSample:
    label: str
    business_type: str
    platform: str
    product_name: str
    campaign_purpose: CampaignPurpose
    tone: Tone
    template_hint: TemplateHint
    price_text: str
    user_constraints: str


DEMO_SAMPLES: tuple[DemoSample, ...] = (
    DemoSample(
        label="디저트 카페 - 딸기 크림 크루아상",
        business_type="디저트 카페",
        platform="인스타그램 피드",
        product_name="딸기 크림 크루아상",
        campaign_purpose="new_menu",
        tone="warm",
        template_hint="cozy_cafe",
        price_text="6,800원",
        user_constraints="봄 시즌 한정 느낌, 따뜻한 카페 조명, 20대 여성 타깃",
    ),
    DemoSample(
        label="베이커리 - 말차 푸딩",
        business_type="베이커리",
        platform="인스타그램 스토리",
        product_name="말차 푸딩",
        campaign_purpose="seasonal_event",
        tone="premium",
        template_hint="minimal_premium",
        price_text="2개 세트 9,900원",
        user_constraints="진한 말차 풍미, 차분한 프리미엄 분위기, 시즌 한정 디저트",
    ),
    DemoSample(
        label="꽃집 - 플라워 박스",
        business_type="꽃집",
        platform="네이버 스마트스토어 썸네일",
        product_name="봄 플라워 박스",
        campaign_purpose="discount",
        tone="playful",
        template_hint="seasonal_event",
        price_text="예약 주문 10% 할인",
        user_constraints="선물용 추천, 화사한 봄 컬러, 주말 예약 주문 유도",
    ),
)
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
.venv/bin/pytest tests/test_demo_samples.py -q
```

Expected:

```text
4 passed
```

- [ ] **Step 5: Run lint**

Run:

```bash
.venv/bin/ruff check src/dessert_ad_studio/demo_samples.py tests/test_demo_samples.py
```

Expected:

```text
All checks passed!
```

- [ ] **Step 6: Commit sample data**

Run:

```bash
git add src/dessert_ad_studio/demo_samples.py tests/test_demo_samples.py
git commit -m "Add reusable demo samples"
```

Expected:

```text
[main <hash>] Add reusable demo samples
```

## Task 2: Streamlit Sample Selector

**Files:**
- Modify: `app/streamlit_app.py`
- Uses: `src/dessert_ad_studio/demo_samples.py`

- [ ] **Step 1: Update imports and constants**

In `app/streamlit_app.py`, add:

```python
from dessert_ad_studio.demo_samples import DEMO_SAMPLES, DemoSample
```

After `TEMPLATE_OPTIONS`, add reverse lookup dictionaries and sample constants:

```python
PURPOSE_LABELS_BY_VALUE = {value: label for label, value in PURPOSE_OPTIONS.items()}
TONE_LABELS_BY_VALUE = {value: label for label, value in TONE_OPTIONS.items()}
TEMPLATE_LABELS_BY_VALUE = {value: label for label, value in TEMPLATE_OPTIONS.items()}
CUSTOM_SAMPLE_LABEL = "직접 입력"
SAMPLE_OPTIONS = (CUSTOM_SAMPLE_LABEL, *(sample.label for sample in DEMO_SAMPLES))
```

- [ ] **Step 2: Add sample lookup helper**

Add this helper before top-level Streamlit code:

```python
def _sample_by_label(label: str) -> DemoSample | None:
    for sample in DEMO_SAMPLES:
        if sample.label == label:
            return sample
    return None
```

- [ ] **Step 3: Add selector and sample defaults**

Inside `with left_column:`, before `uploaded = st.file_uploader(...)`, add:

```python
    sample_label = st.selectbox("데모 샘플", SAMPLE_OPTIONS)
    selected_sample = _sample_by_label(sample_label)
    if selected_sample is not None:
        st.caption(f"{selected_sample.business_type} · {selected_sample.platform}")
```

Before `with st.form("generation_form")`, compute defaults:

```python
    default_product_name = selected_sample.product_name if selected_sample else "딸기 크림 크루아상"
    default_campaign_label = (
        PURPOSE_LABELS_BY_VALUE[selected_sample.campaign_purpose]
        if selected_sample
        else "신메뉴 출시"
    )
    default_tone_label = TONE_LABELS_BY_VALUE[selected_sample.tone] if selected_sample else "따뜻한"
    default_template_label = (
        TEMPLATE_LABELS_BY_VALUE[selected_sample.template_hint]
        if selected_sample
        else "코지 카페"
    )
    default_price_text = selected_sample.price_text if selected_sample else "6,800원"
    default_user_constraints = (
        selected_sample.user_constraints
        if selected_sample
        else "봄 시즌 한정 느낌, 따뜻한 카페 조명"
    )
```

- [ ] **Step 4: Wire defaults into form widgets**

Change the form fields to use defaults:

```python
        product_name = st.text_input("상품명", value=default_product_name)
        campaign_label = st.selectbox(
            "캠페인 목적",
            list(PURPOSE_OPTIONS),
            index=list(PURPOSE_OPTIONS).index(default_campaign_label),
        )
        tone_label = st.selectbox(
            "톤",
            list(TONE_OPTIONS),
            index=list(TONE_OPTIONS).index(default_tone_label),
        )
        template_label = st.selectbox(
            "시각 템플릿",
            list(TEMPLATE_OPTIONS),
            index=list(TEMPLATE_OPTIONS).index(default_template_label),
        )
        price_text = st.text_input("가격/혜택", value=default_price_text)
        user_constraints = st.text_area(
            "추가 요청",
            value=default_user_constraints,
        )
```

- [ ] **Step 5: Run checks**

Run:

```bash
.venv/bin/ruff check app/streamlit_app.py src/dessert_ad_studio/demo_samples.py tests/test_demo_samples.py
.venv/bin/pytest tests/test_demo_samples.py tests/test_banner_overlay.py tests/test_api.py -q
```

Expected:

```text
All checks passed!
24 passed
```

- [ ] **Step 6: Commit Streamlit selector**

Run:

```bash
git add app/streamlit_app.py
git commit -m "Add demo sample selector"
```

Expected:

```text
[main <hash>] Add demo sample selector
```

## Task 3: README Portfolio Rewrite

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace README with evaluator-oriented content**

Replace `README.md` with:

```markdown
# Dessert Ad Studio

Small-business ad banner studio for cafe, bakery, and local-store owners.

The app turns a product photo and a short marketing request into Korean ad copy, a generated visual, and a downloadable banner with deterministic Korean text overlay.

## Problem

Small business owners often need SNS banners, menu images, and promotion copy, but design tools and prompt engineering add friction. A raw image-generation model also tends to distort Korean text, so the service separates visual generation from Korean text rendering.

## What The Demo Does

1. Choose a demo sample or enter a product manually in Streamlit.
2. Generate three Korean ad-copy options through FastAPI.
3. Generate one representative ad visual through the selected image backend.
4. Render headline, price, and CTA with a PIL overlay.
5. Download the finished PNG banner.

## Core Features

- Upload-centered Streamlit Studio UI
- Three reusable demo scenarios
- Korean copy candidates
- Mock Product Analysis for the future VLM flow
- Deterministic Korean banner overlay
- Downloadable finished banner
- Backend adapter slots for mock, OpenAI, and FLUX.2
- JSONL generation logging

## Architecture

```text
Streamlit Upload Studio
  -> FastAPI /generate
  -> template scorer
  -> copy backend
  -> image backend
  -> PIL Korean text overlay
  -> downloadable banner PNG
```

Planned AI pipeline:

```text
Product photo
  -> VLM product analysis
  -> RAG marketing guidance
  -> controlled agent workflow
  -> product-preserving visual generation
  -> deterministic Korean overlay
```

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the API:

```bash
uvicorn api.main:app --reload --port 8000
```

Run Streamlit:

```bash
streamlit run app/streamlit_app.py
```

Open:

```text
http://localhost:8501
```

The default mock backends work without API keys.

## Demo Scenarios

The Streamlit `데모 샘플` selector includes:

| Scenario | Product | Platform | Goal |
| --- | --- | --- | --- |
| Dessert cafe | 딸기 크림 크루아상 | Instagram feed | New menu launch |
| Bakery | 말차 푸딩 | Instagram story | Seasonal event |
| Flower shop | 봄 플라워 박스 | Smartstore thumbnail | Reservation discount |

Generated assets are written to:

```text
outputs/
outputs/streamlit-banners/
logs/generations.jsonl
```

## Configuration

Copy `.env.example` to `.env` and edit local values. Do not commit `.env`.

| Variable | Values | Default |
| --- | --- | --- |
| `COPY_BACKEND` | `mock`, `openai` | `mock` |
| `IMAGE_BACKEND` | `mock`, `openai`, `flux2` | `mock` |
| `COPY_MODEL_ID` | any chat model id | `gpt-5.4-mini` |
| `IMAGE_MODEL_ID` | any GPT image model id | `gpt-image-1-mini` |
| `IMAGE_QUALITY` | `low`, `medium`, `high` | `low` |

Real OpenAI backends need `OPENAI_API_KEY` in `.env`.

Uploading a reference image in Streamlit switches the OpenAI image backend from text-to-image to edit mode. The `flux2` backend is text-to-image only for now: uploading a reference image with it returns a 400 instead of silently ignoring the photo.

## Tests

```bash
pytest -q
ruff check .
```

Manual smoke:

```bash
python scripts/openai_smoke.py                      # copy + text-to-image
python scripts/openai_smoke.py my_product_photo.jpg # copy + reference edit
python scripts/flux2_smoke.py                       # needs [image] deps
```

## Docker Compose Demo

Generate the ONNX model before starting Triton:

```bash
python scripts/export_template_scorer_onnx.py
docker compose up --build
```

To use `openai` backends in the compose demo, put `OPENAI_API_KEY` and backend overrides in `.env` beside `docker-compose.yml`.

Open:

```text
Streamlit: http://localhost:8501
FastAPI:   http://localhost:8080
Triton:    http://localhost:8001
```

## Advanced GPU / FLUX.2 Validation

On an NVIDIA GPU machine, start only the API service with the GPU overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d --no-deps api
```

The overlay installs `[image]` extras, switches `IMAGE_BACKEND=flux2`, and sets `REQUIRE_TRITON=0` so template scoring falls back to the local scorer. The first request downloads model weights into the `hf-cache` volume.

Full VM procedure:

```text
docs/runbooks/gcp-flux2-validation.md
```

## Roadmap

1. Polish sample demo set and README.
2. Replace Mock Product Analysis with real VLM analysis.
3. Add product-preserving segmentation and composition.
4. Add lightweight RAG marketing guidance.
5. Add revision/evaluation loop.
6. Package final portfolio with screenshots, architecture diagram, and latency/cost notes.

FastMCP is intentionally deferred. It can later expose the studio as agent-callable tools such as `generate_dessert_ad`, generation log lookup, result retrieval, and template scoring.
```

- [ ] **Step 2: Check README keeps required commands**

Run:

```bash
rg -n "pytest -q|ruff check|uvicorn api.main|streamlit run|docker compose|gcp-flux2-validation|COPY_BACKEND|IMAGE_BACKEND" README.md
```

Expected: each command/config topic appears at least once.

- [ ] **Step 3: Commit README**

Run:

```bash
git add README.md
git commit -m "Rewrite README for evaluator demo"
```

Expected:

```text
[main <hash>] Rewrite README for evaluator demo
```

## Task 4: Full Verification And Manual Smoke

**Files:**
- No source changes unless fixes are required.

- [ ] **Step 1: Run full tests**

Run:

```bash
.venv/bin/pytest -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 2: Run full lint**

Run:

```bash
.venv/bin/ruff check .
```

Expected:

```text
All checks passed!
```

- [ ] **Step 3: Run Streamlit smoke**

Terminal 1:

```bash
.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```bash
.venv/bin/streamlit run app/streamlit_app.py --server.headless true --server.port 8501 --server.address 127.0.0.1
```

Manual browser check:

- Open `http://127.0.0.1:8501`.
- Confirm the `데모 샘플` selector exists.
- Select each sample and confirm text defaults change.
- Generate one sample with mock backends.
- Confirm result still shows demo analysis, representative banner, copy cards, download button, and expanders.

- [ ] **Step 4: Commit verification fixes if needed**

Only if fixes were required:

```bash
git add app/streamlit_app.py README.md src/dessert_ad_studio/demo_samples.py tests/test_demo_samples.py
git commit -m "Fix demo sample verification issues"
```

Expected if no fixes were required:

```text
No commit needed.
```

## Self-Review Notes

- Spec coverage: The plan covers reusable sample data, Streamlit sample selector, README rewrite, tests, and manual smoke. Real VLM/RAG/segmentation/FastMCP remain out of scope.
- Placeholder scan: No TBD/TODO/fill-in placeholders are present.
- Type consistency: `DemoSample` fields match `GenerationRequest` schema aliases and Streamlit option values.
