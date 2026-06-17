from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ci_runs_agentic_rag_eval_guardrail_gate() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "Agentic RAG eval guardrail gate" in workflow
    assert "python scripts/agentic_rag_eval_guardrail.py" in workflow
    assert "--output /tmp/agentic-rag-eval-guardrail-summary.json" in workflow


def test_ci_runs_promptfoo_package_gate() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "Agentic RAG promptfoo package gate" in workflow
    assert "npm ci --no-audit --no-fund" in workflow
    assert "scripts/agentic_rag_promptfoo_package_smoke.py" in workflow
    assert "--summary-output /tmp/agentic-rag-promptfoo-package-summary.json" in workflow
