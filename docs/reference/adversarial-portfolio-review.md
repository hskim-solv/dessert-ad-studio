# Adversarial Portfolio Review

Date: 2026-06-17

This note records an independent adversarial review of Dessert Ad Studio as a
senior AI/backend portfolio repository. Three subagents reviewed the repository
without conversation history and without paid/API calls:

- `eval-engineer`: overall senior-portfolio critique.
- `readme-generator`: README and portfolio narrative critique.
- `backend-contract-reviewer`: deployability and operations critique.

Scope limits:

- Repository files only.
- No `.env`, secrets, raw outputs, logs, or generated private images.
- No paid model calls.
- No file edits by reviewers.

## Consolidated Findings

| Severity | Finding | Disposition | Roadmap action |
|---|---|---|---|
| High | The phrase `production-grade deployment` is stronger than the current Kubernetes evidence. The repo has Kustomize render evidence, probes, HPA, ingress, and compose smoke, but no live cluster scheduling or full in-cluster `/generate` smoke. | Accept | Reframe as `deployment-shaped` or `Kustomize deployability evidence`; add live `kind`/cluster apply, readiness, ingress, Triton model sync, and full API smoke before using stronger deployment language. |
| High | Product-photo preservation is proven for deterministic composition, but the first paid OpenAI image-edit provider gate failed. | Accept | Put this limitation near the top of portfolio materials. Keep the next paid `gpt-image-2` + `quality=medium` gate as a decision-gated milestone. |
| High | Kubernetes deployability does not include the async worker/Redis/Postgres operational path that Docker Compose demonstrates. | Accept | Either add a Kubernetes worker/Redis/Postgres overlay, or label current K8s evidence as sync API skeleton plus Triton/UI/AgentOps render evidence. |
| Medium | Evaluation is still demo/proxy-heavy: small retrieval sets, 3 workflow demos, synthetic product-analysis evals, and limited visual acceptance criteria. | Accept | Add a real eval pack with 30+ product-like scenarios, human rubric, failure taxonomy, grounding checks, latency/cost p95, and pass/fail thresholds. |
| Medium | `RAG` and `pgvector` can be overread as production semantic retrieval, while the current vector lane is a curated guide store with deterministic hash embeddings and keyword reranking. | Accept with clarification | Use `curated retrieval eval` and `pgvector storage/query lane` language unless a real embedding model and broader corpus are added. |
| Medium | Trace/privacy evidence is safe for local/demo usage, but not yet a production trace privacy guarantee. Some metadata includes filenames and artifact paths. | Investigate | Add a trace/log attribute allowlist and tests that prove raw prompt, raw response, reference bytes, customer image, and generated copy are excluded. |
| Medium | Async job evidence is a good start but mostly happy-path smoke. | Investigate | Add burst jobs, worker failure, retry/failure state, timeout, cancellation or explicit non-support, duplicate polling, and Postgres consistency checks. |
| Medium | Cost evidence records usage, but does not yet estimate dollars or enforce a budget. | Accept with clarification | Keep `paid runs are approval-gated`; add cost estimate summaries and an optional budget guard before claiming cost control. |
| Low | A2A/FastMCP can distract from the core service story. | Accept | Keep A2A as an optional spike/appendix. Do not let A2A/FastMCP outrank core workflow, eval, deployment, and reliability work. |
| Low | Some evidence documents contain historical full-suite counts that are now stale. | Accept | Add a single evidence freshness section and make older docs explicit historical snapshots. |

## Review-Driven Roadmap

| Priority | Workstream | Completion evidence |
|---|---|---|
| P0 | Reframe portfolio claims around verified scope. | README and final target distinguish verified, in-progress, and not-yet-proven items. |
| P1 | Live Kubernetes deployability proof. | Fail-closed live smoke automation is added in `scripts/k8s_live_smoke.py`; remaining proof is an actual `kind`/cluster apply, pod readiness, ingress/port-forward smoke, full `/generate` path after Triton model sync, and documented rollback/cleanup. |
| P2 | Kubernetes async operations alignment. | Worker, Redis, and Postgres overlay or explicit documentation that K8s base is a sync API skeleton. |
| P3 | Provider-quality image-edit gate. | Approved paid `gpt-image-2` + `quality=medium` run over 3 public samples with ROI preservation, text-contamination, latency, and redaction metrics. |
| P4 | Real evaluation pack. | 30+ scenario matrix, retrieval grounding checks, human review rubric, failure taxonomy, p95 latency/cost, and reproducible summary JSON. |
| P5 | Trace/log privacy hardening. | Allowlist tests for trace/log attributes and updated AgentOps evidence separating demo-safe from production-safe telemetry. |
| P6 | Async reliability matrix. | Burst, worker failure, retry/failure, timeout, duplicate polling, and history consistency evidence. |
| P7 | Cost guard. | Per-run estimated cost in summaries and optional budget threshold for paid smoke scripts. |

## Immediate Reframe

Use these claims until the roadmap items above are complete:

- Deployment: `Docker Compose smoke + Kubernetes render/deployability evidence`, not `production-grade deployment`.
- Image preservation: `deterministic preservation path passes; provider image-edit gate is pending after one failed live run`.
- Retrieval: `measured curated retrieval baseline + pgvector storage/query lane`, not broad semantic RAG quality.
- Observability: `local/demo AgentOps traceability`, not production trace privacy.
- A2A/FastMCP: optional integration spikes, not the core product boundary.
