from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_rag_chunking_comparison_script_writes_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "rag-chunking-comparison-results.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/eval_rag_chunking_strategies.py",
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

    assert summary["rag_chunking_comparison"] == "passed"
    assert summary["scope"] == "offline_marketing_context_chunking_no_paid_api_call"
    assert summary["document_count"] >= 5
    assert summary["eval_case_count"] >= 10
    assert summary["embedding_backend"] == "deterministic_local_hash_embedding"
    assert summary["selected_strategy"] == "field_aware"
    assert len(summary["strategies"]) >= 2
    assert {strategy["name"] for strategy in summary["strategies"]} >= {
        "whole_document",
        "field_aware",
    }
    assert summary["selected_metrics"]["category_hit_rate"] >= 0.9
    assert summary["selected_metrics"]["required_category_hit_rate"] == 1.0
    assert summary["selected_metrics"]["average_top_k_chunks"] <= 4
    assert summary["raw_inputs_committed"] is False

    serialized = json.dumps(summary, ensure_ascii=False)
    for raw_value in ["딸기 크림 크루아상", "인스타그램 피드", "말차 푸딩"]:
        assert raw_value not in serialized
