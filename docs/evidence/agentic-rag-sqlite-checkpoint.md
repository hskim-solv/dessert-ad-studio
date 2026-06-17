# Agentic RAG SQLite Checkpoint First Gate

Date: 2026-06-17

This evidence records the first durable LangGraph checkpoint gate for the
Agentic RAG control plane. It uses local SQLite only, makes no paid provider
calls, and stores the SQLite database as an uncommitted local artifact under
`outputs/agentic-rag-checkpoints/`.

## Scope

- `langgraph-checkpoint-sqlite` `SqliteSaver`.
- LangGraph `thread_id` checkpoint persistence.
- Reopened SQLite connection can list the same checkpoints.
- Worker route completes through the local mock worker path.
- Raw product name, user constraints, revision request, reference image bytes,
  and reference filename are absent from the SQLite checkpoint file.

## Result

Summary artifact:

```text
docs/evidence/agentic-rag-sqlite-checkpoint-summary.json
```

Current result:

- `agentic_rag_sqlite_checkpoint_smoke`: `passed`
- `scope`: `local_sqlite_langgraph_checkpointer_no_paid_api_call`
- `checkpoint_backend`: `sqlite`
- `checkpoint_file_created`: `true`
- checkpoints: `8`
- reopened checkpoints: `8`
- final status: `completed`
- next action: `return_cited_ad_package`
- raw inputs found in checkpoint: `false`
- raw inputs committed: `false`

## Reproduce

```bash
.venv/bin/python scripts/agentic_rag_sqlite_checkpoint_smoke.py \
  --date 2026-06-17 \
  --output docs/evidence/agentic-rag-sqlite-checkpoint-summary.json
```

Focused tests:

```bash
.venv/bin/pytest \
  tests/test_agentic_rag.py::test_agentic_rag_sqlite_checkpointer_persists_redacted_checkpoints \
  tests/test_agentic_rag_smoke_script.py::test_agentic_rag_sqlite_checkpoint_smoke_writes_redacted_summary \
  -q
```

## Limits

- This proves local durable SQLite checkpoint persistence, not production
  multi-instance Postgres storage.
- Reviewer approval UI, approval audit summary, and durable stream replay remain
  pending.
- Production trace retention policy and Phoenix/OTLP deployment evidence remain
  pending for Agentic RAG graph spans.
