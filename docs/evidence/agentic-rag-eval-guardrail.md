# Agentic RAG Eval And Guardrail First Gate

Date: 2026-06-17

This evidence records the first local Agentic RAG golden eval and guardrail
gate. It is designed to produce Ragas/promptfoo-compatible JSON fields without
adding new eval dependencies or calling paid APIs. The same script is also run
as a dedicated GitHub Actions CI step.

## Scope

- 13-case golden dataset:
  - 10 existing marketing-context retrieval eval cases
  - 2 local worker-route cases
  - 1 paid-provider plus prompt-injection approval case
- Ragas-compatible deterministic proxy metrics:
  - `faithfulness`
  - `answer_relevancy`
  - `context_precision`
  - `context_recall`
- promptfoo-compatible regression summary:
  - case count
  - pass/fail
  - failure count
- prompt-injection guardrail:
  - stores only category/count summaries
  - routes suspicious input to human approval
  - does not execute the worker before approval
- tool allowlist and max tool-call budget checks
- raw input redaction checks
- GitHub Actions step: `Agentic RAG eval guardrail gate`

## Result

Summary artifact:

```text
docs/evidence/agentic-rag-eval-guardrail-summary.json
```

Current result:

- `agentic_rag_eval_guardrail`: `passed`
- `scope`: `local_ragas_promptfoo_compatible_no_paid_api_call`
- golden cases: `13`
- faithfulness: `1.0`
- answer relevancy: `1.0`
- context precision: `1.0`
- context recall: `1.0`
- promptfoo-compatible regression: `passed`
- prompt-injection case: blocked before worker
- tool budget: max tool calls `4`, no unexpected tools
- raw inputs committed: `false`
- CI gate: `.github/workflows/ci.yml` runs the same command on push/PR

## Reproduce

```bash
.venv/bin/python scripts/agentic_rag_eval_guardrail.py \
  --date 2026-06-17 \
  --output docs/evidence/agentic-rag-eval-guardrail-summary.json
```

Focused tests:

```bash
.venv/bin/pytest \
  tests/test_agentic_rag.py::test_agentic_rag_graph_routes_prompt_injection_to_human_approval_without_raw_inputs \
  tests/test_agentic_rag.py::test_agentic_rag_guardrail_flags_unapproved_tool_and_budget \
  tests/test_ci_workflow.py::test_ci_runs_agentic_rag_eval_guardrail_gate \
  tests/test_agentic_rag_eval_guardrail_script.py -q
```

## Limits

This is not yet a full Ragas or promptfoo execution gate. It is the first
no-new-dependency compatibility gate. Actual `ragas` and `promptfoo` package
adoption still requires an ADR with dependency/runtime comparison, CI runtime
budget, and representative semantic reference labels.
