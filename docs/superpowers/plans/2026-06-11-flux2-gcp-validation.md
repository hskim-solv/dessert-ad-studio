# FLUX.2 GCP L4 검증 라운드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** flux2 이미지 백엔드를 계약 준수 상태로 교정한 뒤, GCP L4 GPU VM에서 Docker Compose GPU 오버레이로 `POST /generate`(image=flux2) 1회 검증을 완료하고 증빙·runbook·ADR을 남긴다.

**Architecture:** 코드 변경(에러 매핑, 모델 id/파라미터 교정, 텔레메트리)은 전부 로컬 TDD로 VM 과금 전에 끝낸다. GPU 실행은 기존 docker-compose.yml 위에 오버레이(docker-compose.gpu.yml)만 얹는 방식이라 로컬 CPU 데모 동작은 불변이다. VM 검증은 gcloud CLI 원격 자동화로 수행하고, 모든 실패 경로에서 즉시 VM을 정지한다.

**Tech Stack:** Python 3.11, FastAPI, diffusers(Flux2KleinPipeline)/torch, Docker Compose + NVIDIA Container Toolkit, GCP Compute Engine(g2-standard-4, L4).

**Spec:** `docs/superpowers/specs/2026-06-11-flux2-gcp-validation-design.md` (사용자 승인됨)

**사전 조건:**
- 브랜치: `feature/flux2-gcp-validation` (spec 커밋 927d3bf 포함). 모든 커밋은 이 브랜치에 쌓는다.
- 로컬 venv: `.venv` (torch/diffusers 미설치 — 테스트는 전부 mock 기반이라 불필요).
- 테스트 실행 명령: `.venv/bin/pytest` (프로젝트 루트에서).
- GCP: times21c@gmail.com 유료 계정, GPU 쿼터 미확인(Task 11에서 확인).

**비용 가드(전 구간 공통):** Task 12에서 VM이 생성되는 순간부터 시간당 ~$0.85가 과금된다. Task 12 이후 어떤 단계든 30분 이상 막히면 일단 `gcloud compute instances stop flux2-l4 --zone=<zone>`으로 정지하고 원인을 로컬에서 분석한다. 세션이 어떤 이유로든 끝날 때는 반드시 Task 15의 정지 확인 명령을 실행한다.

---

## Part A — 로컬 코드 변경 (VM 과금 전 완료)

### Task 1: flux2 에러 매핑 3종 (AdBackendError)

현재 `flux2.py`는 의존성 미설치 시 `RuntimeError`를 던지고, 모델 로드/추론 실패는 원시 예외가 그대로 누출된다. 백엔드 계약(사용자 노출 실패는 한국어 detail의 `AdBackendError`)에 맞게 3개 경로를 모두 매핑한다.

**Files:**
- Create: `tests/test_flux2_backend.py`
- Modify: `src/dessert_ad_studio/backends/flux2.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_flux2_backend.py`를 새로 만든다:

```python
"""Flux2Backend 단위 테스트 — torch/diffusers 설치 없이 mock으로 검증한다."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from dessert_ad_studio.backends.base import AdBackendError, ImageResult
from dessert_ad_studio.backends.flux2 import Flux2Backend
from dessert_ad_studio.schemas import GenerationRequest


def sample_request(product_name: str = "딸기 타르트") -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="new_menu",
        product_name=product_name,
        tone="warm",
        template_hint="cozy_cafe",
    )


def fake_image_pipeline(captured: dict | None = None):
    """generate_image가 호출할 파이프라인 흉내 — 8x8 PNG 한 장을 돌려준다."""

    def pipeline(**kwargs):
        if captured is not None:
            captured.update(kwargs)
        return SimpleNamespace(images=[Image.new("RGB", (8, 8), "pink")])

    return pipeline


def test_missing_image_extras_maps_to_korean_backend_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[image] extras 미설치(ImportError) → 한국어 AdBackendError 503"""
    monkeypatch.setitem(sys.modules, "torch", None)
    monkeypatch.setitem(sys.modules, "diffusers", None)
    backend = Flux2Backend(output_dir=tmp_path)

    with pytest.raises(AdBackendError) as exc_info:
        backend.generate_image(sample_request(), image_prompt="지시문")

    assert "의존성" in exc_info.value.detail
    assert "[image]" in exc_info.value.detail
    assert exc_info.value.status_code == 503


def test_pipeline_load_failure_maps_to_backend_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """from_pretrained 예외(모델 없음/다운로드 실패) → AdBackendError 503"""

    def raising_from_pretrained(model_id, torch_dtype):
        raise OSError("repo not found")

    fake_torch = SimpleNamespace(
        bfloat16="bf16",
        float32="fp32",
        cuda=SimpleNamespace(is_available=lambda: False),
    )
    fake_diffusers = SimpleNamespace(
        DiffusionPipeline=SimpleNamespace(from_pretrained=raising_from_pretrained)
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "diffusers", fake_diffusers)
    backend = Flux2Backend(output_dir=tmp_path)

    with pytest.raises(AdBackendError) as exc_info:
        backend.generate_image(sample_request(), image_prompt="지시문")

    assert "모델 로드" in exc_info.value.detail
    assert exc_info.value.status_code == 503


def test_inference_failure_maps_to_backend_error(tmp_path: Path) -> None:
    """파이프라인 호출 예외(OOM 등) → AdBackendError 503"""

    def raising_pipeline(**kwargs):
        raise RuntimeError("CUDA out of memory")

    backend = Flux2Backend(output_dir=tmp_path)
    backend._pipeline = raising_pipeline

    with pytest.raises(AdBackendError) as exc_info:
        backend.generate_image(sample_request(), image_prompt="지시문")

    assert "이미지 생성" in exc_info.value.detail
    assert exc_info.value.status_code == 503
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `.venv/bin/pytest tests/test_flux2_backend.py -v`
Expected: 3건 모두 FAIL — 첫 번째는 `RuntimeError`(AdBackendError 아님), 두 번째는 `OSError` 누출, 세 번째는 `RuntimeError` 누출.

- [ ] **Step 3: 최소 구현**

`src/dessert_ad_studio/backends/flux2.py`의 `_load_pipeline`과 `generate_image`를 수정한다. import 블록에 `AdBackendError`를 추가하고 세 경로를 감싼다:

```python
from __future__ import annotations

import os
from pathlib import Path

from dessert_ad_studio.backends.base import AdBackendError, ImageResult
from dessert_ad_studio.backends.naming import safe_filename_stem
from dessert_ad_studio.schemas import GenerationRequest


class Flux2Backend:
    name = "flux2"
    # Text-to-image only until the next round wires an i2i pipeline.
    supports_reference_image = False

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
            raise AdBackendError(
                "FLUX.2 백엔드 의존성이 설치되지 않았습니다. pip install -e '.[image]'로 설치해주세요."
            ) from exc

        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        try:
            pipeline = DiffusionPipeline.from_pretrained(self.model_id, torch_dtype=dtype)
            if torch.cuda.is_available():
                pipeline = pipeline.to("cuda")
            else:
                pipeline.enable_model_cpu_offload()
        except Exception as exc:
            raise AdBackendError(f"FLUX.2 모델 로드에 실패했습니다: {exc}") from exc
        self._pipeline = pipeline
        return pipeline

    def generate_image(
        self,
        request: GenerationRequest,
        image_prompt: str,
        reference_image: bytes | None = None,
    ) -> ImageResult:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        pipeline = self._load_pipeline()
        try:
            result = pipeline(
                prompt=image_prompt,
                width=1024,
                height=1024,
                num_inference_steps=28,
                guidance_scale=3.5,
            )
        except Exception as exc:
            raise AdBackendError(f"FLUX.2 이미지 생성에 실패했습니다: {exc}") from exc
        image = result.images[0]
        path = self.output_dir / f"{safe_filename_stem(request.product_name)}_flux2_ad.png"
        image.save(path)
        return ImageResult(path=str(path))
```

(모델 id와 28 steps/3.5 guidance는 Task 2에서 고친다 — 이 태스크는 에러 매핑만.)

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/pytest tests/test_flux2_backend.py -v`
Expected: 3 passed

- [ ] **Step 5: 기존 회귀 확인 후 커밋**

Run: `.venv/bin/pytest -q`
Expected: 69 passed (기존 66 + 신규 3), 0 failed

```bash
git add tests/test_flux2_backend.py src/dessert_ad_studio/backends/flux2.py
git commit -m "Map flux2 dependency, load, and inference failures to AdBackendError"
```

---

### Task 2: 기본 model_id·생성 파라미터 교정

현 기본값 `black-forest-labs/FLUX.2-klein`은 HF Hub에 존재하지 않는다(차단급). 실재하는 비게이트·apache-2.0 변형 `FLUX.2-klein-4B`로 바꾸고, distilled 모델에 맞는 권장 파라미터(4 steps, guidance 1.0)를 적용한다.

**Files:**
- Modify: `tests/test_flux2_backend.py` (테스트 추가)
- Modify: `src/dessert_ad_studio/backends/flux2.py`
- Modify: `.env.example:11`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_flux2_backend.py` 끝에 추가:

```python
def test_default_model_id_is_klein_4b(monkeypatch: pytest.MonkeyPatch) -> None:
    """기본 모델은 실재하는 비게이트 변형이어야 한다 (FLUX.2-klein은 Hub에 없음)"""
    monkeypatch.delenv("FLUX2_MODEL_ID", raising=False)
    assert Flux2Backend().model_id == "black-forest-labs/FLUX.2-klein-4B"


def test_env_var_overrides_model_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUX2_MODEL_ID", "custom/other-model")
    assert Flux2Backend().model_id == "custom/other-model"


def test_generation_uses_distilled_model_params(tmp_path: Path) -> None:
    """klein-4B는 distilled — 모델 카드 권장값 4 steps / guidance 1.0"""
    captured: dict = {}
    backend = Flux2Backend(output_dir=tmp_path)
    backend._pipeline = fake_image_pipeline(captured)

    backend.generate_image(sample_request(), image_prompt="지시문")

    assert captured["num_inference_steps"] == 4
    assert captured["guidance_scale"] == 1.0
    assert captured["width"] == 1024
    assert captured["height"] == 1024
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `.venv/bin/pytest tests/test_flux2_backend.py -v`
Expected: `test_default_model_id_is_klein_4b` FAIL (`FLUX.2-klein` ≠ `FLUX.2-klein-4B`), `test_generation_uses_distilled_model_params` FAIL (28 ≠ 4). `test_env_var_overrides_model_id`는 현 구현에서도 PASS여도 무방(회귀 가드).

- [ ] **Step 3: 최소 구현**

`flux2.py`에서 모듈 상수를 도입하고 두 곳을 교체한다.

import 아래(클래스 위)에 추가:

```python
DEFAULT_MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
# klein-4B is distilled; the model card recommends 4 steps with guidance 1.0.
NUM_INFERENCE_STEPS = 4
GUIDANCE_SCALE = 1.0
```

`__init__`의 model_id 줄 교체:

```python
        self.model_id = model_id or os.getenv("FLUX2_MODEL_ID", DEFAULT_MODEL_ID)
```

`generate_image`의 파이프라인 호출 교체:

```python
            result = pipeline(
                prompt=image_prompt,
                width=1024,
                height=1024,
                num_inference_steps=NUM_INFERENCE_STEPS,
                guidance_scale=GUIDANCE_SCALE,
            )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/pytest tests/test_flux2_backend.py -v`
Expected: 6 passed

- [ ] **Step 5: .env.example 갱신**

`.env.example`의 11행을 교체:

```
FLUX2_MODEL_ID=black-forest-labs/FLUX.2-klein-4B
```

- [ ] **Step 6: 커밋**

```bash
git add tests/test_flux2_backend.py src/dessert_ad_studio/backends/flux2.py .env.example
git commit -m "Default flux2 to FLUX.2-klein-4B with distilled-model generation params"
```

---

### Task 3: 추론 텔레메트리 (ImageResult.usage)

JD 정합 핵심: 생성 latency·스텝 수·VRAM peak를 `ImageResult.usage`로 반환한다. api/main.py가 이미 `image_usage`를 JSONL에 기록하므로 백엔드 반환값만 채우면 된다(무상태 계약 — 인스턴스 속성 금지).

**Files:**
- Modify: `tests/test_flux2_backend.py` (테스트 추가)
- Modify: `src/dessert_ad_studio/backends/flux2.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_flux2_backend.py` 끝에 추가:

```python
def test_success_returns_result_with_telemetry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """성공 시 usage에 latency/steps/VRAM 3종 키 — CPU(torch 없음)면 vram은 None"""
    monkeypatch.setitem(sys.modules, "torch", None)
    backend = Flux2Backend(output_dir=tmp_path)
    backend._pipeline = fake_image_pipeline()

    result = backend.generate_image(sample_request(), image_prompt="지시문")

    assert isinstance(result, ImageResult)
    assert Path(result.path).exists()
    assert result.usage is not None
    assert set(result.usage) == {"generation_seconds", "num_inference_steps", "vram_peak_gb"}
    assert result.usage["generation_seconds"] >= 0
    assert result.usage["num_inference_steps"] == 4
    assert result.usage["vram_peak_gb"] is None


def test_traversal_product_name_stays_inside_output_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "torch", None)
    backend = Flux2Backend(output_dir=tmp_path)
    backend._pipeline = fake_image_pipeline()

    result = backend.generate_image(sample_request("../../etc/passwd"), image_prompt="지시문")

    assert Path(result.path).resolve().is_relative_to(tmp_path.resolve())


def test_reference_image_capability_stays_off() -> None:
    """flux2는 t2i 전용 — 선언이 바뀌면 api의 업로드 거부 동작도 깨진다"""
    assert Flux2Backend.supports_reference_image is False
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `.venv/bin/pytest tests/test_flux2_backend.py -v`
Expected: `test_success_returns_result_with_telemetry` FAIL (`result.usage is None`). 나머지 2건은 PASS여도 무방(회귀 가드).

- [ ] **Step 3: 구현**

`flux2.py`에 `import time`을 추가하고, `_cuda_available` 헬퍼와 텔레메트리 수집을 넣는다. 최종 파일 전문:

```python
from __future__ import annotations

import os
import time
from pathlib import Path

from dessert_ad_studio.backends.base import AdBackendError, ImageResult
from dessert_ad_studio.backends.naming import safe_filename_stem
from dessert_ad_studio.schemas import GenerationRequest

DEFAULT_MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
# klein-4B is distilled; the model card recommends 4 steps with guidance 1.0.
NUM_INFERENCE_STEPS = 4
GUIDANCE_SCALE = 1.0


class Flux2Backend:
    name = "flux2"
    # Text-to-image only until the next round wires an i2i pipeline.
    supports_reference_image = False

    def __init__(self, output_dir: str | Path = "outputs", model_id: str | None = None) -> None:
        self.output_dir = Path(output_dir)
        self.model_id = model_id or os.getenv("FLUX2_MODEL_ID", DEFAULT_MODEL_ID)
        self._pipeline = None

    @staticmethod
    def _cuda_available() -> bool:
        # Tests stub out _load_pipeline, so torch may be absent here even
        # after a successful load; treat that as CPU.
        try:
            import torch
        except ImportError:
            return False
        return torch.cuda.is_available()

    def _load_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline

        try:
            import torch
            from diffusers import DiffusionPipeline
        except Exception as exc:
            raise AdBackendError(
                "FLUX.2 백엔드 의존성이 설치되지 않았습니다. pip install -e '.[image]'로 설치해주세요."
            ) from exc

        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        try:
            pipeline = DiffusionPipeline.from_pretrained(self.model_id, torch_dtype=dtype)
            if torch.cuda.is_available():
                pipeline = pipeline.to("cuda")
            else:
                pipeline.enable_model_cpu_offload()
        except Exception as exc:
            raise AdBackendError(f"FLUX.2 모델 로드에 실패했습니다: {exc}") from exc
        self._pipeline = pipeline
        return pipeline

    def generate_image(
        self,
        request: GenerationRequest,
        image_prompt: str,
        reference_image: bytes | None = None,
    ) -> ImageResult:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        pipeline = self._load_pipeline()

        cuda = self._cuda_available()
        if cuda:
            import torch

            torch.cuda.reset_peak_memory_stats()
        started = time.monotonic()
        try:
            result = pipeline(
                prompt=image_prompt,
                width=1024,
                height=1024,
                num_inference_steps=NUM_INFERENCE_STEPS,
                guidance_scale=GUIDANCE_SCALE,
            )
        except Exception as exc:
            raise AdBackendError(f"FLUX.2 이미지 생성에 실패했습니다: {exc}") from exc
        generation_seconds = time.monotonic() - started

        image = result.images[0]
        path = self.output_dir / f"{safe_filename_stem(request.product_name)}_flux2_ad.png"
        image.save(path)

        vram_peak_gb: float | None = None
        if cuda:
            import torch

            vram_peak_gb = round(torch.cuda.max_memory_allocated() / 1024**3, 2)
        usage = {
            "generation_seconds": round(generation_seconds, 2),
            "num_inference_steps": NUM_INFERENCE_STEPS,
            "vram_peak_gb": vram_peak_gb,
        }
        return ImageResult(path=str(path), usage=usage)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/pytest tests/test_flux2_backend.py -v`
Expected: 9 passed

- [ ] **Step 5: 전체 회귀 + 커밋**

Run: `.venv/bin/pytest -q`
Expected: 75 passed, 0 failed

```bash
git add tests/test_flux2_backend.py src/dessert_ad_studio/backends/flux2.py
git commit -m "Record flux2 latency, steps, and VRAM peak in ImageResult usage"
```

---

### Task 4: pyproject [image] 하한 상향

klein-4B는 `Flux2KleinPipeline`(diffusers 0.37+)과 `Qwen3ForCausalLM` 텍스트 인코더(transformers 4.51+)를 요구한다. 하한을 실측 요구치로 올린다.

**Files:**
- Modify: `pyproject.toml:26-32`

- [ ] **Step 1: [image] extras 수정**

`pyproject.toml`의 image 블록을 다음으로 교체:

```toml
image = [
  "torch>=2.3",
  "diffusers>=0.37",
  "transformers>=4.51",
  "accelerate>=0.33",
  "safetensors>=0.4",
]
```

- [ ] **Step 2: 검증**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check .`
Expected: 75 passed / All checks passed (extras는 로컬 미설치라 메타데이터 변경만 — 실설치 검증은 Task 13의 도커 빌드에서 일어난다)

- [ ] **Step 3: 커밋**

```bash
git add pyproject.toml
git commit -m "Raise image extras floors for Flux2KleinPipeline and Qwen3 encoder"
```

---

### Task 5: scripts/flux2_smoke.py

VM에서 API를 띄우기 전에 백엔드를 직접 1회 호출해보는 수동 스모크(openai_smoke.py 패턴). pytest에 포함하지 않는다.

**Files:**
- Create: `scripts/flux2_smoke.py`

- [ ] **Step 1: 스크립트 작성**

```python
"""Manual FLUX.2 smoke check. Requires the [image] extras; intended for a GPU VM.

Usage:
    python scripts/flux2_smoke.py

Generates one 1024x1024 image through Flux2Backend with the configured
FLUX2_MODEL_ID (default: black-forest-labs/FLUX.2-klein-4B) and prints the
output path plus telemetry. The first run also downloads the model weights
(~8GB+), so total_ms includes the download; usage["generation_seconds"] is
the pure inference time. It is intentionally not part of pytest.
"""

from __future__ import annotations

from time import perf_counter

from dotenv import load_dotenv

from dessert_ad_studio.backends.flux2 import Flux2Backend
from dessert_ad_studio.prompts import build_image_prompt
from dessert_ad_studio.schemas import GenerationRequest


def main() -> None:
    load_dotenv()
    request = GenerationRequest(
        campaign_purpose="new_menu",
        product_name="딸기 크림 크루아상",
        tone="warm",
        template_hint="cozy_cafe",
        price_text="6,800원",
        user_constraints="봄 시즌 한정 느낌",
    )
    backend = Flux2Backend(output_dir="outputs")
    prompt = build_image_prompt(request, ranked_template="cozy_cafe", has_reference=False)

    started = perf_counter()
    result = backend.generate_image(request, image_prompt=prompt)
    total_ms = (perf_counter() - started) * 1000
    print(
        {
            "model": backend.model_id,
            "total_ms": round(total_ms),
            "image_path": result.path,
            "usage": result.usage,
        }
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 로컬 음성 검증 (의존성 미설치 환경에서 에러 매핑 확인)**

Run: `.venv/bin/python scripts/flux2_smoke.py`
Expected: `AdBackendError: FLUX.2 백엔드 의존성이 설치되지 않았습니다. pip install -e '.[image]'로 설치해주세요.` — Task 1의 매핑이 실호출 경로에서도 동작함을 증명. (정상 생성 검증은 Task 14의 VM에서.)

- [ ] **Step 3: 커밋**

```bash
git add scripts/flux2_smoke.py
git commit -m "Add manual FLUX.2 smoke script with telemetry output"
```

---

### Task 6: Dockerfile.api — INSTALL_IMAGE_EXTRAS build arg

CPU 로컬 데모 이미지는 기존처럼 가볍게 유지하고, GPU 오버레이에서만 torch/diffusers를 설치한다. ARG를 base 설치 RUN 뒤에 둬서 arg 변경이 base 레이어 캐시를 깨지 않게 한다. 스모크 스크립트를 컨테이너에서 실행할 수 있도록 `scripts/`도 복사한다.

**Files:**
- Modify: `Dockerfile.api`

- [ ] **Step 1: Dockerfile 수정**

`Dockerfile.api` 전문을 다음으로 교체:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY api ./api
COPY scripts ./scripts
RUN pip install --no-cache-dir -e .

# GPU overlay sets this to 1 to pull in torch/diffusers (~5GB layer).
ARG INSTALL_IMAGE_EXTRAS=0
RUN if [ "$INSTALL_IMAGE_EXTRAS" = "1" ]; then \
      pip install --no-cache-dir -e ".[image]"; \
    fi

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 기본 경로 무변화 검증**

Run: `docker build -f Dockerfile.api -t dessert-api-cpu-check . 2>&1 | tail -5`
Expected: 빌드 성공, `[image]` 설치 분기 스킵(로그에 torch 다운로드 없음). 로컬에 Docker가 없거나 데몬이 꺼져 있으면 이 검증은 Task 13의 VM 빌드로 대체하고 넘어간다(스킵 사실을 작업 로그에 남길 것).

- [ ] **Step 3: 커밋**

```bash
git add Dockerfile.api
git commit -m "Add INSTALL_IMAGE_EXTRAS build arg and ship scripts in api image"
```

---

### Task 7: docker-compose.gpu.yml 오버레이

기본 compose 동작 불변. 오버레이로만 GPU 예약 + flux2 + Triton 비활성(REQUIRE_TRITON=0 → LocalTemplateScorer 폴백)을 켠다. HF 캐시는 named volume으로 모델 재다운로드를 방지한다.

**Files:**
- Create: `docker-compose.gpu.yml`

- [ ] **Step 1: 오버레이 작성**

```yaml
# GPU overlay for the flux2 image backend. Always combine with the base file:
#   docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d --no-deps api
# --no-deps skips the triton container; REQUIRE_TRITON=0 below makes the api
# fall back to LocalTemplateScorer so template scoring still works.
services:
  api:
    build:
      args:
        INSTALL_IMAGE_EXTRAS: "1"
    environment:
      REQUIRE_TRITON: "0"
      IMAGE_BACKEND: flux2
      FLUX2_MODEL_ID: ${FLUX2_MODEL_ID:-black-forest-labs/FLUX.2-klein-4B}
      HF_HOME: /data/hf-cache
    volumes:
      - hf-cache:/data/hf-cache
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

volumes:
  hf-cache:
```

- [ ] **Step 2: 병합 결과 검증**

Run: `docker compose -f docker-compose.yml -f docker-compose.gpu.yml config 2>&1 | grep -A2 -E "REQUIRE_TRITON|IMAGE_BACKEND|INSTALL_IMAGE_EXTRAS|nvidia"`
Expected: api 서비스에 `REQUIRE_TRITON: "0"`, `IMAGE_BACKEND: flux2`, build args `INSTALL_IMAGE_EXTRAS: "1"`, driver nvidia 예약이 보임. (Docker 미가동이면 `python3 -c "import yaml,sys; yaml.safe_load(open('docker-compose.gpu.yml'))"` 대신 — PyYAML이 없을 수 있으니 — Task 13 VM에서 `config`로 검증하고 스킵 사실을 기록.)

- [ ] **Step 3: 커밋**

```bash
git add docker-compose.gpu.yml
git commit -m "Add GPU compose overlay for flux2 with HF cache volume"
```

---

### Task 8: README — GPU 실행 섹션

**Files:**
- Modify: `README.md` (101행 "To use `openai` backends..." 문단 뒤, "Open Streamlit:" 앞에 삽입)

- [ ] **Step 1: 섹션 추가**

```markdown
### GPU demo with the flux2 backend

On an NVIDIA GPU machine (e.g. a GCP L4 VM with nvidia-container-toolkit),
start only the api service with the GPU overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d --no-deps api
```

The overlay installs the `[image]` extras into the image, switches
`IMAGE_BACKEND` to `flux2`, and sets `REQUIRE_TRITON=0` so template scoring
falls back to the local scorer without the Triton container. The first
request downloads the model weights (~8GB) into the `hf-cache` volume.
To run the backend without Docker instead: `pip install -e ".[image]"` then
`python scripts/flux2_smoke.py`. Full VM procedure:
`docs/runbooks/gcp-flux2-validation.md`.
```

- [ ] **Step 2: 커밋**

```bash
git add README.md
git commit -m "Document GPU compose overlay and flux2 smoke usage"
```

---

### Task 9: 계약 검토 + 코드 파트 마감 검증

**Files:** 없음 (검증만)

- [ ] **Step 1: backend-contract-reviewer 에이전트 실행**

Claude 세션에서 `backend-contract-reviewer` 에이전트를 디스패치한다. 프롬프트: "feature/flux2-gcp-validation 브랜치에서 src/dessert_ad_studio/backends/flux2.py가 변경되었다(에러 매핑, 텔레메트리, 모델 기본값). 백엔드 계약(무상태 공유 인스턴스, 한국어 AdBackendError, frozen dataclass, lazy import, supports_reference_image, 팩토리/env/테스트 4종 세트) 준수를 검토하라."
Expected: 위반 0건. 위반이 나오면 이 태스크에서 수정 후 재검토.

- [ ] **Step 2: 전체 검증**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check .`
Expected: 75 passed / All checks passed

- [ ] **Step 3: 푸시 (PR은 검증 증빙 확보 후 Task 18에서)**

```bash
git push -u origin feature/flux2-gcp-validation
```

---

## Part B — GCP 인프라·VM 검증

이 파트는 코드가 아닌 운영 절차다. 단계마다 출력 확인 후 진행하고, 실패 시 비용 가드(헤더 참조)를 따른다. `$PROJECT_ID`와 `$ZONE`은 Task 11–12에서 확정해 이후 명령에 일관되게 쓴다.

### Task 10: scripts/gcp/setup_vm.sh (VM 셋업 스크립트, repo에 커밋)

**Files:**
- Create: `scripts/gcp/setup_vm.sh`

- [ ] **Step 1: 스크립트 작성**

```bash
#!/usr/bin/env bash
# One-shot setup for a GCP accelerator-image VM (NVIDIA driver preinstalled):
# installs Docker Engine + compose plugin + NVIDIA Container Toolkit and
# verifies the GPU is visible from a container. Run ON the VM.
set -euo pipefail

# Driver sanity check first — fails fast on a non-accelerator image.
nvidia-smi

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
fi

curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --yes --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
sudo apt-get update -qq
sudo apt-get install -y -qq nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# End-to-end check: GPU visible inside a container.
sudo docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

- [ ] **Step 2: 정적 검증 + 실행 권한**

Run: `bash -n scripts/gcp/setup_vm.sh && chmod +x scripts/gcp/setup_vm.sh`
Expected: 구문 오류 없음

- [ ] **Step 3: 커밋**

```bash
git add scripts/gcp/setup_vm.sh
git commit -m "Add GCP VM setup script for Docker GPU runtime"
git push
```

---

### Task 11: gcloud 설치·인증·프로젝트·쿼터 확인

- [ ] **Step 1: gcloud 설치**

Run: `command -v gcloud || brew install --cask google-cloud-sdk`
Expected: gcloud 경로 출력 또는 설치 완료. 설치 직후 새 PATH가 필요하면 `source "$(brew --prefix)/share/google-cloud-sdk/path.zsh.inc"`.

- [ ] **Step 2: 사용자 인증 (유일한 수동 개입)**

사용자에게 안내: 프롬프트에 `! gcloud auth login` 입력 (times21c@gmail.com 선택).
확인: `gcloud auth list` → ACTIVE 계정 = times21c@gmail.com

- [ ] **Step 3: 프로젝트 확정**

```bash
gcloud projects list
```
기존 프로젝트가 있으면 그것을 쓰고, 없으면 생성(프로젝트 ID는 전역 유일 — 충돌 시 접미사 변경):

```bash
PROJECT_ID=dessert-ad-flux2-hskim
gcloud projects create "$PROJECT_ID"
gcloud billing accounts list
gcloud billing projects link "$PROJECT_ID" --billing-account=<위 출력의 ACCOUNT_ID>
gcloud config set project "$PROJECT_ID"
gcloud services enable compute.googleapis.com
```
Expected: 결제 연결 성공, Compute API 활성.

- [ ] **Step 4: GPU 쿼터 확인**

```bash
gcloud compute project-info describe --format=json | python3 -c "
import json, sys
for q in json.load(sys.stdin).get('quotas', []):
    if 'GPU' in q['metric']:
        print(q['metric'], 'limit:', q['limit'], 'usage:', q['usage'])
"
gcloud compute regions describe us-central1 --format=json | python3 -c "
import json, sys
for q in json.load(sys.stdin)['quotas']:
    if 'NVIDIA_L4' in q['metric']:
        print(q['metric'], 'limit:', q['limit'], 'usage:', q['usage'])
"
```
Expected: `GPUS_ALL_REGIONS limit >= 1` 그리고 us-central1의 `NVIDIA_L4_GPUS limit >= 1`.
**분기:** us-central1이 0이고 다른 리전(us-east1, us-west1, asia-northeast3)이 1 이상이면 그 리전으로 `$ZONE`을 잡는다. 전부 0이면 — 신규 유료 계정의 흔한 상태 — 콘솔(IAM & Admin → Quotas)에서 `GPUS_ALL_REGIONS`와 해당 리전 `NVIDIA_L4_GPUS`를 1로 증설 요청하도록 사용자에게 안내하고 **여기서 중단**(승인은 보통 분–시간 단위). 승인 후 이 태스크의 Step 4부터 재개.

---

### Task 12: L4 VM 생성

- [ ] **Step 1: 이미지 패밀리 실재 확인 (verify-then-use)**

```bash
gcloud compute images list --project=ubuntu-os-accelerator-images \
  --filter="family~nvidia-550" --format="value(family)" | sort -u
```
Expected: `ubuntu-accelerator-2204-amd64-with-nvidia-550` 포함. 없으면 출력된 2204 계열 최신 패밀리로 아래 명령을 치환.

- [ ] **Step 2: VM 생성**

```bash
ZONE=us-central1-a   # Task 11에서 쿼터 확인된 리전의 존
gcloud compute instances create flux2-l4 \
  --zone="$ZONE" \
  --machine-type=g2-standard-4 \
  --image-family=ubuntu-accelerator-2204-amd64-with-nvidia-550 \
  --image-project=ubuntu-os-accelerator-images \
  --boot-disk-size=100GB \
  --boot-disk-type=pd-balanced \
  --maintenance-policy=TERMINATE
```
Expected: STATUS RUNNING. (g2-standard-4는 L4 1개가 내장된 머신 타입 — `--accelerator` 플래그 불필요.)
**분기:** `ZONE_RESOURCE_POOL_EXHAUSTED`면 같은 리전의 b/c 존 → 다음 쿼터 보유 리전 순으로 재시도. 쿼터 오류면 Task 11 Step 4의 분기로.
**이 시점부터 과금 시작(~$0.85/h).**

---

### Task 13: VM 셋업 + 코드 전송 + 컨테이너 기동 + CUDA 확인

- [ ] **Step 1: 코드 전송 (git bundle — VM에 GitHub 인증 불필요)**

```bash
git bundle create /tmp/dessert-ad-studio.bundle feature/flux2-gcp-validation
gcloud compute scp /tmp/dessert-ad-studio.bundle flux2-l4:~ --zone="$ZONE"
gcloud compute ssh flux2-l4 --zone="$ZONE" \
  --command="git clone -b feature/flux2-gcp-validation ~/dessert-ad-studio.bundle ~/dessert-ad-studio"
```
Expected: clone 완료. (최초 ssh는 `~/.ssh/google_compute_engine` 키를 자동 생성 — passphrase는 비워도 됨.)

- [ ] **Step 2: VM 셋업 스크립트 실행**

```bash
gcloud compute ssh flux2-l4 --zone="$ZONE" \
  --command="bash ~/dessert-ad-studio/scripts/gcp/setup_vm.sh"
```
Expected: 마지막 출력이 컨테이너 안에서 찍힌 `nvidia-smi` 테이블(GPU: NVIDIA L4). 여기서 실패하면 드라이버/툴킷 문제 — `nvidia-smi`가 처음부터 실패하면 이미지 선택 오류이므로 VM을 정지하고 Task 12 Step 1 재확인.

- [ ] **Step 3: api 컨테이너 빌드·기동 (torch 설치 포함 ~10–20분)**

```bash
gcloud compute ssh flux2-l4 --zone="$ZONE" --command="cd ~/dessert-ad-studio && \
  sudo docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d --no-deps api"
```
Expected: api 컨테이너 Started. `--no-deps`가 triton 컨테이너(~10GB 이미지)를 건너뛴다.

- [ ] **Step 4: 컨테이너 내부 CUDA 확인 (완료 기준 1)**

```bash
gcloud compute ssh flux2-l4 --zone="$ZONE" --command="cd ~/dessert-ad-studio && \
  sudo docker compose -f docker-compose.yml -f docker-compose.gpu.yml exec api \
  python -c 'import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))'"
```
Expected: `True NVIDIA L4`

---

### Task 14: 스모크 + POST /generate + 증빙 회수

- [ ] **Step 1: 컨테이너 내 스모크 (최초 실행 = 모델 다운로드 ~8GB 포함, 수 분)**

```bash
gcloud compute ssh flux2-l4 --zone="$ZONE" --command="cd ~/dessert-ad-studio && \
  sudo docker compose -f docker-compose.yml -f docker-compose.gpu.yml exec api \
  python scripts/flux2_smoke.py"
```
Expected: `{'model': 'black-forest-labs/FLUX.2-klein-4B', 'total_ms': ..., 'image_path': 'outputs/..._flux2_ad.png', 'usage': {'generation_seconds': ..., 'num_inference_steps': 4, 'vram_peak_gb': ...}}` — generation_seconds는 수 초대, vram_peak_gb는 0이 아닌 양수. **이 수치를 기록해 둔다(ADR-0003·runbook에 들어감).**
**분기:** OOM이면 AdBackendError("FLUX.2 이미지 생성에 실패했습니다: ... out of memory")로 떨어진다 — spec §8 대응(klein-4B면 L4 24GB에서 발생하지 않아야 정상; 발생 시 컨테이너 로그 확보 후 VM 정지, 로컬 분석).

- [ ] **Step 2: API 경유 생성 (완료 기준 2)**

요청 페이로드를 로컬에서 만들어 VM으로 보낸 뒤 curl:

```bash
cat > /tmp/flux2_req.json <<'EOF'
{
  "campaign_purpose": "new_menu",
  "product_name": "딸기 크림 크루아상",
  "tone": "warm",
  "template_hint": "cozy_cafe",
  "price_text": "6,800원",
  "user_constraints": "봄 시즌 한정 느낌"
}
EOF
gcloud compute scp /tmp/flux2_req.json flux2-l4:/tmp/ --zone="$ZONE"
gcloud compute ssh flux2-l4 --zone="$ZONE" --command="curl -s -X POST http://localhost:8080/generate \
  -H 'Content-Type: application/json' -d @/tmp/flux2_req.json -w '\nHTTP %{http_code}\n'"
```
Expected: `HTTP 200`, 응답 JSON에 `"image_backend": "flux2"`와 `image_path`. (모델은 스모크에서 이미 캐시됨 — 이번엔 생성 시간만.)

- [ ] **Step 3: JSONL 텔레메트리 행 확인 (완료 기준 3)**

```bash
gcloud compute ssh flux2-l4 --zone="$ZONE" \
  --command="tail -n 1 ~/dessert-ad-studio/logs/generations.jsonl" | python3 -m json.tool
```
Expected: `image_usage`에 `generation_seconds`, `num_inference_steps`(4), `vram_peak_gb`(양수)가 채워진 행.

- [ ] **Step 4: 증빙 회수 (완료 기준 4)**

```bash
mkdir -p outputs/gcp-validation
gcloud compute scp 'flux2-l4:~/dessert-ad-studio/outputs/*_flux2_ad.png' outputs/gcp-validation/ --zone="$ZONE"
gcloud compute ssh flux2-l4 --zone="$ZONE" \
  --command="tail -n 2 ~/dessert-ad-studio/logs/generations.jsonl" \
  > outputs/gcp-validation/generations-excerpt.jsonl
ls -la outputs/gcp-validation/
```
Expected: PNG 1장 이상 + generations-excerpt.jsonl. (outputs/는 gitignored — 로컬 증빙 보관용이고, 수치는 ADR/runbook/PR 본문에 옮긴다.)

---

### Task 15: 자원 정리 (완료 기준 5)

- [ ] **Step 1: 컨테이너 정리 + VM 정지**

```bash
gcloud compute ssh flux2-l4 --zone="$ZONE" --command="cd ~/dessert-ad-studio && \
  sudo docker compose -f docker-compose.yml -f docker-compose.gpu.yml down"
gcloud compute instances stop flux2-l4 --zone="$ZONE"
```

- [ ] **Step 2: 정지 상태 재확인**

Run: `gcloud compute instances describe flux2-l4 --zone="$ZONE" --format="value(status)"`
Expected: `TERMINATED`
참고: 정지 상태에서도 100GB pd-balanced 디스크는 월 ~$10 과금된다. 재검증 계획이 없어지면 `gcloud compute instances delete flux2-l4 --zone="$ZONE"`로 완전 삭제(사용자 결정 사항 — 임의 실행 금지, runbook에 명시).

---

## Part C — 문서화·마감

### Task 16: runbook 작성

**Files:**
- Create: `docs/runbooks/gcp-flux2-validation.md`

- [ ] **Step 1: runbook 작성**

아래 골격으로 작성하되, **명령은 Part B에서 실제로 동작한 최종 형태로**(존/리전/이미지 패밀리/프로젝트 ID 등 실행 중 바뀐 값 반영), `<measured>` 자리에는 Task 14에서 기록한 실측치를 기입한다:

```markdown
# Runbook: GCP L4에서 FLUX.2 검증 데모 재실행

검증 완료: 2026-06-11 (브랜치 feature/flux2-gcp-validation). 1회 실행 비용 ~$2–3
(g2-standard-4 ~$0.85/h × 2–3h), 정지 중 디스크 ~$10/월.

## 사전 조건
- gcloud CLI 인증 (times21c@gmail.com), 프로젝트 <실행에 쓴 PROJECT_ID>
- GPU 쿼터: GPUS_ALL_REGIONS >= 1, <리전> NVIDIA_L4_GPUS >= 1

## 1. VM 기동 (이미 만들어 둔 VM 재사용)
gcloud compute instances start flux2-l4 --zone=<ZONE>
# 처음부터 만들 때는 본 문서 부록 A의 create 명령 사용

## 2. 코드 갱신 + 컨테이너 기동
(Task 13의 실제 동작 명령들)

## 3. 검증
(Task 14의 실제 동작 명령들 + 기대 출력)

## 4. 정지 (필수)
gcloud compute instances stop flux2-l4 --zone=<ZONE>
gcloud compute instances describe flux2-l4 --zone=<ZONE> --format="value(status)"  # TERMINATED

## 실측 기준선 (2026-06-11, klein-4B, 4 steps, 1024x1024)
| 지표 | 값 |
|---|---|
| generation_seconds | <measured> |
| vram_peak_gb | <measured> |
| 컨테이너 빌드 시간 | <measured> |
| 모델 다운로드 시간/크기 | <measured> |

## 부록 A: VM 신규 생성
(Task 12의 실제 동작 명령 + scripts/gcp/setup_vm.sh 실행)

## 부록 B: 완전 철거
gcloud compute instances delete flux2-l4 --zone=<ZONE>   # 디스크 과금 종료
```

- [ ] **Step 2: 커밋**

```bash
git add docs/runbooks/gcp-flux2-validation.md
git commit -m "Add runbook for the GCP L4 flux2 validation demo"
```

---

### Task 17: ADR-0003 작성

**Files:**
- Create: `docs/adr/0003-flux2-validation-model-and-deployment.md` (`docs/adr/template.md` 형식 준수)

- [ ] **Step 1: ADR 작성**

아래 내용으로 작성한다. "실측 결과" 표의 `<measured>` 두 칸만 Task 14 기록값으로 채운다:

```markdown
# 0003. FLUX.2 검증 라운드: 모델 변형·배포 경로·텔레메트리

- 상태: 승인됨
- 날짜: 2026-06-11
- 관련: ADR-0002(FLUX.2 헤지), spec `docs/superpowers/specs/2026-06-11-flux2-gcp-validation-design.md`

## 맥락

flux2 백엔드를 GCP L4 VM에서 실검증하는 라운드. 선택 기준에 과제 요건 외에
**포트폴리오 가치(AI 서비스 백엔드 JD 정합: Docker/K8s, inference 성능·비용
최적화, 로컬 모델 서빙)**를 포함한다. 비용은 개인 유료 계정 실비.

## 결정 1: 모델 변형 — FLUX.2-klein-4B

기존 기본값 `black-forest-labs/FLUX.2-klein`은 HF Hub에 존재하지 않았다(2026-06-11
Hub API 확인). 실재 변형 비교:

| 기준 | klein-4B (채택) | klein-9B | FLUX.2-dev |
|---|---|---|---|
| 게이트 | 없음 (gated: False) | gated: auto | gated: auto |
| 라이선스 | apache-2.0 (상업 광고 OK) | other (비상업 계열) | other (비상업 계열) |
| bf16 VRAM (대략) | ~8GB — L4 24GB 여유 | ~18GB — 빠듯 | 24GB+ — 불가 |
| 권장 생성 | 4 steps / guidance 1.0 (distilled) | 동일 계열 | 50 steps급 |
| 16GB RAM 로드 | 여유 | 위험 | 불가 |

광고 생성 용도(상업)에서 라이선스·게이트·VRAM 모두 무리 없는 변형은 klein-4B뿐.
생성 파라미터도 distilled 권장값(4 steps, guidance 1.0)으로 교정했다.

## 결정 2: 배포 경로 — Docker Compose GPU 오버레이

| 기준 | venv 직접 실행 | Docker GPU 오버레이 (채택) |
|---|---|---|
| 검증까지 추가 시간 | 0 | +30–60분 (toolkit, 빌드) |
| 재현성 | VM 로컬 상태 의존 | compose 파일로 고정 |
| 로컬 CPU 데모 영향 | 없음 | 없음 (오버레이 분리) |
| 포트폴리오 가치 | 낮음 | 높음 — JD 필요 역량(컨테이너 GPU 서빙) 직접 증거 |

JD 정합 기준이 없었다면 venv가 합리적이나(실제로 1차 선택), 사용자 커리어 타깃
반영으로 Docker 경로를 채택. `INSTALL_IMAGE_EXTRAS` build arg로 CPU 이미지는
기존처럼 가볍게 유지한다.

## 결정 3: 추론 텔레메트리 — ImageResult.usage로 반환

| 기준 | 기록 안 함 | usage 반환값 (채택) | 별도 미들웨어/APM |
|---|---|---|---|
| 백엔드 무상태 계약 | — | 유지 (반환값 전달) | 유지 |
| 구현 비용 | 0 | 소 (기존 JSONL 경로 재사용) | 대 |
| JD 증거 (inference 성능·비용) | 없음 | 기준선 수치 확보 | 과잉 |

`generation_seconds`(time.monotonic) / `num_inference_steps` / `vram_peak_gb`
(torch.cuda.max_memory_allocated)를 기록 — 이후 최적화(스텝 수, dtype, 배치)의
전/후 비교 기준선이 된다.

## 실측 결과 (2026-06-11, L4, 1024x1024, 4 steps)

| 지표 | 값 |
|---|---|
| generation_seconds | <measured> |
| vram_peak_gb | <measured> |

## 각주: Triton 재평가

ADR-0002 결정 1의 "과제 종료 후 onnxruntime 간소화 권고"는 JD의 Triton 서빙
우대를 반영해 보류한다. Triton 경로는 포트폴리오 가치가 있으므로 과제 종료
시점에 재평가한다.

## 재평가 트리거

- i2i(reference 이미지) 요구 확정 시: klein-4B의 i2i 파이프라인 지원 재조사
  (ADR-0002 트리거와 동일).
- klein-9B/dev 라이선스가 상업 허용으로 바뀌거나 게이트가 풀리면 품질 비교 재실시.
- 상시 데모/대규모 트래픽 요구 발생 시: K8s(GKE) 서빙 라운드로 승격.
```

- [ ] **Step 2: 커밋**

```bash
git add docs/adr/0003-flux2-validation-model-and-deployment.md
git commit -m "Record ADR-0003: flux2 model variant, GPU deployment path, telemetry"
```

---

### Task 18: 최종 검증 + PR 생성

- [ ] **Step 1: 전체 검증 (fresh evidence)**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check .`
Expected: 75 passed / All checks passed

- [ ] **Step 2: 완료 기준 6항목 체크리스트 대조**

spec §4의 6항목을 하나씩 실증과 대조: ① 컨테이너 CUDA True(Task 13 Step 4 출력) ② /generate 200 + PNG(Task 14 Step 2) ③ JSONL image_usage(Task 14 Step 3) ④ 증빙 회수(Task 14 Step 4) ⑤ VM TERMINATED(Task 15 Step 2) ⑥ 테스트·계약 검토(Task 9, Step 1). 하나라도 미충족이면 해당 태스크로 돌아간다.

- [ ] **Step 3: 푸시 + PR 생성**

```bash
git push
gh pr create --base main --title "FLUX.2 GCP L4 validation round" --body "$(cat <<'EOF'
## Summary
- flux2 백엔드 계약 준수 교정: AdBackendError 매핑 3종(의존성/로드/추론), 실재 모델 기본값(FLUX.2-klein-4B), distilled 권장 파라미터(4 steps/guidance 1.0)
- 추론 텔레메트리: ImageResult.usage(generation_seconds/num_inference_steps/vram_peak_gb) → 기존 JSONL image_usage 경로로 기록
- Docker GPU 경로: Dockerfile.api INSTALL_IMAGE_EXTRAS build arg + docker-compose.gpu.yml 오버레이(GPU 예약, REQUIRE_TRITON=0, HF 캐시 볼륨)
- GCP L4 실검증 완료: 컨테이너 내 CUDA → flux2 smoke → POST /generate 200 → 텔레메트리 JSONL → VM 정지 (실측치는 ADR-0003·runbook 참조)
- 문서: ADR-0003(모델 변형/배포 경로/텔레메트리 비교표), runbook, README GPU 섹션

## Test plan
- [ ] `pytest -q` 75 passed (신규 flux2 단위 테스트 9건 포함, mock 기반 — GPU 불필요)
- [ ] `ruff check .` clean
- [ ] backend-contract-reviewer 검토 통과
- [ ] GCP 검증 증빙: outputs/gcp-validation/ (로컬), 수치는 ADR-0003

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

PR 본문의 체크리스트는 Step 1–2의 실증 결과에 맞춰 체크 표시로 바꿔서 제출한다.

---

## Self-Review 결과

- **Spec coverage:** §5.1(Task 1–3) §5.2(Task 4) §5.3(Task 6–7) §5.4(Task 1–3, 9건 — spec 최소 5케이스 초과 충족; 기존 test_api.py flux2 reference 거부 2건은 변경 없이 회귀 유지) §5.5(Task 5, 2 Step 5, 8) §6(Task 10–12) §7(Task 13–15) §9(Task 16–18). 누락 없음.
- **Placeholder:** runbook/ADR의 `<measured>`는 Task 14 실행 출력에서 채우는 데이터 흐름으로, 작성 시점에 알 수 없는 값임을 본문에 명시함. 그 외 TBD 없음.
- **Type consistency:** usage 키 3종(generation_seconds/num_inference_steps/vram_peak_gb), 상수명(DEFAULT_MODEL_ID/NUM_INFERENCE_STEPS/GUIDANCE_SCALE), VM 이름(flux2-l4), 테스트 헬퍼(sample_request/fake_image_pipeline)가 전 태스크에서 동일.
