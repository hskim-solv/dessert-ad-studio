from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_generate_uses_template_ranking_and_returns_copy() -> None:
    response = client.post(
        "/generate",
        json={
            "campaign_purpose": "new_menu",
            "product_name": "말차 푸딩",
            "tone": "clean",
            "template_hint": "minimal_premium",
            "price_text": "5,500원",
            "user_constraints": "깔끔한 프리미엄 느낌",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["copy_options"]) == 3
    assert payload["selected_template"]["scorer"] in {
        "local-template-scorer",
        "triton-template-scorer",
    }
    assert payload["image_backend"] == "mock"
    assert payload["image_path"].endswith(".png")
