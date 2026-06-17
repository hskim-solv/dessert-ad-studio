# Agentic RAG Eval And Guardrail First Gate

Date: 2026-06-17

This evidence records the first local Agentic RAG golden eval and guardrail
gate. It produces Ragas/promptfoo-compatible JSON fields without calling paid
APIs. The same script is also run as a dedicated GitHub Actions CI step.

Runtime adoption decision:

```text
docs/adr/0016-agentic-rag-eval-runtime.md
```

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
- promptfoo package execution scaffold:
  `evals/promptfoo/agentic-rag.yaml`
- Ragas live gate direction: optional `eval` Python extra, paid/API-key gated

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

Offline promptfoo package path:

```bash
npm install
npm run eval:promptfoo
```

Equivalent direct command:

```bash
npx promptfoo@0.121.17 eval -c evals/promptfoo/agentic-rag.yaml \
  -o docs/evidence/agentic-rag-promptfoo-results.json
```

When `promptfoo` is installed from `package.json`, the equivalent command is:

```bash
promptfoo eval -c evals/promptfoo/agentic-rag.yaml \
  -o docs/evidence/agentic-rag-promptfoo-results.json
```

The promptfoo provider executes:

```bash
bash scripts/run_promptfoo_agentic_rag_provider.sh
```

Local package-runtime note:

- `bash scripts/run_promptfoo_agentic_rag_provider.sh` produced valid redacted
  JSON summary output. The wrapper uses `.venv/bin/python` when available and
  falls back to `python3`/`python` for CI-like environments.
- `npx promptfoo@0.121.17 eval -c evals/promptfoo/agentic-rag.yaml -o
  /tmp/agentic-rag-promptfoo-results.json` was attempted on 2026-06-17 and
  exceeded 150 seconds before completion during package/runtime startup. This is
  why ADR 0016 keeps promptfoo as the next CI candidate rather than a proven CI
  package-execution gate.

Ragas live gate is intentionally not part of the default CI gate yet. Install
the optional Python eval dependencies only for the paid semantic eval lane:

```bash
.venv/bin/python -m pip install -e ".[eval]"
```

## Limits

This is not yet a full default-CI Ragas or promptfoo execution gate. ADR 0016
selects offline promptfoo regression as the next package-execution gate and a
paid/API-key-gated Ragas live gate for evaluator-LLM metrics. The current CI
still runs the deterministic compatibility gate until promptfoo runtime and
cache behavior are measured in CI.
