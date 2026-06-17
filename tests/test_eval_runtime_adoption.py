from __future__ import annotations

from pathlib import Path


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
    assert "bash scripts/run_promptfoo_agentic_rag_provider.sh" in config
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
    assert "promptfoo eval -c evals/promptfoo/agentic-rag.yaml" in evidence
    assert "Ragas live gate" in evidence
    assert "0016-agentic-rag-eval-runtime" in final_outcome
