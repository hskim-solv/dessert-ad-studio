from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_agentic_rag_eval_runtime_adr_records_actual_tool_adoption() -> None:
    adr = (ROOT / "docs" / "adr" / "0016-agentic-rag-eval-runtime.md").read_text(encoding="utf-8")

    assert "Ragas" in adr
    assert "promptfoo" in adr
    assert "선택 기준" in adr
    assert "후보 비교" in adr
    assert "오프라인 promptfoo 회귀 게이트 + 선택적 Ragas live 게이트" in adr
    assert "paid API" in adr
    assert "재평가 트리거" in adr


def test_promptfoo_config_runs_agentic_rag_guardrail_script_offline() -> None:
    config = (ROOT / "evals" / "promptfoo" / "agentic-rag.yaml").read_text(encoding="utf-8")

    assert "$schema=https://promptfoo.dev/config-schema.json" in config
    assert "exec:" in config
    assert "bash ../../scripts/run_promptfoo_agentic_rag_provider.sh" in config
    assert "agentic_rag_eval_guardrail" in config
    assert "prompt_injection.passed" in config
    assert "raw_inputs_committed" in config


def test_eval_evidence_lists_actual_package_upgrade_path() -> None:
    evidence = (ROOT / "docs" / "evidence" / "agentic-rag-eval-guardrail.md").read_text(
        encoding="utf-8"
    )
    final_outcome = (ROOT / "docs" / "reference" / "dessert-ad-studio-final-outcome.md").read_text(
        encoding="utf-8"
    )

    assert "docs/adr/0016-agentic-rag-eval-runtime.md" in evidence
    assert "promptfoo eval" in evidence
    assert "-c evals/promptfoo/agentic-rag.yaml" in evidence
    assert "Ragas live gate" in evidence
    assert "0016-agentic-rag-eval-runtime" in final_outcome


def test_promptfoo_package_smoke_writes_redacted_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "agentic-rag-promptfoo-package-summary.json"
    results_path = tmp_path / "agentic-rag-promptfoo-results.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/agentic_rag_promptfoo_package_smoke.py",
            "--summary-output",
            str(output_path),
            "--results-output",
            str(results_path),
            "--timeout-seconds",
            "1",
            "--dry-run-command",
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = __import__("json").loads(output_path.read_text(encoding="utf-8"))

    assert summary["agentic_rag_promptfoo_package_smoke"] == "passed"
    assert summary["scope"] == "local_promptfoo_package_execution_no_paid_api_call"
    assert summary["promptfoo_package"] == "promptfoo"
    assert summary["promptfoo_version"] == "0.121.17"
    assert summary["telemetry_disabled"] is True
    assert summary["cache_disabled"] is True
    assert summary["progress_bar_disabled"] is True
    assert summary["table_disabled"] is True
    assert summary["paid_api_call_count"] == 0
    assert summary["raw_inputs_committed"] is False
    assert any("promptfoo" in part for part in summary["command"])
    assert not any(part.startswith(str(ROOT)) for part in summary["command"])
    assert "--no-cache" in summary["command"]
    assert "--no-progress-bar" in summary["command"]
    assert "--no-table" in summary["command"]
    assert str(results_path) in summary["command"]


def test_promptfoo_provider_script_runs_from_config_base_path() -> None:
    completed = subprocess.run(
        [
            "bash",
            "../../scripts/run_promptfoo_agentic_rag_provider.sh",
            "agentic-rag-offline-eval",
            "{}",
            "{}",
        ],
        cwd=ROOT / "evals" / "promptfoo",
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = __import__("json").loads(completed.stdout)
    assert summary["agentic_rag_eval_guardrail"] == "passed"
    assert summary["raw_inputs_committed"] is False
