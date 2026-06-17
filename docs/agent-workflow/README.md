# AI Agent Team Operating Model

This workflow makes multi-agent work explicit and reviewable without turning the
repository into an uncontrolled autonomous swarm.

## Default Mode

- Main agent is the only writer and integration owner.
- Up to two subagents may run in parallel as read-only scouts:
  - failure or bottleneck analysis
  - verification or test-command planning
- Writer subagents are opt-in only for large milestones with disjoint write
  scopes.

## Multi-Writer Mode

Use multiple writer agents when the milestone can be split into independent
task lanes with non-overlapping files and separate fast gates. Good candidates:

- reviewer UI
- eval or prompt-injection gate
- MCP/tool wrapper
- docs/evidence packaging
- deployment manifest-only work

Avoid multiple writers inside one tightly coupled slice, such as one FastAPI
endpoint plus its shared schema and shared API tests. In that case, keep one
writer and use scouts for review or test planning.

The main agent remains the integration owner: it reviews all diffs, resolves
merge order, runs the relevant lane gates, then runs the full regression before
commit/push.

## Task Lock Contract

Before any writer subagent is allowed, create a task note under
`docs/agent-workflow/tasks/` with:

- task id and owner
- write scope, as exact files or directories
- read-only context the agent may inspect
- fast gate commands
- tripwires requiring main-agent or user decision
- completion evidence

The filename is the lock. Do not assign two writer agents to overlapping write
scopes. Delete or mark the task complete only after the main agent has reviewed
the diff and run the relevant gate.

## Fast Gates

Use `scripts/agent_team_fast_gate.py` to route lane-specific checks:

```bash
.venv/bin/python scripts/agent_team_fast_gate.py --list
.venv/bin/python scripts/agent_team_fast_gate.py --lane agentic-rag --dry-run
.venv/bin/python scripts/agent_team_fast_gate.py --lane agentic-rag --execute
```

Parallel-safe lanes write generated summaries to `/tmp` when possible:

- `agentic-rag`
- `docs`
- `offline-eval`
- `compose`

Tripwire lane:

- `paid-provider` is listed but not executed by the script because it requires
  paid API and budget approval.

## Escalation Rules

Stop for user decision before:

- paid API calls
- new cloud or hosted service adoption
- production-like deploys
- broad data retention changes
- destructive cleanup

The main agent may continue without asking for:

- read-only analysis
- local tests and offline evals
- documentation updates
- local git commit, push, PR, merge, issue, or branch delete when scoped to this
  project

## Portfolio Signal

This model shows that Dessert Ad Studio is not only an agentic application, but
also a repo with an agent-team operating system: task ownership, conflict
avoidance, fast verification, tripwire handling, and evidence-driven integration.
