# Dessert Ad Studio Triton + FLUX.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a course-aligned cafe/dessert ad-generation prototype with Streamlit UI, FastAPI backend, mandatory Triton ONNX template scoring, structured logs, and a configurable FLUX.2 image-generation backend.

**Architecture:** Streamlit collects campaign inputs and calls FastAPI. FastAPI renders prompts, calls Triton `template_scorer` to rank visual templates, generates Korean ad copy, then dispatches image generation through a backend adapter. The default backend is deterministic mock output for local tests; FLUX.2 is the primary modern local model target when the VM can support it.

**Tech Stack:** Python 3.11+, Streamlit, FastAPI, Pydantic, Pillow, pytest, httpx, ONNX, Triton Inference Server HTTP client, Docker Compose, configurable Diffusers/FLUX.2 backend.

---

## Source documents

- Design spec: `docs/superpowers/specs/2026-06-09-cafe-dessert-reference-template-ad-generator-design.md`
- Course alignment: `docs/reference/class-materials-alignment.md`
- Short execution plan: `.omx/plans/part4-next-implementation-plan.md`

## File structure

Create or modify these files:

- `pyproject.toml` — package metadata, runtime dependencies, pytest config.
- `.gitignore` — ignore secrets, generated outputs, local model files, Python caches.
- `.env.example` — documented local configuration without secrets.
- `README.md` — setup, run, Triton smoke, demo flow.
- `src/dessert_ad_studio/__init__.py` — package marker and version.
- `src/dessert_ad_studio/schemas.py` — request/response Pydantic models shared by API and tests.
- `src/dessert_ad_studio/prompts.py` — campaign/template prompt rendering and feature extraction.
- `src/dessert_ad_studio/generation_logger.py` — JSONL generation log writer.
- `src/dessert_ad_studio/backends/__init__.py` — backend exports.
- `src/dessert_ad_studio/backends/mock.py` — deterministic local copy/image backend.
- `src/dessert_ad_studio/backends/flux2.py` — guarded FLUX.2 Diffusers adapter.
- `src/dessert_ad_studio/triton.py` — Triton HTTP client and local scorer fallback for tests.
- `api/main.py` — FastAPI service endpoints.
- `app/streamlit_app.py` — Streamlit frontend.
- `scripts/export_template_scorer_onnx.py` — creates `models/template_scorer/1/model.onnx`.
- `scripts/triton_smoke.py` — health, model readiness, and inference checks.
- `models/template_scorer/config.pbtxt` — Triton model config.
- `Dockerfile.api` — FastAPI container.
- `Dockerfile.app` — Streamlit container.
- `docker-compose.yml` — app, API, and Triton services.
- `tests/conftest.py` — test path setup.
- `tests/test_prompts.py` — prompt and feature rendering tests.
- `tests/test_generation_logger.py` — JSONL log test.
- `tests/test_mock_backend.py` — deterministic backend test.
- `tests/test_triton_local_scorer.py` — template scoring shape/ranking test.
- `tests/test_api.py` — FastAPI endpoint tests.

## Implementation tasks

### Preflight: Git repository check

**Files:**
- Create when missing: `.git/`

- [ ] **Step 1: Initialize git if the workspace is not already a repository**

Run:

```bash
git rev-parse --is-inside-work-tree || git init
```

Expected output in a new workspace includes:

```text
Initialized empty Git repository
```

- [ ] **Step 2: Confirm repository status works**

Run:

```bash
git status --short
```

Expected: exits 0. Existing uncommitted planning documents may be listed.

### Task 1: Project skeleton and dependency contract

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `src/dessert_ad_studio/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create the initial package files**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "dessert-ad-studio"
version = "0.1.0"
description = "Cafe and dessert ad generation prototype with Streamlit, FastAPI, Triton, and FLUX.2-ready backend adapters."
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "streamlit>=1.35",
  "pydantic>=2.7",
  "pillow>=10.3",
  "python-multipart>=0.0.9",
  "httpx>=0.27",
  "numpy>=1.26",
  "onnx>=1.16",
  "tritonclient[http]>=2.45",
]

[project.optional-dependencies]
image = [
  "torch>=2.3",
  "diffusers>=0.31",
  "transformers>=4.44",
  "accelerate>=0.33",
  "safetensors>=0.4",
]
dev = [
  "pytest>=8.2",
  "ruff>=0.5",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
line-length = 100
target-version = "py311"
```

Create `.gitignore`:

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
*.pyc
outputs/
logs/
models/**/1/model.onnx
models/**/1/*.plan
models/**/1/*.engine
*.log
.DS_Store
```

Create `.env.example`:

```bash
API_BASE_URL=http://localhost:8000
TRITON_URL=localhost:8001
REQUIRE_TRITON=0
IMAGE_BACKEND=mock
FLUX2_MODEL_ID=black-forest-labs/FLUX.2-klein
OUTPUT_DIR=outputs
GENERATION_LOG_PATH=logs/generations.jsonl
```

Create `README.md`:

```markdown
# Dessert Ad Studio

Cafe/dessert ad-generation prototype for small business owners.

## MVP flow

1. User enters campaign purpose, tone, product name, and style preferences in Streamlit.
2. Streamlit calls FastAPI.
3. FastAPI renders prompts and calls Triton `template_scorer`.
4. FastAPI returns three Korean ad-copy candidates and one SNS-ready image path.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run tests

```bash
pytest -q
```

## Run API

```bash
uvicorn api.main:app --reload --port 8000
```

## Run Streamlit

```bash
streamlit run app/streamlit_app.py
```

## Export Triton model

```bash
python scripts/export_template_scorer_onnx.py
```

## Triton smoke flow

```bash
docker compose up triton -d
python scripts/triton_smoke.py
```

## Configuration

Copy `.env.example` to `.env` and edit local values. Do not commit `.env`.
```

Create `src/dessert_ad_studio/__init__.py`:

```python
"""Dessert Ad Studio package."""

__version__ = "0.1.0"
```

Create `tests/conftest.py`:

```python
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
```

- [ ] **Step 2: Verify package imports**

Run:

```bash
python - <<'PY'
import dessert_ad_studio
print(dessert_ad_studio.__version__)
PY
```

Expected output:

```text
0.1.0
```

- [ ] **Step 3: Commit skeleton**

```bash
git add pyproject.toml .gitignore .env.example README.md src/dessert_ad_studio/__init__.py tests/conftest.py
git commit -m "Establish the prototype package boundary

Constraint: course project needs Streamlit, FastAPI, Triton, and image-backend seams
Confidence: high
Scope-risk: narrow
Tested: python package import
Not-tested: runtime service startup"
```

### Task 2: Shared schemas and prompt/template engine

**Files:**
- Create: `src/dessert_ad_studio/schemas.py`
- Create: `src/dessert_ad_studio/prompts.py`
- Create: `tests/test_prompts.py`

- [ ] **Step 1: Write prompt tests first**

Create `tests/test_prompts.py`:

```python
from dessert_ad_studio.prompts import build_copy_prompt, build_image_prompt, template_features
from dessert_ad_studio.schemas import GenerationRequest


def sample_request() -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="new_menu",
        product_name="딸기 크림 크루아상",
        tone="warm",
        template_hint="cozy_cafe",
        price_text="6,800원",
        user_constraints="봄 시즌 한정 느낌",
    )


def test_copy_prompt_contains_required_korean_context() -> None:
    prompt = build_copy_prompt(sample_request())

    assert "딸기 크림 크루아상" in prompt
    assert "신메뉴" in prompt
    assert "따뜻한" in prompt
    assert "3개" in prompt


def test_image_prompt_contains_template_and_constraints() -> None:
    prompt = build_image_prompt(sample_request(), ranked_template="cozy_cafe")

    assert "cozy cafe" in prompt.lower()
    assert "SNS 정사각형 광고 이미지" in prompt
    assert "봄 시즌 한정 느낌" in prompt


def test_template_features_are_stable_vector() -> None:
    features = template_features(sample_request())

    assert len(features) == 8
    assert all(isinstance(value, float) for value in features)
    assert features[0] == 1.0
```

- [ ] **Step 2: Run tests to verify they fail before implementation**

Run:

```bash
pytest tests/test_prompts.py -q
```

Expected: FAIL because `dessert_ad_studio.prompts` and `dessert_ad_studio.schemas` do not exist.

- [ ] **Step 3: Implement schemas**

Create `src/dessert_ad_studio/schemas.py`:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CampaignPurpose = Literal["new_menu", "seasonal_event", "discount", "brand_awareness"]
Tone = Literal["warm", "premium", "playful", "clean"]
TemplateHint = Literal["cozy_cafe", "minimal_premium", "cute_dessert", "seasonal_event"]


class GenerationRequest(BaseModel):
    campaign_purpose: CampaignPurpose
    product_name: str = Field(min_length=1, max_length=80)
    tone: Tone
    template_hint: TemplateHint
    price_text: str = Field(default="", max_length=40)
    user_constraints: str = Field(default="", max_length=300)
    reference_image_path: str | None = None


class CopyOption(BaseModel):
    headline: str
    body: str
    call_to_action: str


class TemplateRanking(BaseModel):
    template_name: TemplateHint
    score: float
    scorer: str
    latency_ms: float


class GenerationResponse(BaseModel):
    copy_options: list[CopyOption]
    selected_template: TemplateRanking
    image_path: str
    image_backend: str
    prompt_summary: str
    elapsed_ms: float
```

- [ ] **Step 4: Implement prompt rendering and Triton feature vector**

Create `src/dessert_ad_studio/prompts.py`:

```python
from __future__ import annotations

from dessert_ad_studio.schemas import GenerationRequest

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
            "출력은 헤드라인, 본문, 행동유도문구를 가진 후보 3개로 제한한다.",
        ]
    )


def build_image_prompt(request: GenerationRequest, ranked_template: str) -> str:
    return "\n".join(
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
```

- [ ] **Step 5: Run tests**

Run:

```bash
pytest tests/test_prompts.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit prompt engine**

```bash
git add src/dessert_ad_studio/schemas.py src/dessert_ad_studio/prompts.py tests/test_prompts.py
git commit -m "Make campaign choices render into stable prompts

Constraint: template ranking needs an eight-value feature vector for Triton
Rejected: free-form prompt assembly in the API | hard to test and log consistently
Confidence: high
Scope-risk: narrow
Tested: pytest tests/test_prompts.py -q"
```

### Task 3: Generation logging

**Files:**
- Create: `src/dessert_ad_studio/generation_logger.py`
- Create: `tests/test_generation_logger.py`

- [ ] **Step 1: Write logging test first**

Create `tests/test_generation_logger.py`:

```python
import json

from dessert_ad_studio.generation_logger import GenerationLogger


def test_generation_logger_writes_one_json_line(tmp_path) -> None:
    log_path = tmp_path / "generations.jsonl"
    logger = GenerationLogger(log_path)

    logger.write(
        {
            "campaign_purpose": "new_menu",
            "template": "cozy_cafe",
            "image_backend": "mock",
            "triton_latency_ms": 4.2,
        }
    )

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["campaign_purpose"] == "new_menu"
    assert payload["template"] == "cozy_cafe"
    assert "created_at" in payload
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_generation_logger.py -q
```

Expected: FAIL because `generation_logger.py` does not exist.

- [ ] **Step 3: Implement JSONL logger**

Create `src/dessert_ad_studio/generation_logger.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


class GenerationLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        enriched = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(enriched, ensure_ascii=False, sort_keys=True) + "\n")
```

- [ ] **Step 4: Run logging test**

Run:

```bash
pytest tests/test_generation_logger.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit logger**

```bash
git add src/dessert_ad_studio/generation_logger.py tests/test_generation_logger.py
git commit -m "Record generation metadata for evaluation

Constraint: final report needs latency, backend, and template evidence
Confidence: high
Scope-risk: narrow
Tested: pytest tests/test_generation_logger.py -q"
```

### Task 4: Deterministic mock copy and image backend

**Files:**
- Create: `src/dessert_ad_studio/backends/__init__.py`
- Create: `src/dessert_ad_studio/backends/mock.py`
- Create: `tests/test_mock_backend.py`

- [ ] **Step 1: Write backend test first**

Create `tests/test_mock_backend.py`:

```python
from pathlib import Path

from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.prompts import build_image_prompt
from dessert_ad_studio.schemas import GenerationRequest


def test_mock_backend_returns_three_copy_options_and_image(tmp_path: Path) -> None:
    request = GenerationRequest(
        campaign_purpose="discount",
        product_name="초코 마들렌",
        tone="playful",
        template_hint="cute_dessert",
        price_text="2개 구매 시 10% 할인",
    )
    backend = MockAdBackend(output_dir=tmp_path)

    copy_options = backend.generate_copy(request)
    image_path = backend.generate_image(
        request=request,
        image_prompt=build_image_prompt(request, ranked_template="cute_dessert"),
    )

    assert len(copy_options) == 3
    assert copy_options[0].headline.startswith("초코 마들렌")
    assert Path(image_path).exists()
    assert Path(image_path).suffix == ".png"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_mock_backend.py -q
```

Expected: FAIL because backend files do not exist.

- [ ] **Step 3: Implement mock backend**

Create `src/dessert_ad_studio/backends/__init__.py`:

```python
from dessert_ad_studio.backends.mock import MockAdBackend

__all__ = ["MockAdBackend"]
```

Create `src/dessert_ad_studio/backends/mock.py`:

```python
from __future__ import annotations

from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont

from dessert_ad_studio.schemas import CopyOption, GenerationRequest


class MockAdBackend:
    name = "mock"

    def __init__(self, output_dir: str | Path = "outputs") -> None:
        self.output_dir = Path(output_dir)

    def generate_copy(self, request: GenerationRequest) -> list[CopyOption]:
        product = request.product_name
        return [
            CopyOption(
                headline=f"{product}, 오늘의 달콤한 선택",
                body=f"{request.price_text or '지금 매장에서'} 만나는 기분 좋은 디저트 타임.",
                call_to_action="오늘 매장에서 만나보세요.",
            ),
            CopyOption(
                headline=f"{product}로 채우는 카페 한 컷",
                body="따뜻한 커피와 잘 어울리는 시즌 추천 메뉴입니다.",
                call_to_action="SNS 저장하고 방문해보세요.",
            ),
            CopyOption(
                headline=f"작지만 확실한 행복, {product}",
                body="부담 없이 즐기는 달콤함을 깔끔한 광고 톤으로 전합니다.",
                call_to_action="지금 바로 주문하세요.",
            ),
        ]

    def generate_image(self, request: GenerationRequest, image_prompt: str) -> str:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{request.product_name.replace(' ', '_')}_mock_ad.png"
        path = self.output_dir / filename

        image = Image.new("RGB", (1024, 1024), color=(250, 238, 224))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        draw.rounded_rectangle((90, 120, 934, 780), radius=48, fill=(255, 250, 244), outline=(120, 80, 60), width=4)
        draw.ellipse((332, 230, 692, 590), fill=(230, 120, 140), outline=(90, 60, 50), width=4)
        draw.text((140, 830), request.product_name, fill=(80, 45, 35), font=font)
        prompt_line = textwrap.shorten(image_prompt.replace("\n", " "), width=90)
        draw.text((140, 870), prompt_line, fill=(110, 80, 70), font=font)
        image.save(path)
        return str(path)
```

- [ ] **Step 4: Run backend test**

Run:

```bash
pytest tests/test_mock_backend.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit mock backend**

```bash
git add src/dessert_ad_studio/backends tests/test_mock_backend.py
git commit -m "Provide deterministic generation for local service tests

Constraint: demo flow must work before paid API or GPU setup
Rejected: network-only image backend | unreliable for early verification
Confidence: high
Scope-risk: narrow
Tested: pytest tests/test_mock_backend.py -q"
```

### Task 5: ONNX `template_scorer` export for Triton

**Files:**
- Create: `scripts/export_template_scorer_onnx.py`
- Create: `models/template_scorer/config.pbtxt`
- Create: `tests/test_triton_local_scorer.py`

- [ ] **Step 1: Write local scorer test first**

Create `tests/test_triton_local_scorer.py`:

```python
from dessert_ad_studio.schemas import GenerationRequest
from dessert_ad_studio.triton import LocalTemplateScorer


def test_local_template_scorer_returns_ranked_template() -> None:
    request = GenerationRequest(
        campaign_purpose="seasonal_event",
        product_name="벚꽃 딸기 케이크",
        tone="warm",
        template_hint="seasonal_event",
    )
    ranking = LocalTemplateScorer().rank(request)

    assert ranking.template_name in {"cozy_cafe", "minimal_premium", "cute_dessert", "seasonal_event"}
    assert 0.0 <= ranking.score <= 1.0
    assert ranking.scorer == "local-template-scorer"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_triton_local_scorer.py -q
```

Expected: FAIL because `dessert_ad_studio.triton` does not exist.

- [ ] **Step 3: Implement scorer client and local fallback**

Create `src/dessert_ad_studio/triton.py`:

```python
from __future__ import annotations

from time import perf_counter

import numpy as np

from dessert_ad_studio.prompts import template_features
from dessert_ad_studio.schemas import GenerationRequest, TemplateHint, TemplateRanking

TEMPLATES: tuple[TemplateHint, ...] = (
    "cozy_cafe",
    "minimal_premium",
    "cute_dessert",
    "seasonal_event",
)


class LocalTemplateScorer:
    def rank(self, request: GenerationRequest) -> TemplateRanking:
        started = perf_counter()
        features = np.array(template_features(request), dtype=np.float32)
        weights = np.array(
            [
                [0.9, 0.2, 0.5, 0.6, 0.9, 0.4, 0.5, 0.7],
                [0.4, 0.3, 0.5, 0.8, 0.3, 1.0, 0.2, 0.9],
                [0.7, 0.5, 0.8, 0.4, 0.7, 0.2, 1.0, 0.4],
                [0.5, 1.0, 0.6, 0.5, 0.8, 0.5, 0.7, 0.5],
            ],
            dtype=np.float32,
        )
        scores = weights @ features
        best_index = int(np.argmax(scores))
        normalized = float(1.0 / (1.0 + np.exp(-scores[best_index])))
        elapsed_ms = (perf_counter() - started) * 1000
        return TemplateRanking(
            template_name=TEMPLATES[best_index],
            score=normalized,
            scorer="local-template-scorer",
            latency_ms=elapsed_ms,
        )


class TritonTemplateScorer:
    def __init__(self, url: str = "localhost:8001") -> None:
        self.url = url

    def rank(self, request: GenerationRequest) -> TemplateRanking:
        import tritonclient.http as httpclient

        started = perf_counter()
        client = httpclient.InferenceServerClient(url=self.url)
        features = np.array([template_features(request)], dtype=np.float32)
        infer_input = httpclient.InferInput("features", features.shape, "FP32")
        infer_input.set_data_from_numpy(features)
        output = httpclient.InferRequestedOutput("scores")
        response = client.infer("template_scorer", [infer_input], outputs=[output])
        scores = response.as_numpy("scores")[0]
        best_index = int(np.argmax(scores))
        elapsed_ms = (perf_counter() - started) * 1000
        return TemplateRanking(
            template_name=TEMPLATES[best_index],
            score=float(scores[best_index]),
            scorer="triton-template-scorer",
            latency_ms=elapsed_ms,
        )
```

- [ ] **Step 4: Implement ONNX export script**

Create `scripts/export_template_scorer_onnx.py`:

```python
from __future__ import annotations

from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper


def build_model() -> onnx.ModelProto:
    features = helper.make_tensor_value_info("features", TensorProto.FLOAT, [None, 8])
    scores = helper.make_tensor_value_info("scores", TensorProto.FLOAT, [None, 4])

    weights = np.array(
        [
            [0.9, 0.4, 0.7, 0.5],
            [0.2, 0.3, 0.5, 1.0],
            [0.5, 0.5, 0.8, 0.6],
            [0.6, 0.8, 0.4, 0.5],
            [0.9, 0.3, 0.7, 0.8],
            [0.4, 1.0, 0.2, 0.5],
            [0.5, 0.2, 1.0, 0.7],
            [0.7, 0.9, 0.4, 0.5],
        ],
        dtype=np.float32,
    )
    bias = np.array([0.05, 0.05, 0.05, 0.05], dtype=np.float32)

    graph = helper.make_graph(
        nodes=[
            helper.make_node("MatMul", ["features", "weights"], ["raw_scores"]),
            helper.make_node("Add", ["raw_scores", "bias"], ["biased_scores"]),
            helper.make_node("Sigmoid", ["biased_scores"], ["scores"]),
        ],
        name="template_scorer",
        inputs=[features],
        outputs=[scores],
        initializer=[
            numpy_helper.from_array(weights, name="weights"),
            numpy_helper.from_array(bias, name="bias"),
        ],
    )
    model = helper.make_model(graph, producer_name="dessert-ad-studio")
    onnx.checker.check_model(model)
    return model


def main() -> None:
    output_path = Path("models/template_scorer/1/model.onnx")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(build_model(), output_path)
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
```

Create `models/template_scorer/config.pbtxt`:

```text
name: "template_scorer"
platform: "onnxruntime_onnx"
max_batch_size: 16

input [
  {
    name: "features"
    data_type: TYPE_FP32
    dims: [ 8 ]
  }
]

output [
  {
    name: "scores"
    data_type: TYPE_FP32
    dims: [ 4 ]
  }
]

instance_group [
  {
    count: 1
    kind: KIND_CPU
  }
]
```

- [ ] **Step 5: Run tests and export model**

Run:

```bash
pytest tests/test_triton_local_scorer.py -q
python scripts/export_template_scorer_onnx.py
test -f models/template_scorer/1/model.onnx
```

Expected: pytest PASS, script prints `wrote models/template_scorer/1/model.onnx`, and `test -f` exits 0.

- [ ] **Step 6: Commit Triton model files**

```bash
git add src/dessert_ad_studio/triton.py scripts/export_template_scorer_onnx.py models/template_scorer/config.pbtxt tests/test_triton_local_scorer.py
git commit -m "Serve template choice through an ONNX scorer boundary

Constraint: Triton is required by the project scope and course material
Rejected: serving the full diffusion pipeline in Triton | high setup risk on the L4 VM
Confidence: high
Scope-risk: moderate
Tested: pytest tests/test_triton_local_scorer.py -q; python scripts/export_template_scorer_onnx.py"
```

### Task 6: Triton smoke script

**Files:**
- Create: `scripts/triton_smoke.py`

- [ ] **Step 1: Create smoke script**

Create `scripts/triton_smoke.py`:

```python
from __future__ import annotations

import os

import numpy as np
import tritonclient.http as httpclient


def main() -> None:
    url = os.getenv("TRITON_URL", "localhost:8001")
    client = httpclient.InferenceServerClient(url=url)
    assert client.is_server_ready(), "Triton server is not ready"
    assert client.is_model_ready("template_scorer"), "template_scorer is not ready"

    features = np.array([[1, 0, 0, 0, 1, 0, 0, 0]], dtype=np.float32)
    infer_input = httpclient.InferInput("features", features.shape, "FP32")
    infer_input.set_data_from_numpy(features)
    output = httpclient.InferRequestedOutput("scores")
    response = client.infer("template_scorer", [infer_input], outputs=[output])
    scores = response.as_numpy("scores")

    assert scores.shape == (1, 4), f"unexpected score shape: {scores.shape}"
    print({"ready": True, "model": "template_scorer", "scores": scores.tolist()})


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run smoke only when Triton is running**

Run after `docker compose up triton -d` exists in Task 10:

```bash
python scripts/triton_smoke.py
```

Expected output includes:

```text
{'ready': True, 'model': 'template_scorer'
```

- [ ] **Step 3: Commit smoke script**

```bash
git add scripts/triton_smoke.py
git commit -m "Add a direct Triton readiness and inference smoke check

Constraint: final acceptance requires evidence from Triton, not only local scoring
Confidence: high
Scope-risk: narrow
Tested: python scripts/triton_smoke.py against a running Triton service
Not-tested: Triton smoke before Docker Compose exists"
```

### Task 7: FastAPI service boundary

**Files:**
- Create: `api/main.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write API tests first**

Create `tests/test_api.py`:

```python
from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_generate_uses_template_ranking_and_returns_copy() -> None:
    response = client.post(
        "/generate",
        json={
            "campaign_purpose": "new_menu",
            "product_name": "말차 푸딩",
            "tone": "clean",
            "template_hint": "minimal_premium",
            "price_text": "5,500원",
            "user_constraints": "깔끔한 프리미엄 느낌",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["copy_options"]) == 3
    assert payload["selected_template"]["scorer"] in {
        "local-template-scorer",
        "triton-template-scorer",
    }
    assert payload["image_backend"] == "mock"
    assert payload["image_path"].endswith(".png")
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```bash
pytest tests/test_api.py -q
```

Expected: FAIL because `api/main.py` does not exist.

- [ ] **Step 3: Implement FastAPI app**

Create `api/main.py`:

```python
from __future__ import annotations

import os
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, HTTPException

from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.generation_logger import GenerationLogger
from dessert_ad_studio.prompts import build_image_prompt
from dessert_ad_studio.schemas import GenerationRequest, GenerationResponse
from dessert_ad_studio.triton import LocalTemplateScorer, TritonTemplateScorer

app = FastAPI(title="Dessert Ad Studio API")


def get_template_scorer():
    require_triton = os.getenv("REQUIRE_TRITON", "0") == "1"
    triton_url = os.getenv("TRITON_URL", "localhost:8001")
    if require_triton:
        return TritonTemplateScorer(url=triton_url)
    try:
        return TritonTemplateScorer(url=triton_url)
    except Exception:
        return LocalTemplateScorer()


def get_backend() -> MockAdBackend:
    backend_name = os.getenv("IMAGE_BACKEND", "mock")
    if backend_name != "mock":
        raise HTTPException(status_code=501, detail=f"image backend is not enabled in API tests: {backend_name}")
    return MockAdBackend(output_dir=os.getenv("OUTPUT_DIR", "outputs"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/rank-templates")
def rank_templates(request: GenerationRequest):
    scorer = get_template_scorer()
    try:
        return scorer.rank(request)
    except Exception as exc:
        if os.getenv("REQUIRE_TRITON", "0") == "1":
            raise HTTPException(status_code=503, detail=f"Triton template scoring failed: {exc}") from exc
        return LocalTemplateScorer().rank(request)


@app.post("/generate", response_model=GenerationResponse)
def generate(request: GenerationRequest) -> GenerationResponse:
    started = perf_counter()
    ranking = rank_templates(request)
    backend = get_backend()
    copy_options = backend.generate_copy(request)
    image_prompt = build_image_prompt(request, ranked_template=ranking.template_name)
    image_path = backend.generate_image(request, image_prompt=image_prompt)
    elapsed_ms = (perf_counter() - started) * 1000

    logger = GenerationLogger(Path(os.getenv("GENERATION_LOG_PATH", "logs/generations.jsonl")))
    logger.write(
        {
            "campaign_purpose": request.campaign_purpose,
            "template": ranking.template_name,
            "template_scorer": ranking.scorer,
            "triton_latency_ms": ranking.latency_ms,
            "image_backend": backend.name,
            "elapsed_ms": elapsed_ms,
            "image_path": image_path,
        }
    )

    return GenerationResponse(
        copy_options=copy_options,
        selected_template=ranking,
        image_path=image_path,
        image_backend=backend.name,
        prompt_summary=image_prompt,
        elapsed_ms=elapsed_ms,
    )
```

- [ ] **Step 4: Run API tests**

Run:

```bash
pytest tests/test_api.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit API**

```bash
git add api/main.py tests/test_api.py
git commit -m "Expose generation through a FastAPI service boundary

Constraint: course material requires a model-serving API layer before UI integration
Rejected: Streamlit-only implementation | hides serving and Triton integration
Confidence: high
Scope-risk: moderate
Tested: pytest tests/test_api.py -q"
```

### Task 8: Streamlit UI

**Files:**
- Create: `app/streamlit_app.py`

- [ ] **Step 1: Implement Streamlit app**

Create `app/streamlit_app.py`:

```python
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
```

- [ ] **Step 2: Run static import check**

Run:

```bash
python -m py_compile app/streamlit_app.py
```

Expected: exits 0.

- [ ] **Step 3: Commit UI**

```bash
git add app/streamlit_app.py
git commit -m "Add the Streamlit owner-facing ad generation UI

Constraint: course material prioritizes a web prototype as the first visible service layer
Confidence: high
Scope-risk: narrow
Tested: python -m py_compile app/streamlit_app.py"
```

### Task 9: Guarded FLUX.2 backend adapter

**Files:**
- Create: `src/dessert_ad_studio/backends/flux2.py`

- [ ] **Step 1: Implement configurable FLUX.2 adapter**

Create `src/dessert_ad_studio/backends/flux2.py`:

```python
from __future__ import annotations

import os
from pathlib import Path

from dessert_ad_studio.schemas import GenerationRequest


class Flux2Backend:
    name = "flux2"

    def __init__(self, output_dir: str | Path = "outputs", model_id: str | None = None) -> None:
        self.output_dir = Path(output_dir)
        self.model_id = model_id or os.getenv("FLUX2_MODEL_ID", "black-forest-labs/FLUX.2-klein")
        self._pipeline = None

    def _load_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline

        try:
            import torch
            from diffusers import DiffusionPipeline
        except Exception as exc:
            raise RuntimeError(
                "FLUX.2 backend requires installing the image extras: pip install -e '.[image]'"
            ) from exc

        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        pipeline = DiffusionPipeline.from_pretrained(self.model_id, torch_dtype=dtype)
        if torch.cuda.is_available():
            pipeline = pipeline.to("cuda")
        else:
            pipeline.enable_model_cpu_offload()
        self._pipeline = pipeline
        return pipeline

    def generate_image(self, request: GenerationRequest, image_prompt: str) -> str:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        pipeline = self._load_pipeline()
        result = pipeline(
            prompt=image_prompt,
            width=1024,
            height=1024,
            num_inference_steps=28,
            guidance_scale=3.5,
        )
        image = result.images[0]
        path = self.output_dir / f"{request.product_name.replace(' ', '_')}_flux2_ad.png"
        image.save(path)
        return str(path)
```

- [ ] **Step 2: Run syntax check without loading the model**

Run:

```bash
python -m py_compile src/dessert_ad_studio/backends/flux2.py
```

Expected: exits 0 and does not download a model.

- [ ] **Step 3: Commit FLUX.2 adapter**

```bash
git add src/dessert_ad_studio/backends/flux2.py
git commit -m "Keep FLUX.2 behind a configurable image backend adapter

Constraint: FLUX.2 is the primary modern image target but local GPU feasibility must be verified on the VM
Rejected: hard-coding SDXL as the main model | weaker 2026 project positioning
Confidence: medium
Scope-risk: moderate
Tested: python -m py_compile src/dessert_ad_studio/backends/flux2.py
Not-tested: full FLUX.2 generation without the target VM model cache"
```

### Task 10: Docker Compose, Triton service, and final verification

**Files:**
- Create: `Dockerfile.api`
- Create: `Dockerfile.app`
- Create: `docker-compose.yml`
- Modify: `README.md`

- [ ] **Step 1: Create API Dockerfile**

Create `Dockerfile.api`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY api ./api
RUN pip install --no-cache-dir -e .

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create Streamlit Dockerfile**

Create `Dockerfile.app`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY app ./app
RUN pip install --no-cache-dir -e .

EXPOSE 8501
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
```

- [ ] **Step 3: Create docker-compose with Triton**

Create `docker-compose.yml`:

```yaml
services:
  triton:
    image: nvcr.io/nvidia/tritonserver:24.05-py3
    command: ["tritonserver", "--model-repository=/models"]
    ports:
      - "8000:8000"
      - "8001:8001"
      - "8002:8002"
    volumes:
      - ./models:/models:ro

  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    environment:
      TRITON_URL: triton:8001
      REQUIRE_TRITON: "1"
      IMAGE_BACKEND: mock
      OUTPUT_DIR: /app/outputs
      GENERATION_LOG_PATH: /app/logs/generations.jsonl
    ports:
      - "8080:8000"
    volumes:
      - ./outputs:/app/outputs
      - ./logs:/app/logs
    depends_on:
      - triton

  app:
    build:
      context: .
      dockerfile: Dockerfile.app
    environment:
      API_BASE_URL: http://api:8000
    ports:
      - "8501:8501"
    volumes:
      - ./outputs:/app/outputs
    depends_on:
      - api
```

- [ ] **Step 4: Append final run commands to README**

Append to `README.md`:

```markdown

## Docker Compose demo

Generate the ONNX model before starting Triton:

```bash
python scripts/export_template_scorer_onnx.py
docker compose up --build
```

Open Streamlit:

```text
http://localhost:8501
```

FastAPI is exposed on:

```text
http://localhost:8080
```

Triton HTTP is exposed on:

```text
http://localhost:8001
```
```

- [ ] **Step 5: Run final local verification**

Run:

```bash
pytest -q
python -m py_compile app/streamlit_app.py api/main.py src/dessert_ad_studio/*.py src/dessert_ad_studio/backends/*.py
python scripts/export_template_scorer_onnx.py
```

Expected: all pytest tests pass, py_compile exits 0, and ONNX export prints `wrote models/template_scorer/1/model.onnx`.

- [ ] **Step 6: Run Triton verification when Docker is available**

Run:

```bash
docker compose up triton -d
python scripts/triton_smoke.py
```

Expected: smoke script prints `ready=True` data and score shape `(1, 4)`.

- [ ] **Step 7: Commit deployment files**

```bash
git add Dockerfile.api Dockerfile.app docker-compose.yml README.md
git commit -m "Make the service reproducible with Docker and Triton

Constraint: course delivery requires Docker evidence and Triton model serving
Confidence: medium
Scope-risk: moderate
Directive: keep the full diffusion model outside Triton unless a separate VM feasibility test proves it stable
Tested: pytest -q; python scripts/export_template_scorer_onnx.py; python scripts/triton_smoke.py
Not-tested: FLUX.2 image generation inside Docker"
```

## Final acceptance checklist

- [ ] `pytest -q` passes.
- [ ] `python scripts/export_template_scorer_onnx.py` creates `models/template_scorer/1/model.onnx`.
- [ ] Triton serves `template_scorer`.
- [ ] `python scripts/triton_smoke.py` returns a score array with shape `(1, 4)`.
- [ ] `uvicorn api.main:app --port 8000` serves `/health`.
- [ ] Streamlit can submit a generation request through FastAPI.
- [ ] A generation request creates a PNG under `outputs/`.
- [ ] A generation request appends one JSONL row under `logs/generations.jsonl`.
- [ ] README documents local setup, API run, Streamlit run, ONNX export, Triton smoke, and Docker Compose demo.
- [ ] FLUX.2 is documented as the primary modern local target; SDXL is only fallback/control evidence.
