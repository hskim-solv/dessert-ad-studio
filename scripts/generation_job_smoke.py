from __future__ import annotations

import os
import time
from typing import Any

import httpx


def _payload() -> dict[str, Any]:
    return {
        "campaign_purpose": "new_menu",
        "product_name": "말차 푸딩",
        "tone": "clean",
        "template_hint": "minimal_premium",
        "price_text": "5,500원",
        "user_constraints": "깔끔한 프리미엄 느낌",
    }


def main() -> None:
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
    timeout_seconds = int(os.getenv("GENERATION_JOB_SMOKE_TIMEOUT_SECONDS", "60"))
    started = time.monotonic()

    with httpx.Client(timeout=10) as client:
        create_response = client.post(f"{base_url}/generation-jobs", json=_payload())
        create_response.raise_for_status()
        created = create_response.json()
        status_url = f"{base_url}{created['status_url']}"

        while True:
            status_response = client.get(status_url)
            status_response.raise_for_status()
            status = status_response.json()
            if status["status"] in {"succeeded", "failed"}:
                print(status)
                if status["status"] != "succeeded":
                    raise RuntimeError(status.get("error_detail") or "generation job failed")
                return
            if time.monotonic() - started > timeout_seconds:
                raise TimeoutError(f"generation job did not finish within {timeout_seconds}s")
            time.sleep(1)


if __name__ == "__main__":
    main()
