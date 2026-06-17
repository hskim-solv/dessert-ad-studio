from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

import scripts.k8s_live_smoke as k8s_live_smoke
from scripts.k8s_live_smoke import (
    CommandResult,
    UnsafeKubernetesContextError,
    run_k8s_live_smoke,
)


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


def test_run_k8s_live_smoke_rejects_unsafe_context_before_apply(tmp_path: Path) -> None:
    runner = RecordingRunner(context="prod-gke-cluster")

    with pytest.raises(UnsafeKubernetesContextError):
        run_k8s_live_smoke(
            kustomize_path=Path("deploy/k8s/base"),
            namespace="dessert-ad-studio",
            summary_path=tmp_path / "summary.json",
            runner=runner,
            api_smoke=lambda **_: None,
            port_forward_factory=lambda _: FakePortForward([]),
        )

    assert ["kubectl", "config", "current-context"] in runner.calls
    assert not any("apply" in call for call in runner.calls)


def test_run_k8s_live_smoke_applies_local_context_and_writes_redacted_summary(
    tmp_path: Path,
) -> None:
    runner = RecordingRunner(context="kind-dessert-ad-studio")
    port_forwards: list[FakePortForward] = []
    api_smokes: list[dict[str, object]] = []

    def make_port_forward(args: list[str]) -> FakePortForward:
        port_forward = FakePortForward(args)
        port_forwards.append(port_forward)
        return port_forward

    def record_api_smoke(**kwargs: object) -> None:
        api_smokes.append(kwargs)

    summary = run_k8s_live_smoke(
        kustomize_path=Path("deploy/k8s/base"),
        namespace="dessert-ad-studio",
        summary_path=tmp_path / "summary.json",
        runner=runner,
        api_smoke=record_api_smoke,
        port_forward_factory=make_port_forward,
        local_port=18080,
        skip_generate=False,
    )

    assert summary["k8s_live_smoke"] == "passed"
    assert summary["context"] == "kind-dessert-ad-studio"
    assert summary["checks"]["kubectl_apply"] is True
    assert summary["checks"]["api_smoke"] is True
    assert any(
        call[:4] == ["kubectl", "--context", "kind-dessert-ad-studio", "apply"]
        for call in runner.calls
    )
    assert any("deploy/api" in call for call in runner.calls)
    assert any("deploy/app" in call for call in runner.calls)
    assert any("deploy/triton" in call for call in runner.calls)
    assert port_forwards and port_forwards[0].terminated and port_forwards[0].waited
    assert api_smokes == [
        {
            "base_url": "http://127.0.0.1:18080",
            "timeout_seconds": 180.0,
            "skip_generate": False,
        }
    ]

    persisted = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    serialized = json.dumps(persisted, ensure_ascii=False)
    assert persisted == summary
    assert "OPENAI_API_KEY" not in serialized
    assert "reference_image_b64" not in serialized
    assert '"raw_prompt":' not in serialized


def test_k8s_live_smoke_script_help_runs_from_repo_root() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/k8s_live_smoke.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Run a fail-closed Kubernetes live smoke" in result.stdout


def test_main_reports_api_smoke_runtime_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_smoke(**_: object) -> dict[str, object]:
        raise RuntimeError("api smoke failed")

    monkeypatch.setattr(k8s_live_smoke, "run_k8s_live_smoke", fail_smoke)
    monkeypatch.setattr(sys, "argv", ["k8s_live_smoke.py"])

    assert k8s_live_smoke.main() == 1
    assert "k8s_live_smoke=failed error=api smoke failed" in capsys.readouterr().err
