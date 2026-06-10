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
