import json

from dessert_ad_studio.generation_logger import GenerationLogger


def test_generation_logger_writes_one_json_line(tmp_path) -> None:
    log_path = tmp_path / "generations.jsonl"
    logger = GenerationLogger(log_path)

    logger.write(
        {
            "campaign_purpose": "new_menu",
            "template": "cozy_cafe",
            "image_backend": "mock",
            "triton_latency_ms": 4.2,
        }
    )

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["campaign_purpose"] == "new_menu"
    assert payload["template"] == "cozy_cafe"
    assert "created_at" in payload
