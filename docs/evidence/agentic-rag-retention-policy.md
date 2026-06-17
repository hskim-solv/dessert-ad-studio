# Agentic RAG Retention Boundary First Gate

Date: 2026-06-17

This evidence records the retention boundary for Agentic RAG replay, approval,
post-approval resume, and trace payloads. It does not introduce a new durable
raw-input store. It documents and tests the current safe boundary before any
production storage or live-provider cross-process resume claim is made.

## Scope

- Local SQLite replay keeps redacted checkpoints only.
- Approval evidence keeps decision metadata plus reviewer/comment hashes only.
- Post-approval worker resume uses same-process ephemeral request context.
- Mock/local approval runs may resume from redacted SQLite replay when their
  checkpointed resume policy is `mock_generation_worker`.
- External trace retention excludes raw model inputs, raw images, raw reviewer
  comments, and raw provider responses.
- Durable raw request storage, live-provider cross-process resume, production
  approval audit retention, and external trace payload retention require a
  separate user decision.

Decision record:

```text
docs/adr/0018-agentic-rag-retention-boundary.md
```

## Result

Summary artifact:

```text
docs/evidence/agentic-rag-retention-policy-summary.json
```

Current result:

- `agentic_rag_retention_policy_smoke`: `passed`
- `scope`: `policy_gate_no_raw_input_store`
- decision: `redacted_replay_with_ephemeral_raw_context_and_mock_resume_policy`
- replay artifact: `local_sqlite_redacted_checkpoints`
- replay raw inputs allowed: `false`
- same-process ephemeral resume: `true`
- mock redacted SQLite replay resume: `true`
- live-provider cross-process resume: `pending_user_decision`
- persistent approval audit claim: `false`
- raw model inputs in traces allowed: `false`
- raw inputs committed: `false`

## Reproduce

```bash
.venv/bin/python scripts/agentic_rag_retention_policy_smoke.py \
  --date 2026-06-17 \
  --output docs/evidence/agentic-rag-retention-policy-summary.json
```

Focused test:

```bash
.venv/bin/pytest tests/test_agentic_rag_retention_policy.py -q
```

## Limits

- This is a policy/evidence gate, not a production storage implementation.
- It intentionally blocks durable raw request storage until storage location,
  retention period, deletion behavior, and user/project/entity scope are
  decided.
- Live-provider cross-process resume remains pending.
