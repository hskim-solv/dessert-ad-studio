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
