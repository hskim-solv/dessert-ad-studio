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
