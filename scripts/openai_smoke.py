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
