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


def test_concurrent_first_calls_load_pipeline_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """공유 인스턴스에 동시 첫 요청 2건 → 파이프라인 로드는 정확히 1회"""
    import threading

    load_calls = []
    barrier = threading.Barrier(2)

    def fake_from_pretrained(model_id, torch_dtype):
        try:
            barrier.wait(timeout=2)
        except threading.BrokenBarrierError:
            pass
        load_calls.append(model_id)

        class _Pipe:
            def enable_model_cpu_offload(self):
                return None

            def __call__(self, **kwargs):
                return fake_image_pipeline()(**kwargs)

        return _Pipe()

    fake_torch = SimpleNamespace(
        bfloat16="bf16",
        float32="fp32",
        cuda=SimpleNamespace(is_available=lambda: False),
    )
    fake_diffusers = SimpleNamespace(
        DiffusionPipeline=SimpleNamespace(from_pretrained=fake_from_pretrained)
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "diffusers", fake_diffusers)

    backend = Flux2Backend(output_dir=tmp_path)
    errors = []

    def worker():
        try:
            backend.generate_image(sample_request(), image_prompt="지시문")
        except Exception as exc:  # noqa: BLE001 - 테스트 수집용
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert errors == []
    assert len(load_calls) == 1
