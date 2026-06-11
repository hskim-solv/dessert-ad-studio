from __future__ import annotations

import os
import threading
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
        self._pipeline_lock = threading.Lock()

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
        with self._pipeline_lock:
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
