from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ci_runs_agentic_rag_eval_guardrail_gate() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "Agentic RAG eval guardrail gate" in workflow
    assert "python scripts/agentic_rag_eval_guardrail.py" in workflow
    assert "--output /tmp/agentic-rag-eval-guardrail-summary.json" in workflow
