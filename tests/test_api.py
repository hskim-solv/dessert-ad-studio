import base64
import io

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


def test_generate_rejects_unknown_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_BACKEND", "unknown-backend")

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 501


def test_generate_survives_log_write_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from dessert_ad_studio.generation_logger import GenerationLogger

    monkeypatch.setattr(GenerationLogger, "write", lambda self, record: (_ for _ in ()).throw(OSError("disk full")))

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 200
