"""Fail-closed Kubernetes live smoke for local/test clusters.

This script can apply the Kustomize base to an already selected Kubernetes
context, wait for core deployments, port-forward the API service, and run the
existing API smoke. It refuses unknown/non-local contexts unless explicitly
overridden.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys
from time import perf_counter, sleep
from typing import Protocol

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.api_smoke import run_smoke as run_api_smoke  # noqa: E402


DEFAULT_ALLOWED_CONTEXT_PATTERN = r"^(kind-.+|minikube|docker-desktop|rancher-desktop|k3d-.+)$"
DEFAULT_SUMMARY_PATH = Path("docs/evidence/k8s-live-smoke-summary.json")


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


class PortForwardProcess(Protocol):
    def terminate(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...


CommandRunner = Callable[[list[str], float], CommandResult]
PortForwardFactory = Callable[[list[str]], PortForwardProcess]
ApiSmoke = Callable[..., None]


class UnsafeKubernetesContextError(RuntimeError):
    pass


class CommandFailedError(RuntimeError):
    pass


def run_k8s_live_smoke(
    *,
    kustomize_path: Path,
    namespace: str,
    summary_path: Path = DEFAULT_SUMMARY_PATH,
    context: str | None = None,
    allowed_context_pattern: str = DEFAULT_ALLOWED_CONTEXT_PATTERN,
    allow_unsafe_context: bool = False,
    local_port: int = 18080,
    timeout_seconds: float = 180.0,
    skip_generate: bool = False,
    cleanup: bool = False,
    runner: CommandRunner | None = None,
    api_smoke: ApiSmoke = run_api_smoke,
    port_forward_factory: PortForwardFactory | None = None,
) -> dict[str, object]:
    runner = runner or _run_command
    port_forward_factory = port_forward_factory or _start_port_forward
    started = perf_counter()
    commands: list[list[str]] = []
    checks = {
        "safe_context": False,
        "kubectl_apply": False,
        "rollout_api": False,
        "rollout_app": False,
        "rollout_triton": False,
        "api_port_forward": False,
        "api_smoke": False,
        "cleanup": False,
    }

    active_context = context or _current_context(runner=runner, timeout_seconds=timeout_seconds)
    _assert_safe_context(
        context=active_context,
        allowed_context_pattern=allowed_context_pattern,
        allow_unsafe_context=allow_unsafe_context,
    )
    checks["safe_context"] = True

    try:
        _run_checked(
            _kubectl(active_context, "apply", "-k", str(kustomize_path)),
            runner=runner,
            timeout_seconds=timeout_seconds,
            commands=commands,
        )
        checks["kubectl_apply"] = True

        for deployment, check_name in (
            ("deploy/api", "rollout_api"),
            ("deploy/app", "rollout_app"),
            ("deploy/triton", "rollout_triton"),
        ):
            _run_checked(
                _kubectl(
                    active_context,
                    "-n",
                    namespace,
                    "rollout",
                    "status",
                    deployment,
                    f"--timeout={round(timeout_seconds)}s",
                ),
                runner=runner,
                timeout_seconds=timeout_seconds,
                commands=commands,
            )
            checks[check_name] = True

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
        sleep(1.0)
        try:
            api_smoke(
                base_url=f"http://127.0.0.1:{local_port}",
                timeout_seconds=timeout_seconds,
                skip_generate=skip_generate,
            )
            checks["api_smoke"] = True
        finally:
            port_forward.terminate()
            port_forward.wait(timeout=10)
    finally:
        if cleanup:
            _run_checked(
                _kubectl(active_context, "delete", "-k", str(kustomize_path), "--ignore-not-found"),
                runner=runner,
                timeout_seconds=timeout_seconds,
                commands=commands,
            )
            checks["cleanup"] = True

    summary = {
        "k8s_live_smoke": "passed" if checks["api_smoke"] else "failed",
        "context": active_context,
        "namespace": namespace,
        "kustomize_path": str(kustomize_path),
        "elapsed_ms": round((perf_counter() - started) * 1000),
        "skip_generate": skip_generate,
        "cleanup_requested": cleanup,
        "checks": checks,
        "commands": [_redacted_command(command) for command in commands],
        "privacy_boundary": {
            "secrets_committed": False,
            "raw_prompt_committed": False,
            "raw_model_response_committed": False,
            "reference_image_committed": False,
        },
    }
    _write_summary(summary_path, summary)
    return summary


def _current_context(*, runner: CommandRunner, timeout_seconds: float) -> str:
    result = _run_checked(
        ["kubectl", "config", "current-context"],
        runner=runner,
        timeout_seconds=timeout_seconds,
        commands=[],
    )
    context = result.stdout.strip()
    if not context:
        raise UnsafeKubernetesContextError(
            "kubectl current-context가 비어 있습니다. kind/minikube/docker-desktop 같은 "
            "로컬 context를 먼저 준비하세요."
        )
    return context


def _assert_safe_context(
    *,
    context: str,
    allowed_context_pattern: str,
    allow_unsafe_context: bool,
) -> None:
    if allow_unsafe_context:
        return
    if re.search(allowed_context_pattern, context):
        return
    raise UnsafeKubernetesContextError(
        f"Refusing to apply Kubernetes manifests to context '{context}'. "
        "Use a local/test context such as kind-*, minikube, docker-desktop, "
        "rancher-desktop, or pass --allow-unsafe-context intentionally."
    )


def _kubectl(context: str, *args: str) -> list[str]:
    return ["kubectl", "--context", context, *args]


def _run_checked(
    args: list[str],
    *,
    runner: CommandRunner,
    timeout_seconds: float,
    commands: list[list[str]],
) -> CommandResult:
    commands.append(args)
    result = runner(args, timeout_seconds)
    if result.returncode != 0:
        raise CommandFailedError(
            f"command failed ({result.returncode}): {' '.join(args)}\n"
            f"stderr: {result.stderr.strip()}"
        )
    return result


def _run_command(args: list[str], timeout_seconds: float) -> CommandResult:
    completed = subprocess.run(
        args,
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    return CommandResult(
        args=args,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _start_port_forward(args: list[str]) -> PortForwardProcess:
    return subprocess.Popen(  # noqa: S603 - args are fixed kubectl tokens built above.
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def _redacted_command(command: list[str]) -> list[str]:
    return ["***" if "KEY" in token or "SECRET" in token else token for token in command]


def _write_summary(path: Path, summary: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a fail-closed Kubernetes live smoke against a local/test context.",
        allow_abbrev=False,
    )
    parser.add_argument("--kustomize-path", type=Path, default=Path("deploy/k8s/base"))
    parser.add_argument("--namespace", default="dessert-ad-studio")
    parser.add_argument("--context")
    parser.add_argument("--allowed-context-pattern", default=DEFAULT_ALLOWED_CONTEXT_PATTERN)
    parser.add_argument("--allow-unsafe-context", action="store_true")
    parser.add_argument("--local-port", type=int, default=18080)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--skip-generate", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY_PATH)
    args = parser.parse_args()

    try:
        summary = run_k8s_live_smoke(
            kustomize_path=args.kustomize_path,
            namespace=args.namespace,
            summary_path=args.summary,
            context=args.context,
            allowed_context_pattern=args.allowed_context_pattern,
            allow_unsafe_context=args.allow_unsafe_context,
            local_port=args.local_port,
            timeout_seconds=args.timeout,
            skip_generate=args.skip_generate,
            cleanup=args.cleanup,
        )
    except (
        UnsafeKubernetesContextError,
        CommandFailedError,
        RuntimeError,
        subprocess.TimeoutExpired,
    ) as exc:
        print(f"k8s_live_smoke=failed error={exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["k8s_live_smoke"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
