from __future__ import annotations

import argparse
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the Dessert Ad Studio A2A spike.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    card_response = httpx.get(f"{base_url}/.well-known/agent-card.json", timeout=10)
    card_response.raise_for_status()
    card = card_response.json()
    print(f"agent={card['name']} skill={card['skills'][0]['id']}")

    payload = {
        "message": {
            "role": "ROLE_USER",
            "messageId": "smoke-msg-1",
            "parts": [
                {
                    "data": {
                        "campaign_purpose": "new_menu",
                        "product_name": "말차 푸딩",
                        "tone": "clean",
                        "template_hint": "minimal_premium",
                        "price_text": "5,500원",
                        "user_constraints": "깔끔한 프리미엄 느낌",
                    }
                }
            ],
        }
    }
    send_response = httpx.post(
        f"{base_url}/message:send",
        json=payload,
        headers={"content-type": "application/a2a+json"},
        timeout=60,
    )
    send_response.raise_for_status()
    task = send_response.json()["task"]
    print(f"task={task['id']} state={task['status']['state']}")

    task_response = httpx.get(f"{base_url}/tasks/{task['id']}", timeout=10)
    task_response.raise_for_status()
    artifact = task_response.json()["artifacts"][0]["parts"][0]["data"]
    print(f"image_path={artifact['image_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
