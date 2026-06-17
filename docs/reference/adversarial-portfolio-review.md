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
| High | The phrase `production-grade deployment` was stronger than the Kubernetes evidence before live cluster proof existed. | Accepted and partially closed | Live `kind` base-stack proof now covers apply, PVC binding, Triton model sync, pod readiness, port-forward, and full `/generate` smoke. Keep stronger claims scoped to the synchronous API/UI/Triton base stack until async K8s and production hardening are added. |
| High | Product-photo preservation is proven for deterministic composition, but paid OpenAI image-edit provider gates failed. | Accept | Put this limitation near the top of portfolio materials. Treat any further paid iteration as remediation work, not as a proven portfolio claim. |
| High | Kubernetes deployability did not include the async worker/Redis/Postgres operational path that Docker Compose demonstrates. | Accepted and first gate closed | Added `deploy/k8s/overlays/async` with Redis, pgvector/Postgres, worker, API queue/history env, render test, and live `kind` generation-job smoke. Keep broader async reliability matrix as the next operations gap. |
| Medium | Evaluation is still demo/proxy-heavy: small retrieval sets, 3 workflow demos, synthetic product-analysis evals, and limited visual acceptance criteria. | Accept | Add a real eval pack with 30+ product-like scenarios, human rubric, failure taxonomy, grounding checks, latency/cost p95, and pass/fail thresholds. |
| Medium | `RAG` and `pgvector` can be overread as production semantic retrieval, while the current vector lane is a curated guide store with deterministic hash embeddings and keyword reranking. | Accept with clarification | Use `curated retrieval eval` and `pgvector storage/query lane` language unless a real embedding model and broader corpus are added. |
| Medium | Trace/privacy evidence is safe for local/demo usage, but not yet a production trace privacy guarantee. Some metadata included filenames and artifact paths. | Accepted and first gate closed | Workflow trace/log and image-failure log allowlist tests now prove raw prompt summaries, product inputs, reference filenames, generated copy, and image paths are excluded from persistent surfaces. Keep production trace rollout gated on another deployment-specific attribute review. |
| Medium | Async job evidence started as mostly happy-path smoke. | Accepted and first live failure gate closed | Burst jobs, failure state, queue enqueue failure, duplicate polling, worker startup wait, K8s async smoke, live worker outage/restore, and explicit retry/timeout/cancel non-support are covered. Multi-worker behavior remains unclaimed. |
| Medium | Cost evidence recorded usage, but did not estimate dollars or enforce a budget. | Accepted and first gate closed | Offline cost guard now records estimated USD, pricing source, budget result, env override support, and fail-closed behavior for unknown rates when a budget is set. Keep `paid runs are approval-gated`; account-level billing limits still belong in the OpenAI dashboard. |
| Low | A2A/FastMCP can distract from the core service story. | Accept | Keep A2A as an optional spike/appendix. Do not let A2A/FastMCP outrank core workflow, eval, deployment, and reliability work. |
| Low | Some evidence documents contain historical full-suite counts that are now stale. | Accept | Add a single evidence freshness section and make older docs explicit historical snapshots. |

## Review-Driven Roadmap

| Priority | Workstream | Completion evidence |
|---|---|---|
| P0 | Reframe portfolio claims around verified scope. | README and final target distinguish verified, in-progress, and not-yet-proven items. |
| P1 | Live Kubernetes deployability proof. | Complete for the synchronous base stack: `docs/evidence/k8s-live-smoke-summary.json` records `kind` apply, Triton model sync, pod readiness, port-forward, and full `/generate` smoke. |
| P2 | Kubernetes async operations alignment. | First gate complete: async overlay renders and live `kind` smoke passes Redis/RQ worker plus Postgres history. |
| P3 | Provider-quality image-edit gate. | Paid `gpt-image-2` + `quality=medium` run over 3 public samples is complete and failed: ROI preservation checks passed, but latency, text-contamination, and cost guard failed. A post-calibration one-sample canary reached the API, stayed under budget, passed ROI preservation, passed text-contamination, and manual local review found no visible text, but it still failed the 30s latency threshold. Provider-quality image editing remains unproven until the latency strategy is resolved and a later paid gate passes. |
| P4 | Real evaluation pack. | First product-like gate complete: 30 deterministic workflow scenarios with reproducible summary JSON. Offline visual proxy gate complete for 6 committed banners. Offline provider visual review first gate now records the human-review rubric and latest paid canary/postmortem without claiming provider-quality success. Provider-quality visual statistics remain pending until the latency strategy is resolved and a later paid gate passes. |
| P5 | Trace/log privacy hardening. | First gate complete: allowlist tests cover workflow trace/log attributes, image-failure usage logs, and OTEL smoke output. Production external-trace rollout still requires deployment-specific attribute review. |
| P6 | Async reliability matrix. | First live failure gate complete: burst submit, workflow failure state, queue enqueue failure, duplicate polling, worker startup wait, K8s async smoke, live worker outage/restore, and explicit retry/timeout/cancel non-support passed. Multi-worker failure behavior remains pending. |
| P7 | Cost guard. | First offline gate complete: `docs/evidence/cost-guard-summary.json` records `gpt-image-2` cost estimate `$0.01881` under a `$0.02` budget. Live paid provider-quality evidence also confirms `--max-estimated-cost-usd` fails closed after returned usage exceeded the `$0.20` budget. |

## Immediate Reframe

Use these claims until the roadmap items above are complete:

- Deployment: `Docker Compose smoke + Kubernetes render/deployability evidence`, not `production-grade deployment`.
- Image preservation: `deterministic preservation path passes; provider image-edit gate is pending after one failed live run`.
- Retrieval: `measured curated retrieval baseline + pgvector storage/query lane`, not broad semantic RAG quality.
- Observability: `local/demo AgentOps traceability`, not production trace privacy.
- A2A/FastMCP: optional integration spikes, not the core product boundary.
