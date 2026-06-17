# Agentic RAG HITL Approval First Gate

Date: 2026-06-17

This evidence records the first local human-in-the-loop approval API gate for
the Agentic RAG control plane. It proves that an approval-routed run can be
reviewed through a redacted FastAPI approval endpoint and resumed through the
local mock worker without calling paid providers or storing raw reviewer input.

## Scope

- Starts a local Agentic RAG SSE run with the paid-provider tripwire enabled.
- Routes the graph to `human_approval` and final `wait_for_human_approval`.
- Reuses the SQLite replay summary to verify the run is actually waiting for
  approval.
- Submits a reviewer decision through:

```text
POST /agentic-rag/runs/{run_id}/approval
```

- Returns only redacted reviewer/comment hashes, decision metadata, and
  post-approval worker status.

## Result

Summary artifact:

```text
docs/evidence/agentic-rag-approval-summary.json
```

Current result:

- `agentic_rag_approval_smoke`: `passed`
- `scope`: `local_fastapi_hitl_approval_no_paid_api_call`
- approval route status: `needs_approval`
- approval route next action: `wait_for_human_approval`
- approval decision status: `approved`
- approval next action: `return_cited_ad_package`
- approval reason: `paid_provider_requested`
- post-approval worker resumed: `true`
- post-approval worker status: `succeeded`
- post-approval status: `completed`
- raw inputs committed: `false`
- audit persisted: `false`

## Reproduce

```bash
.venv/bin/python scripts/agentic_rag_approval_smoke.py \
  --date 2026-06-17 \
  --output docs/evidence/agentic-rag-approval-summary.json
```

Focused tests:

```bash
.venv/bin/pytest \
  tests/test_api.py::test_agentic_rag_run_approval_records_redacted_reviewer_decision \
  tests/test_api.py::test_agentic_rag_run_approval_rejects_non_approval_run \
  tests/test_agentic_rag_stream_smoke_script.py::test_agentic_rag_approval_smoke_writes_redacted_summary \
  -q
```

## Limits

- This is a local approval API/audit/resume first gate.
- Post-approval worker resume uses same-process ephemeral request context; raw
  request data is not persisted into SQLite checkpoints or evidence artifacts.
- It does not persist approval audit records beyond the redacted summary
  artifact.
- Reviewer approval UI now has a separate local first gate in
  `docs/evidence/agentic-rag-reviewer-ui.md`.
- Bidirectional in-stream approval has a separate local first gate; live-provider
  cross-process resume, production approval audit retention, and production
  storage policy remain pending.
