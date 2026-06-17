from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any


DEFAULT_REPORT_OUTPUT = Path("docs/evidence/agentic-rag-eval-report.md")
DEFAULT_SUMMARY_OUTPUT = Path("docs/evidence/agentic-rag-eval-report-summary.json")
EVAL_GUARDRAIL_SUMMARY = Path("docs/evidence/agentic-rag-eval-guardrail-summary.json")
KEYWORD_RETRIEVAL_SUMMARY = Path("docs/evidence/rag-baseline-results.json")
CHUNKING_SUMMARY = Path("docs/evidence/rag-chunking-comparison-results.json")
PGVECTOR_SUMMARY = Path("docs/evidence/pgvector-baseline-results.json")
PROMPTFOO_SUMMARY = Path("docs/evidence/agentic-rag-promptfoo-package-summary.json")


def build_agentic_rag_eval_report_summary(*, evidence_date: str) -> dict[str, Any]:
    eval_guardrail = _read_json(EVAL_GUARDRAIL_SUMMARY)
    keyword = _read_json(KEYWORD_RETRIEVAL_SUMMARY)
    chunking = _read_json(CHUNKING_SUMMARY)
    pgvector = _read_json(PGVECTOR_SUMMARY)
    promptfoo = _read_json(PROMPTFOO_SUMMARY)

    ragas_metrics = eval_guardrail["ragas_compatible_metrics"]
    prompt_injection = eval_guardrail["prompt_injection"]
    tool_budget = eval_guardrail["tool_budget"]
    promptfoo_results = promptfoo["promptfoo_results"]

    passed = (
        eval_guardrail["agentic_rag_eval_guardrail"] == "passed"
        and keyword["passed"] is True
        and chunking["rag_chunking_comparison"] == "passed"
        and pgvector["passed"] is True
        and promptfoo["promptfoo_eval_passed"] is True
        and prompt_injection["passed"] is True
        and tool_budget["passed"] is True
        and eval_guardrail["raw_inputs_committed"] is False
        and chunking["raw_inputs_committed"] is False
        and promptfoo["raw_inputs_committed"] is False
    )

    return {
        "agentic_rag_eval_report": "passed" if passed else "failed",
        "scope": "offline_reviewer_eval_report_no_paid_api_call",
        "evidence_date": evidence_date,
        "source_artifacts": [
            str(EVAL_GUARDRAIL_SUMMARY),
            str(KEYWORD_RETRIEVAL_SUMMARY),
            str(CHUNKING_SUMMARY),
            str(PGVECTOR_SUMMARY),
            str(PROMPTFOO_SUMMARY),
        ],
        "golden_eval": {
            "dataset": eval_guardrail["golden_dataset"]["name"],
            "case_count": eval_guardrail["golden_dataset"]["case_count"],
            "faithfulness": ragas_metrics["faithfulness"],
            "answer_relevancy": ragas_metrics["answer_relevancy"],
            "context_precision": ragas_metrics["context_precision"],
            "context_recall": ragas_metrics["context_recall"],
        },
        "retrieval": {
            "keyword_case_count": keyword["sample_count"],
            "keyword_category_hit_rate": keyword["average_category_hit_rate"],
            "keyword_precision": keyword["average_category_precision"],
            "required_category_hit_rate": keyword["required_category_hit_rate"],
            "chunking_eval_case_count": chunking["eval_case_count"],
            "chunking_selected_strategy": chunking["selected_strategy"],
            "chunking_category_hit_rate": chunking["selected_metrics"]["category_hit_rate"],
            "chunking_required_category_hit_rate": chunking["selected_metrics"][
                "required_category_hit_rate"
            ],
            "pgvector_case_count": pgvector["sample_count"],
            "pgvector_category_hit_rate": pgvector["average_category_hit_rate"],
            "pgvector_precision": pgvector["average_category_precision"],
        },
        "promptfoo": {
            "passed": promptfoo["promptfoo_eval_passed"],
            "package": promptfoo["promptfoo_package"],
            "version": promptfoo["promptfoo_version"],
            "assert_pass_count": promptfoo_results["assert_pass_count"],
            "assert_fail_count": promptfoo_results["assert_fail_count"],
            "errors": promptfoo_results["errors"],
            "failures": promptfoo_results["failures"],
            "token_usage_total": promptfoo_results["token_usage_total"],
            "cost": promptfoo_results["cost"],
        },
        "guardrails": {
            "prompt_injection_blocked": prompt_injection["blocked_before_worker"],
            "tool_budget_passed": tool_budget["passed"],
            "max_tool_calls": tool_budget["max_tool_calls"],
            "planned_tool_count": tool_budget["planned_tool_count"],
            "unexpected_tools": tool_budget["unexpected_tools"],
            "raw_inputs_absent": not eval_guardrail["raw_inputs_committed"],
        },
        "limits": {
            "ragas_live_gate": "pending_paid_api_approval",
            "live_web_search": "pending_runtime_security_policy",
            "local_sql_runtime_policy": "first_gate_complete",
            "production_db_access_audit": "pending_runtime_security_policy",
            "production_mcp_transport_auth": "pending_runtime_security_policy",
        },
        "privacy_boundary": {
            "raw_inputs_committed": False,
            "paid_api_call_count": promptfoo["paid_api_call_count"],
        },
    }


def render_agentic_rag_eval_report(summary: dict[str, Any]) -> str:
    golden = summary["golden_eval"]
    retrieval = summary["retrieval"]
    promptfoo = summary["promptfoo"]
    guardrails = summary["guardrails"]
    source_rows = "\n".join(f"- `{path}`" for path in summary["source_artifacts"])
    return f"""# Agentic RAG Eval Report

Date: {summary["evidence_date"]}

This report consolidates the offline Agentic RAG evaluation artifacts for
reviewers. It does not call paid APIs, live web search, production databases, or
external MCP transports.

## Result

- `agentic_rag_eval_report`: `{summary["agentic_rag_eval_report"]}`
- `scope`: `{summary["scope"]}`
- Golden dataset: `{golden["dataset"]}`, `{golden["case_count"]}` cases
- Faithfulness: `{golden["faithfulness"]}`
- Answer relevancy: `{golden["answer_relevancy"]}`
- Context precision: `{golden["context_precision"]}`
- Context recall: `{golden["context_recall"]}`

## Retrieval

| Gate | Result |
|---|---|
| Keyword retrieval | category hit `{retrieval["keyword_category_hit_rate"]}`, precision `{retrieval["keyword_precision"]}`, required safety hit `{retrieval["required_category_hit_rate"]}` |
| Chunking comparison | selected `{retrieval["chunking_selected_strategy"]}`, category hit `{retrieval["chunking_category_hit_rate"]}`, required safety hit `{retrieval["chunking_required_category_hit_rate"]}` |
| pgvector hybrid | category hit `{retrieval["pgvector_category_hit_rate"]}`, precision `{retrieval["pgvector_precision"]}` |

## Regression And Guardrails

- promptfoo package gate: `{promptfoo["passed"]}` with
  `{promptfoo["assert_pass_count"]}` assertions passed,
  `{promptfoo["assert_fail_count"]}` assertions failed, `{promptfoo["errors"]}`
  errors, `{promptfoo["failures"]}` failures, token usage
  `{promptfoo["token_usage_total"]}`, cost `{promptfoo["cost"]}`
- Prompt injection blocked before worker: `{guardrails["prompt_injection_blocked"]}`
- Tool budget passed: `{guardrails["tool_budget_passed"]}` with max tool calls
  `{guardrails["max_tool_calls"]}` and `{guardrails["planned_tool_count"]}`
  planned tools
- Unexpected tools: `{guardrails["unexpected_tools"]}`
- Raw inputs absent from summary artifacts: `{guardrails["raw_inputs_absent"]}`

## Source Artifacts

{source_rows}

## Reproduce

```bash
.venv/bin/python scripts/build_agentic_rag_eval_report.py \\
  --date {summary["evidence_date"]} \\
  --report-output docs/evidence/agentic-rag-eval-report.md \\
  --summary-output docs/evidence/agentic-rag-eval-report-summary.json
```

## Limits

Ragas live metrics remain pending until paid/API-key approval. Live web search,
production DB access/audit policy, and production MCP transport/auth also
remain pending runtime-security work. The local SQL runtime policy first gate is
complete, but it is not production DB access. This report is a reviewer-facing
consolidation of the local deterministic gates, not a replacement for
production traffic evidence.
"""


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a reviewer-facing Agentic RAG eval report from evidence JSON."
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    args = parser.parse_args()

    summary = build_agentic_rag_eval_report_summary(evidence_date=args.date)
    summary_payload = json.dumps(summary, ensure_ascii=False, indent=2)
    report_payload = render_agentic_rag_eval_report(summary)

    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(summary_payload + "\n", encoding="utf-8")
    args.report_output.write_text(report_payload, encoding="utf-8")
    print(summary_payload)
    return 0 if summary["agentic_rag_eval_report"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
