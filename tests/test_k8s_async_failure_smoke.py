from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.k8s_live_smoke import CommandResult, UnsafeKubernetesContextError


class RecordingRunner:
    def __init__(self, *, context: str) -> None:
        self.context = context
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], timeout_seconds: float) -> CommandResult:
        self.calls.append(args)
        if args == ["kubectl", "config", "current-context"]:
            return CommandResult(args=args, returncode=0, stdout=self.context, stderr="")
        return CommandResult(args=args, returncode=0, stdout="ok", stderr="")


class FakePortForward:
    def __init__(self, args: list[str]) -> None:
        self.args = args
        self.terminated = False
        self.waited = False

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        self.waited = True
        return 0


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload


class FakeHttpClient:
    def __init__(self) -> None:
        self.posted_payloads: list[dict[str, object]] = []
        self.statuses = [
            {"status": "pending"},
            {"status": "pending"},
            {"status": "pending"},
            {
                "status": "succeeded",
                "response_summary": {"copy_options_count": 3},
            },
        ]

    def post(self, url: str, json: dict[str, object]) -> FakeResponse:
        self.posted_payloads.append(json)
        return FakeResponse(
            {
                "job_id": "job-sensitive-id",
                "status": "pending",
                "status_url": "/generation-jobs/job-sensitive-id",
            }
        )

    def get(self, url: str) -> FakeResponse:
        return FakeResponse(self.statuses.pop(0))


def test_run_k8s_async_failure_smoke_scales_worker_down_then_restores(
    tmp_path: Path,
) -> None:
    from scripts.k8s_async_failure_smoke import run_k8s_async_failure_smoke

    runner = RecordingRunner(context="kind-dessert-ad-studio")
    port_forwards: list[FakePortForward] = []
    http_client = FakeHttpClient()

    def make_port_forward(args: list[str]) -> FakePortForward:
        port_forward = FakePortForward(args)
        port_forwards.append(port_forward)
        return port_forward

    summary = run_k8s_async_failure_smoke(
        namespace="dessert-ad-studio",
        summary_path=tmp_path / "summary.json",
        runner=runner,
        http_client=http_client,
        port_forward_factory=make_port_forward,
        local_port=18081,
        pending_observation_count=3,
        poll_interval_seconds=0,
    )

    assert summary["k8s_async_failure_smoke"] == "passed"
    assert summary["checks"] == {
        "safe_context": True,
        "worker_scaled_down": True,
        "api_port_forward": True,
        "job_pending_without_worker": True,
        "worker_restored": True,
        "job_succeeded_after_restore": True,
    }
    assert summary["job"]["initial_status"] == "pending"
    assert summary["job"]["pending_observations"] == 3
    assert summary["job"]["final_status"] == "succeeded"
    assert summary["job"]["job_id_sha256"]
    assert "job-sensitive-id" not in json.dumps(summary, ensure_ascii=False)
    assert port_forwards and port_forwards[0].terminated and port_forwards[0].waited
    assert any("scale" in call and "--replicas=0" in call for call in runner.calls)
    assert any("scale" in call and "--replicas=1" in call for call in runner.calls)

    persisted = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert persisted == summary


def test_run_k8s_async_failure_smoke_rejects_unsafe_context(tmp_path: Path) -> None:
    from scripts.k8s_async_failure_smoke import run_k8s_async_failure_smoke

    runner = RecordingRunner(context="prod-gke-cluster")

    with pytest.raises(UnsafeKubernetesContextError):
        run_k8s_async_failure_smoke(
            namespace="dessert-ad-studio",
            summary_path=tmp_path / "summary.json",
            runner=runner,
            http_client=FakeHttpClient(),
            port_forward_factory=lambda _: FakePortForward([]),
        )

    assert not any("scale" in call for call in runner.calls)


def test_k8s_async_failure_smoke_script_help_runs_from_repo_root() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/k8s_async_failure_smoke.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Run a Kubernetes async worker failure-injection smoke" in result.stdout
