# Agentic RAG Eval Report

Date: 2026-06-17

This report consolidates the offline Agentic RAG evaluation artifacts for
reviewers. It does not call paid APIs, live web search, production databases, or
external MCP transports.

## Result

- `agentic_rag_eval_report`: `passed`
- `scope`: `offline_reviewer_eval_report_no_paid_api_call`
- Golden dataset: `agentic_rag_golden_v1`, `13` cases
- Faithfulness: `1.0`
- Answer relevancy: `1.0`
- Context precision: `1.0`
- Context recall: `1.0`

## Retrieval

| Gate | Result |
|---|---|
| Keyword retrieval | category hit `1.0`, precision `0.7466666666666667`, required safety hit `1.0` |
| Chunking comparison | selected `field_aware`, category hit `0.9`, required safety hit `1.0` |
| pgvector hybrid | category hit `1.0`, precision `1.0` |

## Regression And Guardrails

- promptfoo package gate: `True` with
  `9` assertions passed,
  `0` assertions failed, `0`
  errors, `0` failures, token usage
  `0`, cost `0`
- Prompt injection blocked before worker: `True`
- Tool budget passed: `True` with max tool calls
  `7` and `7`
  planned tools
- Unexpected tools: `[]`
- Raw inputs absent from summary artifacts: `True`

## Source Artifacts

- `docs/evidence/agentic-rag-eval-guardrail-summary.json`
- `docs/evidence/rag-baseline-results.json`
- `docs/evidence/rag-chunking-comparison-results.json`
- `docs/evidence/pgvector-baseline-results.json`
- `docs/evidence/agentic-rag-promptfoo-package-summary.json`

## Reproduce

```bash
.venv/bin/python scripts/build_agentic_rag_eval_report.py \
  --date 2026-06-17 \
  --report-output docs/evidence/agentic-rag-eval-report.md \
  --summary-output docs/evidence/agentic-rag-eval-report-summary.json
```

## Limits

Ragas live metrics remain pending until paid/API-key approval. Live web search
provider smoke, credentialed production DB connection smoke, and production MCP
auth/remote client smoke also remain pending user-approved runtime-security
work. The live web search runtime policy, local SQL runtime policy, production
DB access/audit policy, and MCP loopback transport/auth boundary first gates
are complete, but they are not live production traffic, approved production
audit retention, or production MCP auth. This report is a reviewer-facing
consolidation of the local deterministic gates, not a replacement for
production traffic evidence.
