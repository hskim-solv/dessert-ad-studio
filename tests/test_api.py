import base64
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from api.main import app

client = TestClient(app)


def base_payload() -> dict:
    return {
        "campaign_purpose": "new_menu",
        "product_name": "말차 푸딩",
        "tone": "clean",
        "template_hint": "minimal_premium",
        "price_text": "5,500원",
        "user_constraints": "깔끔한 프리미엄 느낌",
    }


def tiny_png_b64() -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color=(120, 200, 160)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_livez() -> None:
    response = client.get("/livez")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readyz(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

    response = client.get("/readyz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["copy_backend"] == "mock"
    assert body["image_backend"] == "mock"
    assert body["product_analysis_backend"] == "mock"
    assert body["template_scorer"] == "local-template-scorer"


def test_readyz_rejects_bad_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPY_BACKEND", "missing")

    response = client.get("/readyz")

    assert response.status_code == 503
    assert "unknown copy backend: missing" in response.json()["detail"]


def test_readyz_checks_required_triton(monkeypatch: pytest.MonkeyPatch) -> None:
    import api.main as api_main

    monkeypatch.setenv("REQUIRE_TRITON", "1")
    monkeypatch.setattr(api_main, "_is_triton_ready", lambda url: False)

    response = client.get("/readyz")

    assert response.status_code == 503
    assert "triton template_scorer is not ready" in response.json()["detail"]


def test_metrics_exposes_prometheus_text() -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert 'dessert_ad_studio_info{service="api"} 1' in response.text
    assert "dessert_ad_studio_http_requests_total" in response.text


def test_generate_uses_template_ranking_and_returns_copy() -> None:
    response = client.post("/generate", json=base_payload())

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["copy_options"]) == 3
    assert payload["selected_template"]["scorer"] in {
        "local-template-scorer",
        "triton-template-scorer",
    }
    assert payload["copy_backend"] == "mock"
    assert payload["image_backend"] == "mock"
    assert payload["used_reference"] is False
    assert payload["image_path"].endswith(".png")
    assert payload["product_analysis"]["analyzer_backend"] == "mock"
    assert payload["elapsed_ms"] >= 0


def test_generate_with_reference_image_flags_usage() -> None:
    payload = {
        **base_payload(),
        "reference_image_b64": tiny_png_b64(),
        "reference_image_name": "store_photo.png",
    }

    response = client.post("/generate", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["used_reference"] is True
    assert body["prompt_summary"].splitlines()[0] == (
        "업로드된 제품 사진의 피사체와 구도를 보존하면서 광고 이미지로 연출한다."
    )


def test_generate_includes_product_analysis(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    response = client.post("/generate", json=base_payload())

    assert response.status_code == 200
    analysis = response.json()["product_analysis"]
    assert analysis["label"] == "Product analysis"
    assert analysis["analyzer_backend"] == "mock"
    assert "말차 푸딩" in analysis["product_context"]
    assert "참고 이미지 없음" in analysis["photo_strategy"]


def test_generate_ignores_reference_name_without_image_bytes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    payload = {**base_payload(), "reference_image_name": "cake.png"}

    response = client.post("/generate", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["used_reference"] is False
    assert "참고 이미지 없음" in body["product_analysis"]["photo_strategy"]


def test_generate_product_analysis_reflects_reference_image(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    payload = {
        **base_payload(),
        "reference_image_b64": tiny_png_b64(),
        "reference_image_name": "cake.png",
    }
    response = client.post("/generate", json=payload)

    assert response.status_code == 200
    assert "업로드된 제품 사진" in response.json()["product_analysis"]["photo_strategy"]


def test_generate_rejects_unknown_product_analysis_backend(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("PRODUCT_ANALYSIS_BACKEND", "vlm")

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 501
    assert response.json()["detail"] == "unknown product analysis backend: vlm"


def test_generate_rejects_reference_image_for_flux2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_BACKEND", "flux2")
    payload = {
        **base_payload(),
        "reference_image_b64": tiny_png_b64(),
        "reference_image_name": "store_photo.png",
    }

    response = client.post("/generate", json=payload)

    assert response.status_code == 400
    assert "참고 이미지" in response.json()["detail"]


def test_flux2_reference_rejection_spends_no_copy_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    from dessert_ad_studio.backends.mock import MockAdBackend

    def fail_if_called(self, request):
        raise AssertionError("copy backend must not be called when the reference is rejected")

    monkeypatch.setattr(MockAdBackend, "generate_copy", fail_if_called)
    monkeypatch.setenv("IMAGE_BACKEND", "flux2")
    payload = {**base_payload(), "reference_image_b64": tiny_png_b64()}

    response = client.post("/generate", json=payload)

    assert response.status_code == 400


def test_generate_rejects_invalid_reference_encoding() -> None:
    payload = {**base_payload(), "reference_image_b64": "not-base64!!!"}

    response = client.post("/generate", json=payload)

    assert response.status_code == 400
    assert "base64" in response.json()["detail"]


def test_generate_maps_missing_openai_key_to_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPY_BACKEND", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_generate_preserves_backend_error_status_code(monkeypatch: pytest.MonkeyPatch) -> None:
    from dessert_ad_studio.backends.base import AdBackendError
    from dessert_ad_studio.backends.mock import MockAdBackend

    def fail_with_validation_error(self, request):
        raise AdBackendError("bad input", status_code=422)

    monkeypatch.setattr(MockAdBackend, "generate_copy", fail_with_validation_error)

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 422
    assert response.json()["detail"] == "bad input"


def test_generate_maps_required_triton_template_failure_to_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.main as api_main

    class FailingTemplateScorer:
        def rank(self, request):
            raise RuntimeError("template scoring unavailable")

    monkeypatch.setenv("REQUIRE_TRITON", "1")
    monkeypatch.setattr(api_main, "get_template_scorer", lambda: FailingTemplateScorer())

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 503
    assert "Triton template scoring failed" in response.json()["detail"]


def test_generate_rejects_unknown_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_BACKEND", "unknown-backend")

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 501


def test_generate_logs_usage_from_returned_results(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """JSONL usage must come from each request's own result objects, not from
    attributes on the cached (shared) backend instances."""
    import api.main as api_main
    from dessert_ad_studio.backends.base import CopyResult, ImageResult
    from dessert_ad_studio.schemas import CopyOption

    log_path = tmp_path / "generations.jsonl"
    monkeypatch.setenv("GENERATION_LOG_PATH", str(log_path))

    class FakeCopyBackend:
        name = "fake-copy"
        model_id = "fake-copy-model"

        def generate_copy(self, request):
            options = [
                CopyOption(headline=f"헤드라인 {i}", body="본문", call_to_action="행동 유도")
                for i in range(3)
            ]
            return CopyResult(
                options=options,
                usage={"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33},
            )

    class FakeImageBackend:
        name = "fake-image"
        model_id = "fake-image-model"
        supports_reference_image = True

        def generate_image(self, request, image_prompt, reference_image=None):
            path = tmp_path / "fake.png"
            path.write_bytes(b"png")
            return ImageResult(path=str(path), usage={"total_tokens": 44})

    monkeypatch.setattr(api_main, "_copy_backend_for", lambda name, output_dir: FakeCopyBackend())
    monkeypatch.setattr(api_main, "_image_backend_for", lambda name, output_dir: FakeImageBackend())

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 200
    record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert record["copy_usage"] == {
        "prompt_tokens": 11,
        "completion_tokens": 22,
        "total_tokens": 33,
    }
    assert record["image_usage"] == {"total_tokens": 44}


def test_image_failure_still_logs_spent_copy_usage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When the image call fails after copy succeeded, the spent copy tokens
    must still land in the quota log even though the request returns 5xx."""
    import api.main as api_main
    from dessert_ad_studio.backends.base import AdBackendError, CopyResult
    from dessert_ad_studio.schemas import CopyOption

    log_path = tmp_path / "generations.jsonl"
    monkeypatch.setenv("GENERATION_LOG_PATH", str(log_path))

    class FakeCopyBackend:
        name = "fake-copy"
        model_id = "fake-copy-model"

        def generate_copy(self, request):
            options = [
                CopyOption(headline=f"헤드라인 {i}", body="본문", call_to_action="행동 유도")
                for i in range(3)
            ]
            return CopyResult(
                options=options,
                usage={"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33},
            )

    class FailingImageBackend:
        name = "failing-image"
        model_id = "failing-image-model"
        supports_reference_image = True

        def generate_image(self, request, image_prompt, reference_image=None):
            raise AdBackendError("이미지 생성 API 호출에 실패했습니다: boom")

    monkeypatch.setattr(api_main, "_copy_backend_for", lambda name, output_dir: FakeCopyBackend())
    monkeypatch.setattr(
        api_main, "_image_backend_for", lambda name, output_dir: FailingImageBackend()
    )

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 503
    record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert record["copy_usage"] == {
        "prompt_tokens": 11,
        "completion_tokens": 22,
        "total_tokens": 33,
    }
    assert record["error"] == "이미지 생성 API 호출에 실패했습니다: boom"
    assert record["image_path"] is None
    assert record["image_usage"] is None


def test_copy_failure_logs_no_row(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """If copy itself fails there is no usage to attribute — no row is written."""
    import api.main as api_main
    from dessert_ad_studio.backends.base import AdBackendError

    log_path = tmp_path / "generations.jsonl"
    monkeypatch.setenv("GENERATION_LOG_PATH", str(log_path))

    class FailingCopyBackend:
        name = "failing-copy"
        model_id = "failing-copy-model"

        def generate_copy(self, request):
            raise AdBackendError("문구 생성 API 호출에 실패했습니다: boom")

    monkeypatch.setattr(
        api_main, "_copy_backend_for", lambda name, output_dir: FailingCopyBackend()
    )

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 503
    assert not log_path.exists()


def test_generate_survives_log_write_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from dessert_ad_studio.generation_logger import GenerationLogger

    monkeypatch.setattr(
        GenerationLogger, "write", lambda self, record: (_ for _ in ()).throw(OSError("disk full"))
    )

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 200


def test_template_scorer_defaults_to_local_without_require_triton(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without REQUIRE_TRITON=1 the scorer must be local from the start, so
    Triton-less deployments never pay a per-request connection failure."""
    import api.main as api_main
    from dessert_ad_studio.triton import LocalTemplateScorer

    monkeypatch.delenv("REQUIRE_TRITON", raising=False)

    assert isinstance(api_main.get_template_scorer(), LocalTemplateScorer)


def test_template_scorer_uses_triton_when_required(monkeypatch: pytest.MonkeyPatch) -> None:
    import api.main as api_main
    from dessert_ad_studio.triton import TritonTemplateScorer

    monkeypatch.setenv("REQUIRE_TRITON", "1")

    assert isinstance(api_main.get_template_scorer(), TritonTemplateScorer)
