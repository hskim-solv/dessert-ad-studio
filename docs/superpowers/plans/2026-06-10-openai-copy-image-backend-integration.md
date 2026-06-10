# OpenAI Copy/Image Backend Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mock copy/image generation with real OpenAI backends (GPT-5.4 Mini copy, gpt-image-1-mini images with reference-image edit mode) behind independently switchable adapters.

**Architecture:** Copy and image backends become separate protocols selected by `COPY_BACKEND` and `IMAGE_BACKEND` env vars (defaults stay `mock` so tests run without network). Reference images travel as base64 in the existing JSON request, get validated/normalized in a dedicated module, and switch the OpenAI image backend from generate to edit mode. Backends translate OpenAI SDK errors into a domain `AdBackendError` that FastAPI maps to Korean actionable HTTP errors — no silent fallback.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, Streamlit, Pillow, openai>=2.8 (Structured Outputs via `chat.completions.parse`, Images API generate/edit), python-dotenv, pytest with injected fake clients.

---

## Source documents

- Design spec: `docs/superpowers/specs/2026-06-10-openai-copy-image-backend-integration-design.md`
- Parent spec: `docs/superpowers/specs/2026-06-09-cafe-dessert-reference-template-ad-generator-design.md`

## File structure

Create:

- `src/dessert_ad_studio/backends/base.py` — `CopyBackend`/`ImageBackend` protocols and `AdBackendError`.
- `src/dessert_ad_studio/reference_image.py` — base64 decode, validation, PNG normalization.
- `src/dessert_ad_studio/backends/openai_copy.py` — Structured-Outputs copy backend.
- `src/dessert_ad_studio/backends/openai_image.py` — generate/edit image backend.
- `scripts/openai_smoke.py` — manual real-API smoke check (excluded from pytest).
- `tests/test_backend_base.py`, `tests/test_reference_image.py`, `tests/test_openai_copy_backend.py`, `tests/test_openai_image_backend.py`.

Modify:

- `src/dessert_ad_studio/schemas.py` — request reference fields, response `copy_backend`/`used_reference`.
- `src/dessert_ad_studio/prompts.py` — `build_image_prompt` gains `has_reference`.
- `src/dessert_ad_studio/backends/mock.py` — accepts `reference_image`, draws REF badge.
- `src/dessert_ad_studio/backends/flux2.py` — accepts and ignores `reference_image`.
- `src/dessert_ad_studio/backends/__init__.py` — exports.
- `api/main.py` — dual backend selection, reference decoding, error mapping, logging.
- `app/streamlit_app.py` — base64 upload, backend captions, error detail display.
- `tests/conftest.py` — hermetic backend env fixture.
- `tests/test_api.py`, `tests/test_mock_backend.py`, `tests/test_prompts.py` — updated coverage.
- `pyproject.toml`, `.env.example`, `docker-compose.yml`, `README.md`.

Model id caveat: `gpt-5.4-mini` and `gpt-image-1-mini` defaults follow the course guide; the smoke script (Task 9) is the runtime verification step. If an id is wrong, fix `.env` only — code reads env vars.

---

### Task 1: Backend protocols and domain error

**Files:**
- Create: `src/dessert_ad_studio/backends/base.py`
- Modify: `src/dessert_ad_studio/backends/__init__.py`
- Test: `tests/test_backend_base.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_backend_base.py`:

```python
from dessert_ad_studio.backends.base import AdBackendError, CopyBackend, ImageBackend
from dessert_ad_studio.backends.mock import MockAdBackend


def test_ad_backend_error_carries_status_and_detail() -> None:
    error = AdBackendError("한도 초과", status_code=503)

    assert error.detail == "한도 초과"
    assert error.status_code == 503
    assert str(error) == "한도 초과"


def test_ad_backend_error_defaults_to_503() -> None:
    assert AdBackendError("실패").status_code == 503


def test_mock_backend_satisfies_both_protocols() -> None:
    backend = MockAdBackend()

    assert isinstance(backend, CopyBackend)
    assert isinstance(backend, ImageBackend)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_backend_base.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'dessert_ad_studio.backends.base'`

- [ ] **Step 3: Implement base module**

Create `src/dessert_ad_studio/backends/base.py`:

```python
from __future__ import annotations

from typing import Protocol, runtime_checkable

from dessert_ad_studio.schemas import CopyOption, GenerationRequest


class AdBackendError(Exception):
    """User-facing backend failure with a Korean detail message."""

    def __init__(self, detail: str, status_code: int = 503) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@runtime_checkable
class CopyBackend(Protocol):
    """Generates three Korean ad-copy options.

    Implementations may expose ``model_id`` and ``last_usage`` attributes;
    the API logs them via ``getattr`` when present.
    """

    name: str

    def generate_copy(self, request: GenerationRequest) -> list[CopyOption]: ...


@runtime_checkable
class ImageBackend(Protocol):
    """Generates one ad image and returns the saved file path."""

    name: str

    def generate_image(
        self,
        request: GenerationRequest,
        image_prompt: str,
        reference_image: bytes | None = None,
    ) -> str: ...
```

Replace `src/dessert_ad_studio/backends/__init__.py` with:

```python
from dessert_ad_studio.backends.base import AdBackendError, CopyBackend, ImageBackend
from dessert_ad_studio.backends.mock import MockAdBackend

__all__ = ["AdBackendError", "CopyBackend", "ImageBackend", "MockAdBackend"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_backend_base.py -q`
Expected: PASS (3 passed). `isinstance` works because `MockAdBackend` already has `name`, `generate_copy`, and `generate_image` attributes; exact signatures align in Task 4.

- [ ] **Step 5: Commit**

```bash
git add src/dessert_ad_studio/backends/base.py src/dessert_ad_studio/backends/__init__.py tests/test_backend_base.py
git commit -m "Split copy and image generation into explicit contracts

Constraint: spec requires independently switchable copy/image backends with uniform error mapping
Confidence: high
Scope-risk: narrow
Tested: pytest tests/test_backend_base.py -q"
```

### Task 2: Reference image decode/validation module

**Files:**
- Create: `src/dessert_ad_studio/reference_image.py`
- Test: `tests/test_reference_image.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_reference_image.py`:

```python
import base64
import io

import pytest
from PIL import Image

from dessert_ad_studio.reference_image import (
    MAX_REFERENCE_IMAGE_BYTES,
    ReferenceImageError,
    decode_reference_image,
)


def encode_image(image_format: str) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color=(180, 90, 120)).save(buffer, format=image_format)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_none_and_empty_input_return_none() -> None:
    assert decode_reference_image(None) is None
    assert decode_reference_image("") is None


def test_jpeg_input_is_normalized_to_rgba_png_bytes() -> None:
    normalized = decode_reference_image(encode_image("JPEG"))

    assert normalized is not None
    with Image.open(io.BytesIO(normalized)) as image:
        assert image.format == "PNG"
        assert image.mode == "RGBA"


def test_invalid_base64_raises_korean_error() -> None:
    with pytest.raises(ReferenceImageError, match="base64"):
        decode_reference_image("not-base64!!!")


def test_oversized_payload_raises_size_error() -> None:
    oversized = base64.b64encode(b"x" * (MAX_REFERENCE_IMAGE_BYTES + 1)).decode("ascii")

    with pytest.raises(ReferenceImageError, match="10MB"):
        decode_reference_image(oversized)


def test_disallowed_format_raises_format_error() -> None:
    with pytest.raises(ReferenceImageError, match="PNG, JPEG, WEBP"):
        decode_reference_image(encode_image("GIF"))


def test_corrupt_image_raises_open_error() -> None:
    corrupt = base64.b64encode(b"definitely not an image").decode("ascii")

    with pytest.raises(ReferenceImageError, match="열 수 없습니다"):
        decode_reference_image(corrupt)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_reference_image.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'dessert_ad_studio.reference_image'`

- [ ] **Step 3: Implement the module**

Create `src/dessert_ad_studio/reference_image.py`:

```python
from __future__ import annotations

import base64
import io

from PIL import Image

MAX_REFERENCE_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}


class ReferenceImageError(ValueError):
    """Raised when an uploaded reference image cannot be used."""


def decode_reference_image(encoded: str | None) -> bytes | None:
    """Decode base64 input, validate it, and return normalized RGBA PNG bytes."""
    if not encoded:
        return None
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ReferenceImageError("참고 이미지 인코딩(base64)이 올바르지 않습니다.") from exc
    if len(raw) > MAX_REFERENCE_IMAGE_BYTES:
        raise ReferenceImageError("참고 이미지는 10MB 이하만 사용할 수 있습니다.")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image_format = (image.format or "").upper()
            if image_format not in ALLOWED_FORMATS:
                raise ReferenceImageError("PNG, JPEG, WEBP 형식의 참고 이미지만 지원합니다.")
            buffer = io.BytesIO()
            image.convert("RGBA").save(buffer, format="PNG")
    except ReferenceImageError:
        raise
    except Exception as exc:
        raise ReferenceImageError(
            "참고 이미지를 열 수 없습니다. 손상되지 않은 이미지인지 확인해주세요."
        ) from exc
    return buffer.getvalue()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_reference_image.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/dessert_ad_studio/reference_image.py tests/test_reference_image.py
git commit -m "Validate and normalize uploaded reference images

Constraint: spec caps decoded reference bytes at 10MB and normalizes to PNG before backend use
Rejected: passing raw upload bytes straight to the API | mislabeled formats break the edit call
Confidence: high
Scope-risk: narrow
Tested: pytest tests/test_reference_image.py -q"
```

### Task 3: Edit-mode line in the image prompt

**Files:**
- Modify: `src/dessert_ad_studio/prompts.py:48-60`
- Test: `tests/test_prompts.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_prompts.py`:

```python
def test_image_prompt_without_reference_has_no_preserve_line() -> None:
    prompt = build_image_prompt(sample_request(), ranked_template="cozy_cafe")

    assert "보존" not in prompt


def test_image_prompt_with_reference_prepends_preserve_instruction() -> None:
    prompt = build_image_prompt(sample_request(), ranked_template="cozy_cafe", has_reference=True)

    assert prompt.splitlines()[0] == ("업로드된 제품 사진의 피사체와 구도를 보존하면서 광고 이미지로 연출한다.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_prompts.py -q`
Expected: FAIL with `TypeError: build_image_prompt() got an unexpected keyword argument 'has_reference'`

- [ ] **Step 3: Implement the flag**

In `src/dessert_ad_studio/prompts.py`, replace `build_image_prompt` with:

```python
def build_image_prompt(
    request: GenerationRequest,
    ranked_template: str,
    has_reference: bool = False,
) -> str:
    lines: list[str] = []
    if has_reference:
        lines.append("업로드된 제품 사진의 피사체와 구도를 보존하면서 광고 이미지로 연출한다.")
    lines.extend(
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
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_prompts.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/dessert_ad_studio/prompts.py tests/test_prompts.py
git commit -m "Tell the image model to preserve uploaded product photos

Constraint: edit mode must keep the product subject while restyling the ad
Confidence: high
Scope-risk: narrow
Tested: pytest tests/test_prompts.py -q"
```

### Task 4: Align mock and FLUX.2 backends with the image protocol

**Files:**
- Modify: `src/dessert_ad_studio/backends/mock.py:37-57`
- Modify: `src/dessert_ad_studio/backends/flux2.py:38`
- Modify: `src/dessert_ad_studio/backends/__init__.py`
- Test: `tests/test_mock_backend.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_mock_backend.py`:

```python
REF_BADGE_COLOR = (40, 160, 90)


def test_mock_image_marks_reference_usage_with_badge(tmp_path: Path) -> None:
    request = GenerationRequest(
        campaign_purpose="new_menu",
        product_name="레몬 타르트",
        tone="clean",
        template_hint="minimal_premium",
    )
    backend = MockAdBackend(output_dir=tmp_path)
    prompt = build_image_prompt(request, ranked_template="minimal_premium")

    plain_path = backend.generate_image(request=request, image_prompt=prompt)
    badge_path = backend.generate_image(
        request=request, image_prompt=prompt, reference_image=b"fake-reference-bytes"
    )

    from PIL import Image

    with Image.open(plain_path) as plain:
        assert plain.getpixel((60, 60)) != REF_BADGE_COLOR
    with Image.open(badge_path) as badged:
        assert badged.getpixel((60, 60)) == REF_BADGE_COLOR
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mock_backend.py -q`
Expected: FAIL with `TypeError: MockAdBackend.generate_image() got an unexpected keyword argument 'reference_image'`

- [ ] **Step 3: Extend the mock backend**

In `src/dessert_ad_studio/backends/mock.py`, replace `generate_image` with:

```python
    def generate_image(
        self,
        request: GenerationRequest,
        image_prompt: str,
        reference_image: bytes | None = None,
    ) -> str:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{request.product_name.replace(' ', '_')}_mock_ad.png"
        path = self.output_dir / filename

        image = Image.new("RGB", (1024, 1024), color=(250, 238, 224))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        draw.rounded_rectangle(
            (90, 120, 934, 780),
            radius=48,
            fill=(255, 250, 244),
            outline=(120, 80, 60),
            width=4,
        )
        draw.ellipse((332, 230, 692, 590), fill=(230, 120, 140), outline=(90, 60, 50), width=4)
        if reference_image is not None:
            draw.rectangle((40, 40, 200, 120), fill=(40, 160, 90))
            draw.text((70, 70), "REF", fill=(255, 255, 255), font=font)
        draw.text((140, 830), request.product_name, fill=(80, 45, 35), font=font)
        prompt_line = textwrap.shorten(image_prompt.replace("\n", " "), width=90)
        draw.text((140, 870), prompt_line, fill=(110, 80, 70), font=font)
        image.save(path)
        return str(path)
```

In `src/dessert_ad_studio/backends/flux2.py`, replace the `generate_image` signature line (line 38) with:

```python
    def generate_image(
        self,
        request: GenerationRequest,
        image_prompt: str,
        reference_image: bytes | None = None,
    ) -> str:
```

(The body is unchanged; FLUX.2 ignores `reference_image` this round.)

Replace `src/dessert_ad_studio/backends/__init__.py` with:

```python
from dessert_ad_studio.backends.base import AdBackendError, CopyBackend, ImageBackend
from dessert_ad_studio.backends.flux2 import Flux2Backend
from dessert_ad_studio.backends.mock import MockAdBackend

__all__ = ["AdBackendError", "CopyBackend", "ImageBackend", "Flux2Backend", "MockAdBackend"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_mock_backend.py tests/test_backend_base.py -q && python -m py_compile src/dessert_ad_studio/backends/flux2.py`
Expected: PASS (4 passed), py_compile exits 0

- [ ] **Step 5: Commit**

```bash
git add src/dessert_ad_studio/backends/mock.py src/dessert_ad_studio/backends/flux2.py src/dessert_ad_studio/backends/__init__.py tests/test_mock_backend.py
git commit -m "Prove reference plumbing without any API call

Constraint: the REF badge makes reference delivery assertable in hermetic tests
Confidence: high
Scope-risk: narrow
Tested: pytest tests/test_mock_backend.py tests/test_backend_base.py -q"
```

### Task 5: OpenAI copy backend with Structured Outputs

**Files:**
- Modify: `pyproject.toml:10-21`
- Create: `src/dessert_ad_studio/backends/openai_copy.py`
- Modify: `src/dessert_ad_studio/backends/__init__.py`
- Test: `tests/test_openai_copy_backend.py`

- [ ] **Step 1: Add dependencies**

In `pyproject.toml`, extend `[project] dependencies` (after the `"tritonclient[http]>=2.45",` line) with:

```toml
  "openai>=2.8",
  "python-dotenv>=1.0",
```

Run: `pip install -e ".[dev]"`
Expected: exits 0 and installs `openai` and `python-dotenv`.

- [ ] **Step 2: Write the failing test**

Create `tests/test_openai_copy_backend.py`:

```python
from types import SimpleNamespace

import pytest

from dessert_ad_studio.backends.base import AdBackendError
from dessert_ad_studio.backends.openai_copy import CopyOptionsPayload, OpenAICopyBackend
from dessert_ad_studio.schemas import CopyOption, GenerationRequest


def sample_request() -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="discount",
        product_name="초코 마들렌",
        tone="playful",
        template_hint="cute_dessert",
        price_text="2개 구매 시 10% 할인",
    )


def make_payload(count: int = 3) -> CopyOptionsPayload:
    return CopyOptionsPayload(
        options=[
            CopyOption(
                headline=f"헤드라인 {index}",
                body=f"본문 {index}",
                call_to_action=f"행동 유도 {index}",
            )
            for index in range(count)
        ]
    )


class FakeCompletions:
    def __init__(self, payload: CopyOptionsPayload | None) -> None:
        self._payload = payload
        self.last_kwargs: dict | None = None

    def parse(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=self._payload))],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=88, total_tokens=208),
        )


def make_fake_client(payload: CopyOptionsPayload | None) -> SimpleNamespace:
    completions = FakeCompletions(payload)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def test_generate_copy_returns_three_options_and_records_usage() -> None:
    client = make_fake_client(make_payload())
    backend = OpenAICopyBackend(model_id="gpt-test-mini", client=client)

    options = backend.generate_copy(sample_request())

    assert [option.headline for option in options] == ["헤드라인 0", "헤드라인 1", "헤드라인 2"]
    assert backend.last_usage == {
        "prompt_tokens": 120,
        "completion_tokens": 88,
        "total_tokens": 208,
    }
    kwargs = client.chat.completions.last_kwargs
    assert kwargs["model"] == "gpt-test-mini"
    assert kwargs["response_format"] is CopyOptionsPayload
    assert kwargs["messages"][0]["role"] == "system"
    assert "초코 마들렌" in kwargs["messages"][1]["content"]


def test_generate_copy_rejects_wrong_option_count() -> None:
    backend = OpenAICopyBackend(client=make_fake_client(make_payload(count=2)))

    with pytest.raises(AdBackendError, match="3개"):
        backend.generate_copy(sample_request())


def test_missing_api_key_maps_to_backend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    backend = OpenAICopyBackend()

    with pytest.raises(AdBackendError, match="OPENAI_API_KEY"):
        backend.generate_copy(sample_request())
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_openai_copy_backend.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'dessert_ad_studio.backends.openai_copy'`

- [ ] **Step 4: Implement the copy backend**

Create `src/dessert_ad_studio/backends/openai_copy.py`:

```python
from __future__ import annotations

import os
from typing import Any

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
from dessert_ad_studio.prompts import build_copy_prompt
from dessert_ad_studio.schemas import CopyOption, GenerationRequest

COPY_SYSTEM_PROMPT = (
    "너는 카페/디저트 소상공인을 돕는 한국어 광고 카피라이터다. "
    "과장 광고, 허위 수상 문구, 근거 없는 효능 주장은 금지한다. "
    "각 후보는 헤드라인, 본문 한두 문장, 행동 유도 문구로 구성하며 정확히 3개를 만든다."
)


class CopyOptionsPayload(BaseModel):
    options: list[CopyOption]


class OpenAICopyBackend:
    name = "openai"

    def __init__(self, model_id: str | None = None, client: Any | None = None) -> None:
        self.model_id = model_id or os.getenv("COPY_MODEL_ID", "gpt-5.4-mini")
        self.last_usage: dict[str, int] | None = None
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                self._client = OpenAI(timeout=120.0)
            except OpenAIError as exc:
                raise AdBackendError(
                    "OpenAI API 키가 설정되지 않았습니다. .env의 OPENAI_API_KEY를 확인해주세요."
                ) from exc
        return self._client

    def generate_copy(self, request: GenerationRequest) -> list[CopyOption]:
        client = self._get_client()
        try:
            completion = client.chat.completions.parse(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": COPY_SYSTEM_PROMPT},
                    {"role": "user", "content": build_copy_prompt(request)},
                ],
                response_format=CopyOptionsPayload,
            )
        except AuthenticationError as exc:
            raise AdBackendError("OpenAI API 키가 유효하지 않습니다. 키 값을 확인해주세요.") from exc
        except RateLimitError as exc:
            raise AdBackendError(
                "OpenAI API 호출 한도를 초과했습니다. 잠시 후 다시 시도하거나 팀 사용량을 확인해주세요."
            ) from exc
        except BadRequestError as exc:
            raise AdBackendError(f"문구 생성 요청이 거부되었습니다: {exc}", status_code=422) from exc
        except APIError as exc:
            raise AdBackendError(f"문구 생성 API 호출에 실패했습니다: {exc}") from exc

        parsed = completion.choices[0].message.parsed
        if parsed is None or len(parsed.options) != 3:
            raise AdBackendError("광고 문구 3개 생성에 실패했습니다. 다시 시도해주세요.")
        usage = getattr(completion, "usage", None)
        if usage is not None:
            self.last_usage = {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            }
        return list(parsed.options)
```

Replace `src/dessert_ad_studio/backends/__init__.py` with:

```python
from dessert_ad_studio.backends.base import AdBackendError, CopyBackend, ImageBackend
from dessert_ad_studio.backends.flux2 import Flux2Backend
from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.backends.openai_copy import OpenAICopyBackend

__all__ = [
    "AdBackendError",
    "CopyBackend",
    "ImageBackend",
    "Flux2Backend",
    "MockAdBackend",
    "OpenAICopyBackend",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_openai_copy_backend.py -q`
Expected: PASS (3 passed). The missing-key test passes because `OpenAI()` raises `OpenAIError` when no key is available, which maps to `AdBackendError`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/dessert_ad_studio/backends/openai_copy.py src/dessert_ad_studio/backends/__init__.py tests/test_openai_copy_backend.py
git commit -m "Generate real Korean ad copy through Structured Outputs

Constraint: copy parsing must never fail on free-form LLM text during a demo
Rejected: prompt-only JSON formatting | brittle parsing under tone variations
Confidence: high
Scope-risk: moderate
Tested: pytest tests/test_openai_copy_backend.py -q
Not-tested: live OpenAI call, deferred to scripts/openai_smoke.py"
```

### Task 6: OpenAI image backend with generate/edit branch

**Files:**
- Create: `src/dessert_ad_studio/backends/openai_image.py`
- Modify: `src/dessert_ad_studio/backends/__init__.py`
- Test: `tests/test_openai_image_backend.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_openai_image_backend.py`:

```python
import base64
import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from dessert_ad_studio.backends.base import AdBackendError
from dessert_ad_studio.backends.openai_image import OpenAIImageBackend
from dessert_ad_studio.schemas import GenerationRequest


def sample_request() -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="seasonal_event",
        product_name="벚꽃 딸기 케이크",
        tone="warm",
        template_hint="seasonal_event",
    )


def tiny_png_b64() -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color=(200, 80, 120)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class FakeImages:
    def __init__(self, b64: str) -> None:
        self._b64 = b64
        self.generate_kwargs: dict | None = None
        self.edit_kwargs: dict | None = None

    def generate(self, **kwargs):
        self.generate_kwargs = kwargs
        return SimpleNamespace(
            data=[SimpleNamespace(b64_json=self._b64)],
            usage=SimpleNamespace(total_tokens=4160),
        )

    def edit(self, **kwargs):
        self.edit_kwargs = kwargs
        return SimpleNamespace(data=[SimpleNamespace(b64_json=self._b64)], usage=None)


def make_fake_client(b64: str) -> SimpleNamespace:
    return SimpleNamespace(images=FakeImages(b64))


def test_generate_without_reference_calls_generate(tmp_path: Path) -> None:
    client = make_fake_client(tiny_png_b64())
    backend = OpenAIImageBackend(
        output_dir=tmp_path, model_id="gpt-image-test", quality="low", client=client
    )

    image_path = backend.generate_image(sample_request(), image_prompt="광고 이미지 지시문")

    assert Path(image_path).exists()
    assert Path(image_path).suffix == ".png"
    assert client.images.edit_kwargs is None
    kwargs = client.images.generate_kwargs
    assert kwargs["model"] == "gpt-image-test"
    assert kwargs["quality"] == "low"
    assert kwargs["size"] == "1024x1024"
    assert backend.last_usage == {"total_tokens": 4160}


def test_generate_with_reference_calls_edit(tmp_path: Path) -> None:
    client = make_fake_client(tiny_png_b64())
    backend = OpenAIImageBackend(output_dir=tmp_path, client=client)
    reference = b"normalized-png-bytes"

    backend.generate_image(
        sample_request(), image_prompt="광고 이미지 지시문", reference_image=reference
    )

    assert client.images.generate_kwargs is None
    kwargs = client.images.edit_kwargs
    assert kwargs["image"] == ("reference.png", reference, "image/png")
    assert kwargs["prompt"] == "광고 이미지 지시문"


def test_empty_response_payload_maps_to_backend_error(tmp_path: Path) -> None:
    client = make_fake_client("")
    backend = OpenAIImageBackend(output_dir=tmp_path, client=client)

    with pytest.raises(AdBackendError, match="비어"):
        backend.generate_image(sample_request(), image_prompt="지시문")


def test_missing_api_key_maps_to_backend_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    backend = OpenAIImageBackend(output_dir=tmp_path)

    with pytest.raises(AdBackendError, match="OPENAI_API_KEY"):
        backend.generate_image(sample_request(), image_prompt="지시문")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_openai_image_backend.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'dessert_ad_studio.backends.openai_image'`

- [ ] **Step 3: Implement the image backend**

Create `src/dessert_ad_studio/backends/openai_image.py`:

```python
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from openai import (
    APIError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)

from dessert_ad_studio.backends.base import AdBackendError
from dessert_ad_studio.schemas import GenerationRequest


class OpenAIImageBackend:
    name = "openai"

    def __init__(
        self,
        output_dir: str | Path = "outputs",
        model_id: str | None = None,
        quality: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.model_id = model_id or os.getenv("IMAGE_MODEL_ID", "gpt-image-1-mini")
        self.quality = quality or os.getenv("IMAGE_QUALITY", "low")
        self.last_usage: dict[str, int | None] | None = None
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                self._client = OpenAI(timeout=120.0)
            except OpenAIError as exc:
                raise AdBackendError(
                    "OpenAI API 키가 설정되지 않았습니다. .env의 OPENAI_API_KEY를 확인해주세요."
                ) from exc
        return self._client

    def generate_image(
        self,
        request: GenerationRequest,
        image_prompt: str,
        reference_image: bytes | None = None,
    ) -> str:
        client = self._get_client()
        try:
            if reference_image is not None:
                result = client.images.edit(
                    model=self.model_id,
                    image=("reference.png", reference_image, "image/png"),
                    prompt=image_prompt,
                    size="1024x1024",
                    quality=self.quality,
                )
            else:
                result = client.images.generate(
                    model=self.model_id,
                    prompt=image_prompt,
                    size="1024x1024",
                    quality=self.quality,
                )
        except AuthenticationError as exc:
            raise AdBackendError("OpenAI API 키가 유효하지 않습니다. 키 값을 확인해주세요.") from exc
        except RateLimitError as exc:
            raise AdBackendError(
                "OpenAI API 호출 한도를 초과했습니다. 잠시 후 다시 시도하거나 팀 사용량을 확인해주세요."
            ) from exc
        except BadRequestError as exc:
            raise AdBackendError(
                f"이미지 생성 요청이 거부되었습니다(콘텐츠 정책 등): {exc}", status_code=422
            ) from exc
        except APIError as exc:
            raise AdBackendError(f"이미지 생성 API 호출에 실패했습니다: {exc}") from exc

        image_b64 = result.data[0].b64_json
        if not image_b64:
            raise AdBackendError("이미지 생성 응답이 비어 있습니다. 다시 시도해주세요.")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{request.product_name.replace(' ', '_')}_openai_ad.png"
        path.write_bytes(base64.b64decode(image_b64))
        usage = getattr(result, "usage", None)
        if usage is not None:
            self.last_usage = {"total_tokens": getattr(usage, "total_tokens", None)}
        return str(path)
```

Replace `src/dessert_ad_studio/backends/__init__.py` with:

```python
from dessert_ad_studio.backends.base import AdBackendError, CopyBackend, ImageBackend
from dessert_ad_studio.backends.flux2 import Flux2Backend
from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.backends.openai_copy import OpenAICopyBackend
from dessert_ad_studio.backends.openai_image import OpenAIImageBackend

__all__ = [
    "AdBackendError",
    "CopyBackend",
    "ImageBackend",
    "Flux2Backend",
    "MockAdBackend",
    "OpenAICopyBackend",
    "OpenAIImageBackend",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_openai_image_backend.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/dessert_ad_studio/backends/openai_image.py src/dessert_ad_studio/backends/__init__.py tests/test_openai_image_backend.py
git commit -m "Turn reference uploads into real ad images via edit mode

Constraint: same output contract as mock so the API layer stays backend-agnostic
Rejected: separate edit-only backend class | doubles configuration without benefit
Confidence: high
Scope-risk: moderate
Tested: pytest tests/test_openai_image_backend.py -q
Not-tested: live image API call, deferred to scripts/openai_smoke.py"
```

### Task 7: Schemas, API wiring, error mapping, and logging

**Files:**
- Modify: `src/dessert_ad_studio/schemas.py:12-41`
- Modify: `api/main.py` (full rewrite below)
- Modify: `tests/conftest.py`
- Test: `tests/test_api.py` (full rewrite below)

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_api.py` with:

```python
import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from api.main import app

client = TestClient(app)


def base_payload() -> dict:
    return {
        "campaign_purpose": "new_menu",
        "product_name": "말차 푸딩",
        "tone": "clean",
        "template_hint": "minimal_premium",
        "price_text": "5,500원",
        "user_constraints": "깔끔한 프리미엄 느낌",
    }


def tiny_png_b64() -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color=(120, 200, 160)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_generate_uses_template_ranking_and_returns_copy() -> None:
    response = client.post("/generate", json=base_payload())

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["copy_options"]) == 3
    assert payload["selected_template"]["scorer"] in {
        "local-template-scorer",
        "triton-template-scorer",
    }
    assert payload["copy_backend"] == "mock"
    assert payload["image_backend"] == "mock"
    assert payload["used_reference"] is False
    assert payload["image_path"].endswith(".png")


def test_generate_with_reference_image_flags_usage() -> None:
    payload = {
        **base_payload(),
        "reference_image_b64": tiny_png_b64(),
        "reference_image_name": "store_photo.png",
    }

    response = client.post("/generate", json=payload)

    assert response.status_code == 200
    assert response.json()["used_reference"] is True


def test_generate_rejects_invalid_reference_encoding() -> None:
    payload = {**base_payload(), "reference_image_b64": "not-base64!!!"}

    response = client.post("/generate", json=payload)

    assert response.status_code == 400
    assert "base64" in response.json()["detail"]


def test_generate_maps_missing_openai_key_to_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPY_BACKEND", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_generate_rejects_unknown_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_BACKEND", "unknown-backend")

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 501
```

Replace `tests/conftest.py` with (imports must stay at the top of the file or
`ruff check .` fails with E402):

```python
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def hermetic_backend_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPY_BACKEND", "mock")
    monkeypatch.setenv("IMAGE_BACKEND", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
```

(The fixture keeps a developer's local `.env` — loaded by `api/main.py` below — from leaking real backends or keys into the test suite. Tests that need other values call `monkeypatch.setenv` again inside the test, which wins because it runs after the autouse fixture.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py -q`
Expected: FAIL — `GenerationRequest` has no `reference_image_b64` field yet and responses lack `copy_backend`/`used_reference`.

- [ ] **Step 3: Update schemas**

In `src/dessert_ad_studio/schemas.py`, replace `GenerationRequest` and `GenerationResponse` with:

```python
class GenerationRequest(BaseModel):
    campaign_purpose: CampaignPurpose
    product_name: str = Field(min_length=1, max_length=80)
    tone: Tone
    template_hint: TemplateHint
    price_text: str = Field(default="", max_length=40)
    user_constraints: str = Field(default="", max_length=300)
    reference_image_b64: str | None = None
    reference_image_name: str | None = None
```

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
```

(`CopyOption` and `TemplateRanking` stay unchanged. `reference_image_path` is gone; old clients that still send it are unaffected because pydantic ignores unknown fields by default.)

- [ ] **Step 4: Rewrite the API service**

Replace `api/main.py` with:

```python
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from dessert_ad_studio.backends.base import AdBackendError, CopyBackend, ImageBackend
from dessert_ad_studio.backends.flux2 import Flux2Backend
from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.backends.openai_copy import OpenAICopyBackend
from dessert_ad_studio.backends.openai_image import OpenAIImageBackend
from dessert_ad_studio.generation_logger import GenerationLogger
from dessert_ad_studio.prompts import build_image_prompt
from dessert_ad_studio.reference_image import ReferenceImageError, decode_reference_image
from dessert_ad_studio.schemas import GenerationRequest, GenerationResponse
from dessert_ad_studio.triton import LocalTemplateScorer, TritonTemplateScorer

load_dotenv()

app = FastAPI(title="Dessert Ad Studio API")


def get_template_scorer():
    require_triton = os.getenv("REQUIRE_TRITON", "0") == "1"
    triton_url = os.getenv("TRITON_URL", "localhost:8001")
    if require_triton:
        return TritonTemplateScorer(url=triton_url)
    return TritonTemplateScorer(url=triton_url)


@lru_cache(maxsize=None)
def _copy_backend_for(name: str, output_dir: str) -> CopyBackend | None:
    if name == "mock":
        return MockAdBackend(output_dir=output_dir)
    if name == "openai":
        return OpenAICopyBackend()
    return None


@lru_cache(maxsize=None)
def _image_backend_for(name: str, output_dir: str) -> ImageBackend | None:
    if name == "mock":
        return MockAdBackend(output_dir=output_dir)
    if name == "openai":
        return OpenAIImageBackend(output_dir=output_dir)
    if name == "flux2":
        return Flux2Backend(output_dir=output_dir)
    return None


def get_copy_backend() -> CopyBackend:
    name = os.getenv("COPY_BACKEND", "mock")
    backend = _copy_backend_for(name, os.getenv("OUTPUT_DIR", "outputs"))
    if backend is None:
        raise HTTPException(status_code=501, detail=f"unknown copy backend: {name}")
    return backend


def get_image_backend() -> ImageBackend:
    name = os.getenv("IMAGE_BACKEND", "mock")
    backend = _image_backend_for(name, os.getenv("OUTPUT_DIR", "outputs"))
    if backend is None:
        raise HTTPException(status_code=501, detail=f"unknown image backend: {name}")
    return backend


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
            raise HTTPException(
                status_code=503,
                detail=f"Triton template scoring failed: {exc}",
            ) from exc
        return LocalTemplateScorer().rank(request)


@app.post("/generate", response_model=GenerationResponse)
def generate(request: GenerationRequest) -> GenerationResponse:
    started = perf_counter()
    ranking = rank_templates(request)
    copy_backend = get_copy_backend()
    image_backend = get_image_backend()

    try:
        reference_image = decode_reference_image(request.reference_image_b64)
    except ReferenceImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    image_prompt = build_image_prompt(
        request,
        ranked_template=ranking.template_name,
        has_reference=reference_image is not None,
    )

    try:
        copy_options = copy_backend.generate_copy(request)
        image_path = image_backend.generate_image(
            request,
            image_prompt=image_prompt,
            reference_image=reference_image,
        )
    except AdBackendError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    elapsed_ms = (perf_counter() - started) * 1000

    logger = GenerationLogger(Path(os.getenv("GENERATION_LOG_PATH", "logs/generations.jsonl")))
    logger.write(
        {
            "campaign_purpose": request.campaign_purpose,
            "template": ranking.template_name,
            "template_scorer": ranking.scorer,
            "triton_latency_ms": ranking.latency_ms,
            "copy_backend": copy_backend.name,
            "copy_model_id": getattr(copy_backend, "model_id", None),
            "copy_usage": getattr(copy_backend, "last_usage", None),
            "image_backend": image_backend.name,
            "image_model_id": getattr(image_backend, "model_id", None),
            "used_reference": reference_image is not None,
            "reference_image_name": request.reference_image_name,
            "elapsed_ms": elapsed_ms,
            "image_path": image_path,
        }
    )

    return GenerationResponse(
        copy_options=copy_options,
        selected_template=ranking,
        image_path=image_path,
        image_backend=image_backend.name,
        copy_backend=copy_backend.name,
        used_reference=reference_image is not None,
        prompt_summary=image_prompt,
        elapsed_ms=elapsed_ms,
    )
```

Notes for the implementer:

- `load_dotenv()` fills missing env vars from `.env` for local runs; it never overrides already-set variables, and the autouse conftest fixture pins backends to `mock` during tests.
- The `lru_cache` factories satisfy the spec's one-instance-per-process requirement; the cache key includes the backend name and output dir, so monkeypatched test env changes resolve to the right instance.
- The missing-key 503 path works without injection: `OpenAICopyBackend._get_client()` raises `AdBackendError` when `OpenAI()` cannot find a key, and `/generate` maps it via `exc.status_code`.

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS (all tests, including the updated API tests).

- [ ] **Step 6: Commit**

```bash
git add src/dessert_ad_studio/schemas.py api/main.py tests/test_api.py tests/conftest.py
git commit -m "Route generation through switchable copy and image backends

Constraint: spec requires independent COPY_BACKEND/IMAGE_BACKEND with mock defaults for hermetic tests
Rejected: silent mock fallback on API failure | fake results must never look real in a demo
Confidence: high
Scope-risk: moderate
Tested: pytest -q"
```

### Task 8: Streamlit upload encoding and result display

**Files:**
- Modify: `app/streamlit_app.py`

- [ ] **Step 1: Rewrite the Streamlit app**

Replace `app/streamlit_app.py` with:

```python
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
```

- [ ] **Step 2: Run static check**

Run: `python -m py_compile app/streamlit_app.py`
Expected: exits 0

- [ ] **Step 3: Commit**

```bash
git add app/streamlit_app.py
git commit -m "Send uploads to the API and surface backend errors in Korean

Constraint: reference images must reach the backend as base64 JSON per the spec transport decision
Confidence: high
Scope-risk: narrow
Tested: python -m py_compile app/streamlit_app.py
Not-tested: manual Streamlit flow, covered in final verification"
```

### Task 9: Real-API smoke script

**Files:**
- Create: `scripts/openai_smoke.py`

- [ ] **Step 1: Create the smoke script**

Create `scripts/openai_smoke.py`:

```python
"""Manual OpenAI smoke check. Costs real money — run on purpose, not in CI.

Usage:
    python scripts/openai_smoke.py [path/to/reference.jpg]

Verifies the configured COPY_MODEL_ID and IMAGE_MODEL_ID work with the current
OPENAI_API_KEY, prints token usage and latency, and saves one image under outputs/.
Passing a reference image path exercises the edit branch instead of text-to-image.
"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv

from dessert_ad_studio.backends.openai_copy import OpenAICopyBackend
from dessert_ad_studio.backends.openai_image import OpenAIImageBackend
from dessert_ad_studio.prompts import build_image_prompt
from dessert_ad_studio.reference_image import decode_reference_image
from dessert_ad_studio.schemas import GenerationRequest


def main() -> None:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY가 없습니다. .env 또는 환경변수를 확인하세요.")

    request = GenerationRequest(
        campaign_purpose="new_menu",
        product_name="딸기 크림 크루아상",
        tone="warm",
        template_hint="cozy_cafe",
        price_text="6,800원",
        user_constraints="봄 시즌 한정 느낌",
    )

    copy_backend = OpenAICopyBackend()
    started = perf_counter()
    options = copy_backend.generate_copy(request)
    copy_ms = (perf_counter() - started) * 1000
    for index, option in enumerate(options, start=1):
        print(f"[copy {index}] {option.headline}")
    print(
        {
            "copy_model": copy_backend.model_id,
            "copy_ms": round(copy_ms),
            "copy_usage": copy_backend.last_usage,
        }
    )

    reference_image = None
    if len(sys.argv) > 1:
        raw = Path(sys.argv[1]).read_bytes()
        encoded = base64.b64encode(raw).decode("ascii")
        reference_image = decode_reference_image(encoded)

    image_backend = OpenAIImageBackend(output_dir="outputs")
    prompt = build_image_prompt(
        request,
        ranked_template="cozy_cafe",
        has_reference=reference_image is not None,
    )
    started = perf_counter()
    image_path = image_backend.generate_image(
        request,
        image_prompt=prompt,
        reference_image=reference_image,
    )
    image_ms = (perf_counter() - started) * 1000
    print(
        {
            "image_model": image_backend.model_id,
            "image_quality": image_backend.quality,
            "image_ms": round(image_ms),
            "image_path": image_path,
            "image_usage": image_backend.last_usage,
            "used_reference": reference_image is not None,
        }
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run static check (no API call)**

Run: `python -m py_compile scripts/openai_smoke.py`
Expected: exits 0. Do NOT run the script itself in this task — it spends real quota. The user runs it manually during final verification.

- [ ] **Step 3: Commit**

```bash
git add scripts/openai_smoke.py
git commit -m "Verify live OpenAI models and cost outside the test suite

Constraint: model ids and edit support must be proven against the real API without burning quota in CI
Confidence: high
Scope-risk: narrow
Tested: python -m py_compile scripts/openai_smoke.py
Not-tested: live API call, reserved for manual verification"
```

### Task 10: Configuration, compose wiring, and README

**Files:**
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Modify: `README.md`

- [ ] **Step 1: Update `.env.example`**

Replace `.env.example` with:

```bash
API_BASE_URL=http://localhost:8000
TRITON_URL=localhost:8001
REQUIRE_TRITON=0
COPY_BACKEND=mock
COPY_MODEL_ID=gpt-5.4-mini
IMAGE_BACKEND=mock
IMAGE_MODEL_ID=gpt-image-1-mini
IMAGE_QUALITY=low
OPENAI_API_KEY=
FLUX2_MODEL_ID=black-forest-labs/FLUX.2-klein
OUTPUT_DIR=outputs
GENERATION_LOG_PATH=logs/generations.jsonl
```

- [ ] **Step 2: Pass backend settings through docker-compose**

In `docker-compose.yml`, replace the `api` service `environment` block with:

```yaml
    environment:
      TRITON_URL: triton:8001
      REQUIRE_TRITON: "1"
      COPY_BACKEND: ${COPY_BACKEND:-mock}
      COPY_MODEL_ID: ${COPY_MODEL_ID:-gpt-5.4-mini}
      IMAGE_BACKEND: ${IMAGE_BACKEND:-mock}
      IMAGE_MODEL_ID: ${IMAGE_MODEL_ID:-gpt-image-1-mini}
      IMAGE_QUALITY: ${IMAGE_QUALITY:-low}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      OUTPUT_DIR: /app/outputs
      GENERATION_LOG_PATH: /app/logs/generations.jsonl
```

(Compose reads `.env` in the project root for `${...}` interpolation, so the same file configures both local runs and the compose demo. The key never lands in the compose file itself.)

- [ ] **Step 3: Document backends in README**

In `README.md`, replace the `## Configuration` section with:

```markdown
## Configuration

Copy `.env.example` to `.env` and edit local values. Do not commit `.env`.

### Generation backends

Copy and image generation switch independently:

| Variable | Values | Default |
| --- | --- | --- |
| `COPY_BACKEND` | `mock`, `openai` | `mock` |
| `IMAGE_BACKEND` | `mock`, `openai`, `flux2` | `mock` |
| `COPY_MODEL_ID` | any chat model id | `gpt-5.4-mini` |
| `IMAGE_MODEL_ID` | any GPT image model id | `gpt-image-1-mini` |
| `IMAGE_QUALITY` | `low`, `medium`, `high` | `low` |

Real backends need `OPENAI_API_KEY` in `.env`. Uploading a reference image in
Streamlit switches the OpenAI image backend from text-to-image to edit mode.
Keep `IMAGE_QUALITY=low` while iterating; raise it only for final demo shots.

### OpenAI smoke check (manual, costs quota)

```bash
python scripts/openai_smoke.py                      # copy + text-to-image
python scripts/openai_smoke.py my_product_photo.jpg # copy + reference edit
```

Run it once after setting a key to confirm the configured model ids exist and
to record baseline latency/token usage. It is intentionally not part of pytest.
```

- [ ] **Step 4: Validate compose config**

Run: `docker compose config -q`
Expected: exits 0 (warning about unset `OPENAI_API_KEY` is acceptable when no `.env` exists).

If Docker is unavailable in the session, record that and rely on YAML review.

- [ ] **Step 5: Commit**

```bash
git add .env.example docker-compose.yml README.md
git commit -m "Wire backend selection through env, compose, and docs

Constraint: the same .env must drive local runs, compose demo, and the future team-key swap
Confidence: high
Scope-risk: narrow
Tested: docker compose config -q"
```

### Task 11: Final verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run the full automated gate**

Run:

```bash
pytest -q
ruff check .
python -m py_compile app/streamlit_app.py api/main.py scripts/openai_smoke.py \
  src/dessert_ad_studio/*.py src/dessert_ad_studio/backends/*.py
```

Expected: all tests pass, ruff reports no issues, py_compile exits 0.

- [ ] **Step 2: Manual acceptance with a real key (user-run)**

With `OPENAI_API_KEY`, `COPY_BACKEND=openai`, `IMAGE_BACKEND=openai` in `.env`:

```bash
python scripts/openai_smoke.py
uvicorn api.main:app --reload --port 8000   # terminal 1
streamlit run app/streamlit_app.py          # terminal 2
```

Acceptance per spec section 7:

1. Streamlit shows three LLM-generated Korean copy candidates.
2. Submitting without an upload produces a text-to-image ad PNG.
3. Submitting with an uploaded product photo produces an edit-mode ad that
   visibly uses the photo, and the result caption shows `참고 이미지 반영: 예`.
4. `logs/generations.jsonl` gains rows containing `copy_model_id`,
   `copy_usage`, `image_model_id`, and `used_reference`.

- [ ] **Step 3: Record results**

If any acceptance item fails, capture the exact error output and stop for review
instead of patching ad hoc — model-id or edit-parameter mismatches are expected
failure modes and the fix belongs in `.env` or a focused follow-up commit.

## Final acceptance checklist

- [ ] `pytest -q` passes with no network access.
- [ ] `ruff check .` passes.
- [ ] Mock remains the default backend pair; no test touches the OpenAI API.
- [ ] `COPY_BACKEND=openai` + `IMAGE_BACKEND=openai` serve real copy and images.
- [ ] Reference upload flips the OpenAI backend to edit mode and flags
      `used_reference` in response and log.
- [ ] API failures surface Korean actionable messages; no silent mock fallback.
- [ ] `scripts/openai_smoke.py` documents live model verification and cost evidence.
- [ ] README documents backend matrix, smoke procedure, and key handling.
