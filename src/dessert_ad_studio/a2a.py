from __future__ import annotations

from copy import deepcopy
from threading import Lock
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from dessert_ad_studio.schemas import GenerationRequest, GenerationResponse

TASK_COMPLETED = "TASK_STATE_COMPLETED"
TASK_REJECTED = "TASK_STATE_REJECTED"
_JSON_MODE = "application/json"
_GENERATE_SKILL_ID = "generate_ad_banner"


class A2AInputError(ValueError):
    pass


class A2ATaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def save(self, task: dict[str, Any]) -> None:
        with self._lock:
            self._tasks[task["id"]] = deepcopy(task)

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            task = self._tasks.get(task_id)
            return deepcopy(task) if task is not None else None


def build_agent_card(base_url: str) -> dict[str, Any]:
    return {
        "name": "Dessert Ad Studio Agent",
        "url": base_url.rstrip("/"),
        "version": "0.1.0",
        "protocolVersion": "1.0",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "extendedAgentCard": False,
        },
        "defaultInputModes": [_JSON_MODE],
        "defaultOutputModes": [_JSON_MODE],
        "supportedInterfaces": [
            {
                "protocolBinding": "HTTP+JSON",
                "url": base_url.rstrip("/"),
                "protocolVersion": "1.0",
            }
        ],
        "skills": [
            {
                "id": _GENERATE_SKILL_ID,
                "name": "Generate ad banner",
                "description": "Generate a dessert cafe ad banner from a structured JSON request.",
                "tags": ["dessert", "advertising", "banner-generation"],
                "inputModes": [_JSON_MODE],
                "outputModes": [_JSON_MODE],
            }
        ],
    }


def extract_generation_request(message: dict[str, Any]) -> GenerationRequest:
    parts = message.get("parts")
    if not isinstance(parts, list) or not parts:
        raise A2AInputError("A2A message parts must be a non-empty list.")

    for part in parts:
        if not isinstance(part, dict):
            continue

        data = part.get("data")
        if not isinstance(data, dict):
            continue

        try:
            return GenerationRequest.model_validate(data)
        except ValidationError as exc:
            raise A2AInputError(str(exc)) from exc

    raise A2AInputError("A2A message must include a data part with a JSON object payload.")


def completed_generation_task(
    response: GenerationResponse,
    message_id: str | None,
    context_id: str | None = None,
) -> dict[str, Any]:
    task_id = f"task-{uuid4()}"
    return {
        "id": task_id,
        "contextId": context_id or task_id,
        "status": {
            "state": TASK_COMPLETED,
            "message": {
                "role": "ROLE_AGENT",
                "messageId": f"msg-{uuid4()}",
                "parts": [{"text": "Dessert ad banner generation completed."}],
            },
        },
        "metadata": {
            "sourceMessageId": message_id,
            "skillId": _GENERATE_SKILL_ID,
        },
        "artifacts": [
            {
                "artifactId": f"artifact-{uuid4()}",
                "parts": [{"data": response.model_dump(mode="json")}],
            }
        ],
    }
