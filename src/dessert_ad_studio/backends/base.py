from __future__ import annotations

from typing import Protocol, runtime_checkable

from dessert_ad_studio.schemas import CopyOption, GenerationRequest


class AdBackendError(Exception):
    """User-facing backend failure with a Korean detail message."""

    def __init__(self, detail: str, status_code: int = 503) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@runtime_checkable
class CopyBackend(Protocol):
    """Generates three Korean ad-copy options.

    Implementations may expose ``model_id`` and ``last_usage`` attributes;
    the API logs them via ``getattr`` when present.
    """

    name: str

    def generate_copy(self, request: GenerationRequest) -> list[CopyOption]: ...


@runtime_checkable
class ImageBackend(Protocol):
    """Generates one ad image and returns the saved file path.

    ``supports_reference_image`` declares whether ``reference_image`` is
    actually applied; the API rejects reference uploads for backends that
    would silently ignore them.
    """

    name: str
    supports_reference_image: bool

    def generate_image(
        self,
        request: GenerationRequest,
        image_prompt: str,
        reference_image: bytes | None = None,
    ) -> str: ...
