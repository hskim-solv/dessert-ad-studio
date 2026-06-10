from __future__ import annotations

import base64
import binascii
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

        data = result.data
        if not data:
            raise AdBackendError("이미지 생성 응답이 비어 있습니다. 다시 시도해주세요.")
        image_b64 = data[0].b64_json
        if not image_b64:
            raise AdBackendError("이미지 생성 응답이 비어 있습니다. 다시 시도해주세요.")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{request.product_name.replace(' ', '_')}_openai_ad.png"
        try:
            raw = base64.b64decode(image_b64)
        except (binascii.Error, ValueError) as exc:
            raise AdBackendError("이미지 응답을 디코딩하지 못했습니다. 다시 시도해주세요.") from exc
        path.write_bytes(raw)
        usage = getattr(result, "usage", None)
        if usage is not None:
            self.last_usage = {"total_tokens": getattr(usage, "total_tokens", None)}
        return str(path)
