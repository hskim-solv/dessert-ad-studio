"""Kubernetes async worker failure-injection smoke for local/test clusters."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter, sleep
from typing import Any, Protocol

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.k8s_live_smoke import (  # noqa: E402
    DEFAULT_ALLOWED_CONTEXT_PATTERN,
    CommandFailedError,
    CommandRunner,
    PortForwardFactory,
    UnsafeKubernetesContextError,
    _assert_safe_context,
    _current_context,
    _kubectl,
    _redacted_command,
    _run_checked,
    _run_command,
    _start_port_forward,
    _write_summary,
)


DEFAULT_SUMMARY_PATH = Path("docs/evidence/k8s-async-failure-smoke-summary.json")


class HttpResponse(Protocol):
    def raise_for_status(self) -> None: ...

    def json(self) -> dict[str, Any]: ...


class HttpClient(Protocol):
    def post(self, url: str, json: dict[str, object]) -> HttpResponse: ...

    def get(self, url: str) -> HttpResponse: ...


SleepFunc = Callable[[float], None]


def run_k8s_async_failure_smoke(
    *,
    namespace: str,
    summary_path: Path = DEFAULT_SUMMARY_PATH,
    context: str | None = None,
    allowed_context_pattern: str = DEFAULT_ALLOWED_CONTEXT_PATTERN,
    allow_unsafe_context: bool = False,
    local_port: int = 18081,
    timeout_seconds: float = 180.0,
    pending_observation_count: int = 3,
    poll_interval_seconds: float = 2.0,
    worker_deployment: str = "deploy/worker",
    runner: CommandRunner | None = None,
    http_client: HttpClient | None = None,
    port_forward_factory: PortForwardFactory | None = None,
    sleep_func: SleepFunc = sleep,
) -> dict[str, object]:
    if pending_observation_count <= 0:
        raise ValueError("pending_observation_count must be greater than 0")
    if poll_interval_seconds < 0:
        raise ValueError("poll_interval_seconds must be non-negative")

    runner = runner or _run_command
    port_forward_factory = port_forward_factory or _start_port_forward
    started = perf_counter()
    commands: list[list[str]] = []
    checks = {
        "safe_context": False,
        "worker_scaled_down": False,
        "api_port_forward": False,
        "job_pending_without_worker": False,
        "worker_restored": False,
        "job_succeeded_after_restore": False,
    }

    active_context = context or _current_context(runner=runner, timeout_seconds=timeout_seconds)
    _assert_safe_context(
        context=active_context,
        allowed_context_pattern=allowed_context_pattern,
        allow_unsafe_context=allow_unsafe_context,
    )
    checks["safe_context"] = True

    client_owner: httpx.Client | None = None
    if http_client is None:
        client_owner = httpx.Client(timeout=10)
        http_client = client_owner

    port_forward = None
    job_id = ""
    initial_status = ""
    final_status = ""
    pending_statuses: list[str] = []
    worker_scaled_down = False
    try:
        _scale_worker(
            active_context=active_context,
            namespace=namespace,
            worker_deployment=worker_deployment,
            replicas=0,
            runner=runner,
            timeout_seconds=timeout_seconds,
            commands=commands,
        )
        worker_scaled_down = True
        checks["worker_scaled_down"] = True

        port_forward_args = _kubectl(
            active_context,
            "-n",
            namespace,
            "port-forward",
            "svc/api",
            f"{local_port}:8000",
        )
        commands.append(port_forward_args)
        port_forward = port_forward_factory(port_forward_args)
        checks["api_port_forward"] = True
        sleep_func(1.0)

        base_url = f"http://127.0.0.1:{local_port}"
        created = _post_generation_job(http_client=http_client, base_url=base_url)
        job_id = str(created["job_id"])
        initial_status = str(created["status"])
        status_url = f"{base_url}{created['status_url']}"

        for _ in range(pending_observation_count):
            status = _get_status(http_client=http_client, status_url=status_url)
            status_value = str(status["status"])
            if status_value in {"succeeded", "failed"}:
                raise RuntimeError(
                    "generation job reached a terminal state while worker replicas were 0"
                )
            pending_statuses.append(status_value)
            if poll_interval_seconds:
                sleep_func(poll_interval_seconds)
        checks["job_pending_without_worker"] = True

        _scale_worker(
            active_context=active_context,
            namespace=namespace,
            worker_deployment=worker_deployment,
            replicas=1,
            runner=runner,
            timeout_seconds=timeout_seconds,
            commands=commands,
        )
        checks["worker_restored"] = True

        final = _wait_for_terminal_status(
            http_client=http_client,
            status_url=status_url,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
            sleep_func=sleep_func,
        )
        final_status = str(final["status"])
        if final_status != "succeeded":
            raise RuntimeError(final.get("error_detail") or "generation job failed after restore")
        checks["job_succeeded_after_restore"] = True
    finally:
        if worker_scaled_down and not checks["worker_restored"]:
            _scale_worker(
                active_context=active_context,
                namespace=namespace,
                worker_deployment=worker_deployment,
                replicas=1,
                runner=runner,
                timeout_seconds=timeout_seconds,
                commands=commands,
            )
        if port_forward is not None:
            port_forward.terminate()
            port_forward.wait(timeout=10)
        if client_owner is not None:
            client_owner.close()

    summary = {
        "k8s_async_failure_smoke": "passed" if checks["job_succeeded_after_restore"] else "failed",
        "context": active_context,
        "namespace": namespace,
        "worker_deployment": worker_deployment,
        "elapsed_ms": round((perf_counter() - started) * 1000),
        "pending_observation_count": pending_observation_count,
        "poll_interval_seconds": poll_interval_seconds,
        "checks": checks,
        "job": {
            "job_id_sha256": _sha256_text(job_id),
            "initial_status": initial_status,
            "pending_statuses": pending_statuses,
            "pending_observations": len(pending_statuses),
            "final_status": final_status,
        },
        "commands": [_redacted_command(command) for command in commands],
        "privacy_boundary": {
            "raw_prompt_committed": False,
            "raw_model_response_committed": False,
            "raw_product_name_committed": False,
            "raw_user_constraints_committed": False,
            "raw_job_id_committed": False,
        },
    }
    _write_summary(summary_path, summary)
    return summary


def _scale_worker(
    *,
    active_context: str,
    namespace: str,
    worker_deployment: str,
    replicas: int,
    runner: CommandRunner,
    timeout_seconds: float,
    commands: list[list[str]],
) -> None:
    _run_checked(
        _kubectl(
            active_context,
            "-n",
            namespace,
            "scale",
            worker_deployment,
            f"--replicas={replicas}",
        ),
        runner=runner,
        timeout_seconds=timeout_seconds,
        commands=commands,
    )
    _run_checked(
        _kubectl(
            active_context,
            "-n",
            namespace,
            "rollout",
            "status",
            worker_deployment,
            f"--timeout={round(timeout_seconds)}s",
        ),
        runner=runner,
        timeout_seconds=timeout_seconds,
        commands=commands,
    )


def _post_generation_job(*, http_client: HttpClient, base_url: str) -> dict[str, Any]:
    response = http_client.post(f"{base_url}/generation-jobs", json=_payload())
    response.raise_for_status()
    return response.json()


def _get_status(*, http_client: HttpClient, status_url: str) -> dict[str, Any]:
    response = http_client.get(status_url)
    response.raise_for_status()
    return response.json()


def _wait_for_terminal_status(
    *,
    http_client: HttpClient,
    status_url: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
    sleep_func: SleepFunc,
) -> dict[str, Any]:
    started = perf_counter()
    while True:
        status = _get_status(http_client=http_client, status_url=status_url)
        if status["status"] in {"succeeded", "failed"}:
            return status
        if perf_counter() - started > timeout_seconds:
            raise TimeoutError(f"generation job did not finish within {timeout_seconds}s")
        if poll_interval_seconds:
            sleep_func(poll_interval_seconds)


def _payload() -> dict[str, object]:
    return {
        "campaign_purpose": "new_menu",
        "product_name": "말차 푸딩",
        "tone": "clean",
        "template_hint": "minimal_premium",
        "price_text": "5,500원",
        "user_constraints": "worker failure-injection smoke",
    }


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a Kubernetes async worker failure-injection smoke.",
        allow_abbrev=False,
    )
    parser.add_argument("--namespace", default="dessert-ad-studio")
    parser.add_argument("--context")
    parser.add_argument("--allowed-context-pattern", default=DEFAULT_ALLOWED_CONTEXT_PATTERN)
    parser.add_argument("--allow-unsafe-context", action="store_true")
    parser.add_argument("--local-port", type=int, default=18081)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--pending-observation-count", type=int, default=3)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--worker-deployment", default="deploy/worker")
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY_PATH)
    args = parser.parse_args()

    try:
        summary = run_k8s_async_failure_smoke(
            namespace=args.namespace,
            summary_path=args.summary,
            context=args.context,
            allowed_context_pattern=args.allowed_context_pattern,
            allow_unsafe_context=args.allow_unsafe_context,
            local_port=args.local_port,
            timeout_seconds=args.timeout,
            pending_observation_count=args.pending_observation_count,
            poll_interval_seconds=args.poll_interval,
            worker_deployment=args.worker_deployment,
        )
    except (
        UnsafeKubernetesContextError,
        CommandFailedError,
        RuntimeError,
        TimeoutError,
        subprocess.TimeoutExpired,
    ) as exc:
        print(f"k8s_async_failure_smoke=failed error={exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["k8s_async_failure_smoke"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
