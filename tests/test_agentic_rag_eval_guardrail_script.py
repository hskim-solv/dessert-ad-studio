from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_agentic_rag_eval_guardrail_script_writes_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "agentic-rag-eval-guardrail-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/agentic_rag_eval_guardrail.py",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["agentic_rag_eval_guardrail"] == "passed"
    assert summary["scope"] == "local_ragas_promptfoo_compatible_no_paid_api_call"
    assert summary["golden_dataset"]["case_count"] >= 12
    assert summary["ragas_compatible_metrics"] == {
        "faithfulness": 1.0,
        "answer_relevancy": 1.0,
        "context_precision": 1.0,
        "context_recall": 1.0,
    }
    assert summary["promptfoo_regression"]["passed"] is True
    assert summary["promptfoo_regression"]["case_count"] == summary["golden_dataset"]["case_count"]
    assert summary["prompt_injection"]["passed"] is True
    assert summary["tool_budget"]["passed"] is True
    assert summary["tool_budget"]["max_tool_calls"] == 4
    assert summary["tool_budget"]["unexpected_tools"] == []
    assert summary["raw_inputs_committed"] is False

    serialized = json.dumps(summary, ensure_ascii=False)
    for raw_value in [
        "비공개 말차 푸딩",
        "VIP 고객에게만 보일 문구",
        "ignore previous instructions",
        "system prompt",
        "secret-reference.png",
        "c2VjcmV0LWltYWdlLWJ5dGVz",
    ]:
        assert raw_value not in serialized
