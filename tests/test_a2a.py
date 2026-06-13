import pytest

from dessert_ad_studio.a2a import (
    A2AInputError,
    A2ATaskStore,
    build_agent_card,
    completed_generation_task,
    extract_generation_request,
)
from dessert_ad_studio.schemas import GenerationResponse


def generation_payload() -> dict:
    return {
        "campaign_purpose": "new_menu",
        "product_name": "말차 푸딩",
        "tone": "clean",
        "template_hint": "minimal_premium",
        "price_text": "5,500원",
        "user_constraints": "깔끔한 프리미엄 느낌",
    }


def generation_response() -> GenerationResponse:
    return GenerationResponse.model_validate(
        {
            "copy_options": [
                {
                    "headline": "말차 푸딩 출시",
                    "body": "진한 말차와 부드러운 푸딩을 지금 만나보세요.",
                    "call_to_action": "오늘 방문하기",
                }
            ],
            "selected_template": {
                "template_name": "minimal_premium",
                "score": 0.92,
                "scorer": "rule_based",
                "latency_ms": 2.5,
            },
            "image_path": "/tmp/ad.png",
            "image_backend": "pil",
            "copy_backend": "rules",
            "used_reference": False,
            "prompt_summary": "minimal premium matcha pudding ad",
            "elapsed_ms": 125.0,
            "product_analysis": {
                "label": "말차 푸딩",
                "product_context": "신메뉴 디저트",
                "ad_goal": "출시 홍보",
                "visual_strategy": "clean layout",
                "photo_strategy": "product focused",
                "copy_focus": "premium texture",
                "rendering_strategy": "korean text overlay",
                "analyzer_backend": "rules",
            },
        }
    )


def test_agent_card_advertises_generate_skill() -> None:
    card = build_agent_card(base_url="http://testserver")

    assert card["name"] == "Dessert Ad Studio Agent"
    assert card["url"] == "http://testserver"
    assert card["supportedInterfaces"][0]["protocolBinding"] == "HTTP+JSON"
    assert card["skills"][0]["id"] == "generate_ad_banner"
    assert card["skills"][0]["inputModes"] == ["application/json"]
    assert card["skills"][0]["outputModes"] == ["application/json"]


def test_extract_generation_request_from_data_part() -> None:
    request = extract_generation_request(
        {
            "role": "ROLE_USER",
            "messageId": "msg-1",
            "parts": [{"data": generation_payload()}],
        }
    )

    assert request.product_name == "말차 푸딩"
    assert request.template_hint == "minimal_premium"


def test_task_store_saves_and_returns_task() -> None:
    store = A2ATaskStore()
    task = {
        "id": "task-1",
        "contextId": "context-1",
        "status": {"state": "TASK_STATE_COMPLETED"},
    }

    store.save(task)

    assert store.get("task-1") == task
    assert store.get("missing") is None


def test_task_store_copies_task_on_save() -> None:
    store = A2ATaskStore()
    task = {
        "id": "task-1",
        "contextId": "context-1",
        "status": {"state": "TASK_STATE_COMPLETED"},
    }

    store.save(task)
    task["status"]["state"] = "TASK_STATE_REJECTED"

    assert store.get("task-1") == {
        "id": "task-1",
        "contextId": "context-1",
        "status": {"state": "TASK_STATE_COMPLETED"},
    }


def test_task_store_copies_task_on_get() -> None:
    store = A2ATaskStore()
    task = {
        "id": "task-1",
        "contextId": "context-1",
        "status": {"state": "TASK_STATE_COMPLETED"},
    }
    store.save(task)

    saved = store.get("task-1")
    assert saved is not None
    saved["status"]["state"] = "TASK_STATE_REJECTED"

    assert store.get("task-1") == {
        "id": "task-1",
        "contextId": "context-1",
        "status": {"state": "TASK_STATE_COMPLETED"},
    }


@pytest.mark.parametrize(
    "message",
    [
        {},
        {"parts": "not-a-list"},
    ],
)
def test_extract_generation_request_rejects_missing_or_non_list_parts(message: dict) -> None:
    with pytest.raises(A2AInputError, match="parts must be a non-empty list"):
        extract_generation_request(message)


def test_extract_generation_request_rejects_missing_data_part() -> None:
    with pytest.raises(A2AInputError, match="data part"):
        extract_generation_request({"parts": [{"text": "hello"}]})


def test_extract_generation_request_wraps_invalid_data() -> None:
    with pytest.raises(A2AInputError) as exc_info:
        extract_generation_request({"parts": [{"data": {"product_name": ""}}]})

    assert "campaign_purpose" in str(exc_info.value)


def test_completed_generation_task_accepts_positional_message_id() -> None:
    response = generation_response()

    task = completed_generation_task(response, "msg-1")

    assert task["metadata"]["sourceMessageId"] == "msg-1"
    assert task["artifacts"][0]["parts"][0]["data"] == response.model_dump(mode="json")
