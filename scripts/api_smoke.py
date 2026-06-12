from __future__ import annotations

import argparse
import sys
import time
from typing import Any

import httpx


def _wait_for_api(client: httpx.Client, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = client.get("/livez")
            if response.status_code == 200 and response.json().get("status") == "alive":
                return
        except Exception as exc:  # pragma: no cover - exercised by CI shell smoke
            last_error = exc
        time.sleep(0.25)

    raise RuntimeError(f"API did not become live within {timeout_seconds:.1f}s: {last_error}")


def _assert_json_status(response: httpx.Response, expected: int = 200) -> dict[str, Any]:
    if response.status_code != expected:
        raise RuntimeError(f"{response.request.method} {response.request.url} -> {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"{response.request.url} did not return a JSON object")
    return payload


def run_smoke(base_url: str, timeout_seconds: float, skip_generate: bool) -> None:
    with httpx.Client(base_url=base_url, timeout=timeout_seconds) as client:
        _wait_for_api(client, timeout_seconds)

        livez = _assert_json_status(client.get("/livez"))
        if livez.get("status") != "alive":
            raise RuntimeError(f"unexpected livez payload: {livez}")

        readyz = _assert_json_status(client.get("/readyz"))
        if readyz.get("status") != "ready":
            raise RuntimeError(f"unexpected readyz payload: {readyz}")

        metrics = client.get("/metrics")
        if metrics.status_code != 200 or "dessert_ad_studio_http_requests_total" not in metrics.text:
            raise RuntimeError("metrics endpoint did not expose Prometheus text")

        if not skip_generate:
            payload = {
                "campaign_purpose": "new_menu",
                "product_name": "Matcha pudding",
                "tone": "clean",
                "template_hint": "minimal_premium",
                "price_text": "5500 KRW",
                "user_constraints": "Clean premium cafe banner",
            }
            generated = _assert_json_status(client.post("/generate", json=payload))
            if "product_analysis" not in generated or not generated.get("image_path"):
                raise RuntimeError(f"unexpected generate payload: {generated}")

    print(f"API smoke passed: {base_url}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke check the Dessert Ad Studio API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--skip-generate", action="store_true")
    args = parser.parse_args()

    try:
        run_smoke(args.base_url, args.timeout, args.skip_generate)
    except Exception as exc:
        print(f"API smoke failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
