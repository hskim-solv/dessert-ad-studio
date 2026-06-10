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

    def generate_image(
        self,
        request: GenerationRequest,
        image_prompt: str,
        reference_image: bytes | None = None,
    ) -> str:
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
