# Agentic RAG Eval And Guardrail First Gate

Date: 2026-06-17

This evidence records the first local Agentic RAG golden eval and guardrail
gate. It produces Ragas-compatible deterministic proxy metrics and runs a real
promptfoo package gate without calling paid APIs. Both gates run in GitHub
Actions.

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
- GitHub Actions step: `Agentic RAG promptfoo package gate`
- promptfoo package execution:
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
- tool budget: max tool calls `7`, no unexpected tools
- raw inputs committed: `false`
- CI gate: `.github/workflows/ci.yml` runs the same command on push/PR
- promptfoo package gate: `1` passed, `0` failed, `0` errors, `9` assertions
  passed, token usage `0`, cost `0`

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
  tests/test_agentic_rag_tools.py \
  tests/test_ci_workflow.py::test_ci_runs_agentic_rag_eval_guardrail_gate \
  tests/test_agentic_rag_eval_guardrail_script.py -q
```

Offline promptfoo package path:

```bash
npm ci --no-audit --no-fund
npm run eval:promptfoo
```

Bounded package smoke:

```bash
.venv/bin/python scripts/agentic_rag_promptfoo_package_smoke.py \
  --date 2026-06-17 \
  --summary-output docs/evidence/agentic-rag-promptfoo-package-summary.json \
  --results-output docs/evidence/agentic-rag-promptfoo-results.json \
  --timeout-seconds 180
```

The package smoke executes the equivalent promptfoo command:

```bash
PROMPTFOO_DISABLE_TELEMETRY=1 promptfoo eval \
  -c evals/promptfoo/agentic-rag.yaml \
  --no-cache --no-progress-bar --no-table \
  -o docs/evidence/agentic-rag-promptfoo-results.json
```

The promptfoo provider executes:

```bash
bash ../../scripts/run_promptfoo_agentic_rag_provider.sh
```

Local package-runtime note:

- `bash ../../scripts/run_promptfoo_agentic_rag_provider.sh` runs correctly from
  the promptfoo config base path. The wrapper resolves the repository root from
  its own location and uses `.venv/bin/python` when available.
- The first `npx promptfoo@0.121.17` attempt exceeded 150 seconds during
  package startup. The fixed path uses `npm ci` plus the local
  `node_modules/.bin/promptfoo` binary and completed locally within the bounded
  smoke.

Ragas live gate is intentionally not part of the default CI gate yet. Install
the optional Python eval dependencies only for the paid semantic eval lane:

```bash
.venv/bin/python -m pip install -e ".[eval]"
```

## Limits

This is not yet a default-CI Ragas live execution gate. ADR 0016 keeps Ragas
semantic evaluator metrics behind paid/API-key approval. The promptfoo package
gate is now part of default CI and remains bounded to a local exec provider.
