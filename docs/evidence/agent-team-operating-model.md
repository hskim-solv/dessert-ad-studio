# AI Agent Team Operating Model Evidence

Date: 2026-06-17

This evidence records the first operating model for AI-agent teamwork in Dessert
Ad Studio. It adapts the useful parts of multi-agent engineering patterns:
central source of truth, task ownership, lock files, fast gates, tripwires, and
external memory through ADR/evidence docs.

## Scope

- ADR 0015 selects the operating model.
- `docs/agent-workflow/README.md` defines roles, lock contract, fast gates, and
  escalation rules.
- Multi-writer mode is allowed for independent task lanes with disjoint write
  scopes; the main agent remains integration owner.
- `docs/agent-workflow/tasks/README.md` defines the task-lock template.
- `scripts/agent_team_fast_gate.py` lists and runs lane-specific fast gates.
- Paid-provider checks are represented as a tripwire lane and are not executed
  by the script.

## Result

Summary artifact:

```text
docs/evidence/agent-team-fast-gate-summary.json
```

Current fast-gate lanes:

- `agentic-rag`
- `docs`
- `offline-eval`
- `compose`
- `paid-provider` (tripwire, not parallel-safe)

Current tested behavior:

- `--list` returns available lanes and excludes `paid-provider` from
  `parallel_safe_lanes`.
- `--lane agentic-rag --dry-run` returns commands without executing them.
- `--lane agentic-rag --execute` runs the Agentic RAG lane fast gate: focused
  tests plus graph, SSE/WebSocket stream/replay, SQLite checkpoint, and graph
  trace/eval/guardrail smokes.
- `--lane paid-provider --dry-run` reports `paid_api: true` and
  `parallel_safe: false`.

## Reproduce

```bash
.venv/bin/python scripts/agent_team_fast_gate.py --list
.venv/bin/python scripts/agent_team_fast_gate.py --lane agentic-rag --dry-run
.venv/bin/python scripts/agent_team_fast_gate.py --lane agentic-rag --execute
.venv/bin/pytest tests/test_agent_team_fast_gate.py -q
```

## Limits

- This is not a fully autonomous Docker worker swarm.
- Writer subagents are allowed for independent task bundles, but require
  disjoint write scopes and main-agent integration.
- The default mode for tightly coupled slices remains main writer plus
  read-only scouts.
