# Agent Team Task Locks

Create one task file per writer-owned lane. The filename acts as the lock.

Use this template:

```md
# TASK-ID short title

- status: claimed | in_review | completed | abandoned
- owner: main | worker-1 | worker-2
- write_scope:
  - path/or/file.py
- read_scope:
  - path/or/docs.md
- fast_gate:
  - `.venv/bin/python scripts/agent_team_fast_gate.py --lane agentic-rag --execute`
- tripwires:
  - paid API: no
  - cloud/service: no
  - destructive: no
  - broad retention: no
- completion_evidence:
  - tests:
  - smoke:
  - docs:

## Notes

```

Do not create overlapping writer tasks. The main agent owns final integration.
