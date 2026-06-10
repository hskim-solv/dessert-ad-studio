from dessert_ad_studio.backends.base import AdBackendError, CopyBackend, ImageBackend
from dessert_ad_studio.backends.mock import MockAdBackend


def test_ad_backend_error_carries_status_and_detail() -> None:
    error = AdBackendError("한도 초과", status_code=503)

    assert error.detail == "한도 초과"
    assert error.status_code == 503
    assert str(error) == "한도 초과"


def test_ad_backend_error_defaults_to_503() -> None:
    assert AdBackendError("실패").status_code == 503


def test_mock_backend_satisfies_both_protocols() -> None:
    backend = MockAdBackend()

    assert isinstance(backend, CopyBackend)
    assert isinstance(backend, ImageBackend)
