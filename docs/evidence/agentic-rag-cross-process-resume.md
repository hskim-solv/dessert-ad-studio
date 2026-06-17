# Agentic RAG Cross-Process Resume First Gate

Date: 2026-06-17

This evidence records the first local cross-process resume gate for the
Agentic RAG approval flow. It proves that an approval-routed mock/local run can
resume from redacted SQLite replay after the same-process pending context has
been cleared.

## Scope

- Starts an approval-routed Agentic RAG run through the FastAPI SSE endpoint.
- Persists redacted LangGraph checkpoints in local SQLite.
- Confirms the replay summary exposes `resume_policy_mode:
  mock_generation_worker`.
- Clears the in-memory pending approval context before submitting approval.
- Approves the run through:

```text
POST /agentic-rag/runs/{run_id}/approval
```

- Resumes the mock generation worker from redacted SQLite replay summary.
- Stores no raw customer input, reviewer id, or reviewer comment.

## Result

Summary artifact:

```text
docs/evidence/agentic-rag-cross-process-resume-summary.json
```

Current result:

- `agentic_rag_cross_process_resume_smoke`: `passed`
- `scope`: `local_redacted_sqlite_replay_resume_no_paid_api_call`
- checkpointing enabled: `true`
- approval route status: `needs_approval`
- resume policy mode: `mock_generation_worker`
- pending context cleared before approval: `true`
- post-approval resume source: `redacted_sqlite_replay`
- post-approval worker status: `succeeded`
- raw inputs committed: `false`

## Reproduce

```bash
.venv/bin/python scripts/agentic_rag_cross_process_resume_smoke.py \
  --date 2026-06-17 \
  --output docs/evidence/agentic-rag-cross-process-resume-summary.json
```

Focused test:

```bash
.venv/bin/pytest \
  tests/test_agentic_rag_smoke_script.py::test_agentic_rag_cross_process_resume_smoke_writes_redacted_summary \
  -q
```

## Limits

- This is a local no-paid-provider gate for `mock_generation_worker` resume
  policy only.
- It does not resume live paid-provider runs after process restart.
- It does not persist production approval audit records.
- Durable production replay/audit storage still requires an explicit retention
  decision before storing external traces, raw requests, or provider payloads.
