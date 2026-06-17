# Agentic RAG Reviewer Approval UI First Gate

Date: 2026-06-17

This evidence records the first local Streamlit reviewer approval UI gate for
the Agentic RAG control plane. It proves that a reviewer-facing queue can submit
an approval decision for an approval-routed run and merge the redacted decision
metadata back into Streamlit session state without calling paid providers or
committing raw reviewer input.

## Scope

- Starts a local Agentic RAG SSE run with the paid-provider tripwire enabled.
- Uses the replay endpoint as the reviewer-visible source of truth for the
  pending run.
- Stores pending runs under Streamlit session key:

```text
agentic_rag_runs
```

- Renders the approval queue helper for runs with `needs_approval` status.
- Submits reviewer decisions through the existing FastAPI approval endpoint:

```text
POST /agentic-rag/runs/{run_id}/approval
```

- Merges only redacted reviewer/comment hashes and decision metadata into the UI
  run state.

## Result

Summary artifact:

```text
docs/evidence/agentic-rag-reviewer-ui-summary.json
```

Current result:

- `agentic_rag_reviewer_ui_smoke`: `passed`
- `scope`: `local_streamlit_reviewer_approval_ui_no_paid_api_call`
- Streamlit session key: `agentic_rag_runs`
- approval run status: `needs_approval`
- approval run next action: `wait_for_human_approval`
- UI decision status: `approved`
- UI decision next action: `dispatch_generation_worker_after_approval`
- raw reviewer id committed: `false`
- raw reviewer comment committed: `false`
- raw request committed: `false`
- paid API call count: `0`

## Reproduce

```bash
.venv/bin/python scripts/agentic_rag_reviewer_ui_smoke.py \
  --date 2026-06-17 \
  --output docs/evidence/agentic-rag-reviewer-ui-summary.json
```

Focused tests:

```bash
.venv/bin/pytest \
  tests/test_agentic_rag_reviewer_ui_smoke.py \
  tests/test_streamlit_jobs.py \
  -q
```

## Limits

- This is a local Streamlit helper/UI first gate, not a full interactive
  stream-to-approval workflow.
- It does not yet resume the graph worker after approval.
- It does not persist production approval audit records.
- Bidirectional in-stream approval, production approval retention, production
  replay retention, and production storage policy remain pending.
