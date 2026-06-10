import base64
import io
from pathlib import Path
from types import SimpleNamespace

import httpx
import openai
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


def _make_httpx_request() -> httpx.Request:
    return httpx.Request("POST", "https://api.openai.com/v1/images/generations")


def _make_httpx_response(status_code: int = 400) -> httpx.Response:
    return httpx.Response(status_code, request=_make_httpx_request())


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


class RaisingImages:
    """FakeImages variant that raises a given SDK exception from generate()."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def generate(self, **kwargs):
        raise self._exc

    def edit(self, **kwargs):
        raise self._exc


def make_fake_client(b64: str) -> SimpleNamespace:
    return SimpleNamespace(images=FakeImages(b64))


# ---------------------------------------------------------------------------
# Existing Task 6 tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# New: SDK exception mapping tests (Commit 1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc, expected_status_code",
    [
        (
            openai.AuthenticationError("invalid key", response=_make_httpx_response(401), body=None),
            503,
        ),
        (
            openai.RateLimitError("rate limit", response=_make_httpx_response(429), body=None),
            503,
        ),
        (
            openai.BadRequestError("bad request", response=_make_httpx_response(400), body=None),
            422,
        ),
        (
            openai.APIError("api error", request=_make_httpx_request(), body=None),
            503,
        ),
    ],
)
def test_sdk_exceptions_map_to_backend_error(
    tmp_path: Path, exc: Exception, expected_status_code: int
) -> None:
    client = SimpleNamespace(images=RaisingImages(exc))
    backend = OpenAIImageBackend(output_dir=tmp_path, client=client)

    with pytest.raises(AdBackendError) as exc_info:
        backend.generate_image(sample_request(), image_prompt="지시문")

    assert exc_info.value.status_code == expected_status_code


def test_data_none_response_maps_to_backend_error(tmp_path: Path) -> None:
    """result.data is None → TypeError 누출 전에 AdBackendError로 매핑"""
    client = SimpleNamespace(
        images=SimpleNamespace(
            generate=lambda **kw: SimpleNamespace(data=None, usage=None)
        )
    )
    backend = OpenAIImageBackend(output_dir=tmp_path, client=client)

    with pytest.raises(AdBackendError, match="비어"):
        backend.generate_image(sample_request(), image_prompt="지시문")


def test_data_empty_list_response_maps_to_backend_error(tmp_path: Path) -> None:
    """result.data == [] → IndexError 누출 전에 AdBackendError로 매핑"""
    client = SimpleNamespace(
        images=SimpleNamespace(
            generate=lambda **kw: SimpleNamespace(data=[], usage=None)
        )
    )
    backend = OpenAIImageBackend(output_dir=tmp_path, client=client)

    with pytest.raises(AdBackendError, match="비어"):
        backend.generate_image(sample_request(), image_prompt="지시문")


def test_malformed_b64_maps_to_backend_error(tmp_path: Path) -> None:
    """non-empty but invalid b64 → binascii.Error 누출 전에 AdBackendError로 매핑"""
    client = make_fake_client("!!!not-base64!!!")
    backend = OpenAIImageBackend(output_dir=tmp_path, client=client)

    with pytest.raises(AdBackendError, match="디코딩"):
        backend.generate_image(sample_request(), image_prompt="지시문")
