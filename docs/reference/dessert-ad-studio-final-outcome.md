# Dessert Ad Studio Final Outcome Target

Updated: 2026-06-17

## Final Product Definition

Dessert Ad Studio v2 is a **Production-grade Agentic RAG System for
small-business ad generation**.

The product is not a generic RAG chatbot and not an image-generation demo. The
user uploads a product photo and a short marketing request. An Agentic RAG
control plane retrieves business evidence, plans tool calls, validates
guardrails, requests human approval when needed, orchestrates copy/image/overlay
workers, streams execution state, and returns cited ad assets with evaluation,
trace, cost, failure, and deployment evidence.

## Canonical Portfolio Goal

This repository should be presented as:

> A production-grade Agentic RAG workflow that retrieves business evidence,
> orchestrates tools with a typed graph, enforces guardrails, streams execution
> state, and produces cited ad assets with evaluation, tracing, cost controls,
> failure analysis, and deployability evidence.

The project should not be framed as "a dessert ad app" or "an image generation
demo." The dessert/cafe domain is the concrete business scenario. The hiring
signal is the ability to build, evaluate, observe, and deploy a multimodal AI
workflow as a reliable service.

## Final Deliverable Scope

The final artifact should prove the following integrated system:

```mermaid
flowchart LR
  UI[Streamlit reviewer UI] --> API[FastAPI async API<br/>SSE/WebSocket run stream]
  API --> G[LangGraph StateGraph<br/>typed state schema]

  G --> PLAN[Planner / supervisor]
  PLAN --> RAG[Document retrieval tool]
  RAG --> VDB[(pgvector / hybrid retrieval)]
  RAG --> CITE[Citation builder]

  PLAN --> TOOLS[Tool allowlist]
  TOOLS --> SQL[SQL query tool]
  TOOLS --> WEB[Web search tool]
  TOOLS --> INT[Internal API tool]
  TOOLS --> MCP[MCP tool server]

  PLAN --> WORK[Worker / executor]
  WORK --> COPY[Copy backend]
  WORK --> IMG[Image-edit backend]
  WORK --> OVERLAY[Deterministic Korean overlay]

  G --> REFLECT[Critic / reflection loop]
  REFLECT --> GUARD[Structured validation<br/>PII/secrets/tool budget]
  GUARD --> HITL[Human approval node]
  HITL --> OUT[Cited ad package<br/>assets + eval + trace]
```

The concrete domain remains Korean small-business advertising. The portfolio
claim is the production engineering around Agentic RAG: backend contracts,
stateful orchestration, retrieval quality, tool safety, eval, tracing, cost,
fallbacks, and deployment evidence.

## Capability Classification

| Category | Must be included in final portfolio | Strong bonus | Not required for this portfolio |
|---|---|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic schemas, async endpoints, SSE or WebSocket streaming | Separate reviewer UI for human approval | Replacing FastAPI with another backend framework |
| Agent orchestration | LangGraph StateGraph, typed state schema, conditional edges, retry/reflection loop, supervisor-worker or planner-executor, SQLite/Postgres checkpointing, human-in-the-loop approval node | Multi-agent decomposition with independent worker traces | RLHF or custom agent training |
| RAG | Document ingestion, chunking comparison, embeddings, vector DB, hybrid search or reranker, citations, retrieval fallback | GraphRAG or knowledge graph evidence | Broad web-scale corpus |
| Tools | Web search, SQL query, internal API, document retrieval, tool allowlist | One MCP tool server | Large marketplace of tools |
| Evaluation | Golden dataset, Ragas metrics, promptfoo regression, CI eval gate | Ragas + promptfoo trend report across releases | Human preference training loop |
| Observability | Phoenix or LangSmith tracing, latency, token usage, cost, tool success/failure, failed-run analysis | Two tracing backends compared | Production APM contract with real customer traffic |
| Guardrails | Structured output validation, prompt-injection tests, max tool-call budget, PII/secrets leakage prevention, graceful fallback | Agent security/red-team report | Formal verification |
| Deployment | Docker, GitHub Actions, architecture diagram, eval report | Cloud deploy on AWS/GCP/Azure, Kubernetes, Terraform, demo video | Robotics, theorem proving, custom SLM training |

## Korean Hiring Validation

Validated on 2026-06-15 against roughly 45 non-duplicate Korean AI Agent, RAG,
LLMOps, backend AI, and inference-serving job postings across Wanted, Remember,
Saramin/Jumpit, JobKorea, and company career pages. This sample is enough to
fix the portfolio direction, but not enough for exact market-share statistics.

| Repeated Korean hiring signal | Portfolio implication |
|---|---|
| RAG, retrieval, vector DB, hybrid search, reranking | Build keyword retrieval first, then add measured hybrid/vector retrieval. Do not claim RAG quality without eval evidence. |
| FastAPI, API contracts, backend service operation | Keep FastAPI as the core service boundary and add job/status, history, failure handling, and smoke evidence. |
| Docker, Kubernetes, CI/CD, health checks, monitoring | Treat deployability and operational evidence as first-class deliverables, not extras. |
| LangGraph/LangChain/LlamaIndex, tool/function calling, agent workflow | Show an explicit typed workflow for product analysis, retrieval, copy, image, overlay, and evaluation. |
| LLMOps/AgentOps, quality evaluation, trace, latency/cost/failure monitoring | Add reproducible evals, OTEL/Phoenix traces, JSONL summaries, and regression checks. |
| vLLM, Triton, ONNX, TensorRT, SGLang | Keep Triton/ONNX as concrete serving proof. Add vLLM/TensorRT only when a measured serving benchmark supports the story. |
| MCP/A2A | Treat as a later thin integration layer and hiring bonus, not the main product path. |

Confirmed positioning:

> For the Korean market, the strongest senior portfolio angle is not model
> novelty. It is measured retrieval + AI backend + workflow orchestration +
> evaluation + observability + deployability evidence.

## Current Verification Scope

Verified:

- Deterministic preservation/composition path for public samples.
- Korean text rendering through deterministic overlay instead of image-model
  text rendering.
- Curated retrieval baseline, offline chunking comparison, and a measured
  pgvector storage/query lane.
- Redis/RQ and Postgres job/history path in Docker Compose.
- Local/demo AgentOps trace evidence, Kubernetes Kustomize render evidence, and
  live `kind` base-stack smoke with Triton model sync plus full `/generate`.
- First trace/log privacy allowlist gate for workflow traces, generation logs,
  image-failure usage logs, and OTEL smoke output.
- Kubernetes async overlay and live `kind` smoke for Redis/RQ worker plus
  Postgres generation history.
- First async reliability matrix for burst submit, failure state, queue enqueue
  failure, duplicate polling, worker startup wait, K8s async smoke, worker
  outage/restore, explicit retry/timeout/cancel non-support, and scoped
  multi-worker policy.
- 30-scenario product-like deterministic workflow eval with failure-case summary
  fields.
- Final target architecture decision: Agentic RAG control plane over the
  existing multimodal workflow, recorded in
  [`docs/adr/0011-agentic-rag-control-plane-final-target.md`](../adr/0011-agentic-rag-control-plane-final-target.md).
- First LangGraph control-plane gate: typed graph state, deterministic
  planner/tool-suite/retriever/citation/guardrail/HITL/finalize nodes, conditional
  approval routing, local mock worker execution through the existing generation
  workflow, retry/reflection test coverage, in-memory checkpoint proof,
  3 citations, redacted cited ad package summary, 8 approval checkpoints,
  9 worker checkpoints, and redacted summary evidence in
  [`docs/evidence/agentic-rag-graph.md`](../evidence/agentic-rag-graph.md).
- First FastAPI async SSE/WebSocket streaming and replay gate:
  `POST /agentic-rag/runs/stream` returns `text/event-stream`, WebSocket
  `/agentic-rag/runs/ws` sends JSON event envelopes, both surfaces emit 9
  redacted run/node/completion events or messages, stream local graph progress
  through `run_tool_suite` and `execute_worker`, emit a durable `agr-*` run id,
  support redacted local SQLite replay through
  `GET /agentic-rag/runs/{run_id}/replay`, and prove bidirectional WebSocket
  approval/resume for approval-routed runs. Evidence is recorded in
  [`docs/evidence/agentic-rag-streaming.md`](../evidence/agentic-rag-streaming.md).
- First durable SQLite checkpoint gate: local `langgraph-checkpoint-sqlite`
  persists 9 checkpoints, a reopened connection lists the same 9 checkpoints,
  the worker route completes, redacted cited package metadata is present, and
  raw inputs are absent from the SQLite file.
  Evidence is recorded in
  [`docs/evidence/agentic-rag-sqlite-checkpoint.md`](../evidence/agentic-rag-sqlite-checkpoint.md).
- AI agent team operating model: ADR 0015, main-writer ownership, read-only
  scouts, task-lock template, lane fast-gate CLI, and paid-provider tripwire
  lane are recorded in
  [`docs/evidence/agent-team-operating-model.md`](../evidence/agent-team-operating-model.md).
- First Agentic RAG graph trace gate: 7 local OpenInference-compatible
  LangGraph node spans including `run_tool_suite`, API stream tracer wiring, and redacted span attributes
  are recorded in
  [`docs/evidence/agentic-rag-trace.md`](../evidence/agentic-rag-trace.md).
- First Agentic RAG run-metrics gate: local graph-node latency, explicit mock
  token/cost zero values, planned/successful tool-call counts, and a
  deterministic failed-worker analysis route are recorded without paid API calls
  or raw inputs in
  [`docs/evidence/agentic-rag-run-metrics.md`](../evidence/agentic-rag-run-metrics.md).
- First Agentic RAG local tool-suite gate: graph-planned tools now cover
  document retrieval, local web-search snapshot, allowlisted SQLite SQL query,
  in-process internal API policy preview, citation builder, guardrail check, and
  generation workflow. FastMCP server import/tool-call smoke passes with `mcp`
  1.28.0 and records a loopback-only `streamable-http` transport/auth boundary.
  Evidence is recorded in
  [`docs/evidence/agentic-rag-tools.md`](../evidence/agentic-rag-tools.md).
- First Agentic RAG eval/guardrail gate: 13 local golden cases produce
  Ragas-compatible deterministic metrics and a real promptfoo package gate.
  Faithfulness, answer relevancy, context precision, and context recall proxy
  scores are `1.0`; prompt-injection routes to HITL before worker execution;
  tool allowlist/budget checks pass; raw inputs remain absent from artifacts;
  and both the compatibility script and promptfoo package smoke are wired as
  GitHub Actions CI steps. Evidence is recorded in
  [`docs/evidence/agentic-rag-eval-guardrail.md`](../evidence/agentic-rag-eval-guardrail.md).
  ADR `0016-agentic-rag-eval-runtime` keeps Ragas live metrics behind
  paid/API-key approval.
- First Agentic RAG HITL approval API gate: approval-routed runs can be reviewed
  through `POST /agentic-rag/runs/{run_id}/approval`, returning only redacted
  reviewer/comment hashes, decision metadata, and same-process post-approval
  worker status. Evidence is recorded in
  [`docs/evidence/agentic-rag-approval.md`](../evidence/agentic-rag-approval.md).
- First Agentic RAG cross-process resume gate: a mock/local approval-routed run
  persists `resume_policy_mode=mock_generation_worker`, clears the in-memory
  pending context before approval, and resumes from redacted SQLite replay
  without raw inputs or paid API calls. Evidence is recorded in
  [`docs/evidence/agentic-rag-cross-process-resume.md`](../evidence/agentic-rag-cross-process-resume.md).
- First Agentic RAG reviewer approval UI gate: replay-backed approval-routed
  runs can be shown in Streamlit under `agentic_rag_runs`, approved or rejected
  through the existing API, and merged back into UI state with only redacted
  reviewer/comment hashes, decision metadata, and post-approval worker status.
  Evidence is recorded in
  [`docs/evidence/agentic-rag-reviewer-ui.md`](../evidence/agentic-rag-reviewer-ui.md).
- First Agentic RAG retention boundary gate: ADR 0018 adopts redacted replay
  with same-process ephemeral raw context plus mock-only redacted SQLite replay
  resume, and records that durable raw request storage, live-provider
  cross-process resume store, production approval audit retention, external
  trace backend selection, retention above 7 days, and production customer trace
  capture require explicit user decision. It also defines a deployment trace
  retention contract for redacted node/status/latency/tool/error/cost
  attributes. Evidence is recorded in
  [`docs/evidence/agentic-rag-retention-policy.md`](../evidence/agentic-rag-retention-policy.md).
- Agentic RAG pending decision register: 9 user-gated pending decisions are
  centralized with approval reason, current boundary, no-claim rule, and next
  evidence artifact. Evidence is recorded in
  [`docs/evidence/agentic-rag-decision-register.md`](../evidence/agentic-rag-decision-register.md).
- Agentic RAG final readiness audit: the final portfolio target is mapped to 9
  capability categories, local first-gate evidence is verified, production
  completion remains false, and provider-quality image editing stays in the
  `not_claimed` boundary. Evidence is recorded in
  [`docs/evidence/agentic-rag-final-readiness.md`](../evidence/agentic-rag-final-readiness.md).

Not yet proven:

- Full LangGraph production orchestration. The first offline graph, SSE, local
  SQLite checkpoint, local replay, local graph trace, local run-metrics, local
  approval API, reviewer approval UI, same-process post-approval worker resume,
  and mock-only redacted SQLite cross-process resume first gates are complete.
  The retention boundary policy is defined, but live-provider cross-process
  resume, an approved production storage implementation, external trace backend
  selection/production customer trace capture, and live provider token/cost
  telemetry remain pending.
  The pending decision register centralizes these approval-gated items so they
  are not implied as production-complete.
- Full production streaming. SSE, WebSocket, bidirectional approval, local
  SQLite replay, mock-only cross-process resume, and retention boundary policy
  first gates are complete; live-provider cross-process resume, approved
  production replay/audit storage, and production stream trace integration
  remain pending.
- Actual Ragas live execution in CI. Promptfoo package execution is now bounded
  and part of default CI, but evaluator-LLM Ragas live metrics remain
  paid/API-key gated.
- Live/production tool suite. Local web search, allowlisted SQLite SQL with
  read-only/raw-SQL-disabled/mutation-disabled/row-limit/timeout policy,
  in-process internal API, document retrieval, local FastMCP package smoke plus
  loopback-only transport/auth boundary, live web search runtime policy, and
  production DB access/audit policy first gates are present; live web search
  provider smoke, credentialed production DB connection/audit-retention smoke,
  production MCP auth provider selection and remote client transport/auth smoke
  remain pending; the remote client auth contract first gate is recorded.
- Full production citation assembly across live retrieved documents and
  generated ad outputs. A local redacted cited package first gate is complete;
  production/live source contracts and approved storage remain pending.
- Cloud deployment and demo video.
- Provider-quality image editing. The first paid OpenAI image-edit gate failed;
  the strengthened `gpt-image-2` + `quality=medium` gate also failed. ROI
  preservation, script cost guard, and post-calibration text-contamination
  checks passed in the latest one-sample canary, but latency still failed the
  30 second threshold. Provider-quality image editing remains unproven until
  the latency strategy is resolved and a later paid gate passes.
- Production async operation. Kubernetes now has a local/test async overlay
  smoke, first reliability matrix, single worker outage/restore evidence, and
  explicit retry/timeout/cancel non-support evidence plus scoped multi-worker
  policy, but not exactly-once processing, worker affinity, or production
  storage policy.
- Production trace privacy. The first allowlist gate and deployment trace
  retention contract are complete, but external backend selection and
  production customer trace capture remain pending user decisions.
- Broad real-world quality statistics. Current evals now include 30
  product-like deterministic scenarios and an offline visual proxy over 6
  committed banners, but not human-rated real customer outcomes or
  provider-quality visual statistics.

## Target Architecture

```mermaid
flowchart LR
  U[User<br/>product photo + ad request] --> UI[Upload Studio<br/>Streamlit]
  UI --> API[FastAPI /generate]
  API --> WF[Generation Workflow]

  WF --> TS[Triton/ONNX<br/>template scorer]
  WF --> PA[VLM Product Analysis<br/>product/color/preservation points]
  PA --> RAG[Marketing Context Retrieval<br/>keyword baseline + pgvector hybrid lane]
  RAG --> COPY[Copy Backend<br/>3 Korean ad-copy options]
  PA --> IMG[Image Backend<br/>OpenAI/FLUX2]
  COPY --> OVERLAY[Deterministic Korean Overlay<br/>PIL/Canvas]
  IMG --> OVERLAY
  OVERLAY --> OUT[Ad banner result<br/>download/gallery/revision]

  WF --> OBS[Trace / Eval / Logs<br/>OTEL Phoenix JSONL RAG eval]
  API --> DEPLOY[Docker / K8s / CI evidence]
```

## Required Features

| Area | Final target |
|---|---|
| Input | Product photo upload plus product name, price/benefit, campaign purpose, tone, platform, and target audience. |
| Product analysis | Detect product name, dominant colors, mood, selling points, and visual preservation notes. |
| Retrieval | Retrieve cafe/dessert, platform, CTA, discount, premium-tone, and prohibited-claims guidance. Keep keyword retrieval as the default path and expose measured `pgvector_hybrid` as the vector lane. |
| Copy | Generate at least 3 structured Korean copy options with headline, body, and CTA. |
| Image | Generate or compose a product-preserving ad visual, with explicit reference-image support behavior per backend. |
| Korean overlay | Do not ask the image model to render Korean text. Render copy, price, CTA, and layout deterministically with PIL, Canvas, or HTML/CSS. |
| Result UX | Show one representative banner, copy/style candidates, download action, and result gallery. |
| Revision loop | Support concise revision requests such as more premium, emphasize discount, shorter copy, or warmer tone. First gate complete through the optional `revision_request` generation field and Streamlit input. |
| API/agent surface | FastAPI remains the core service boundary. A2A/FastMCP should be thin wrappers after the workflow stabilizes. |

## Target Quality And Performance

| Metric | Target |
|---|---|
| API health | Mock/demo backend path passes tests and smoke checks. |
| Latency | Mock path p95 <= 2 seconds; OpenAI path p95 <= 30 seconds; FLUX2/GPU path measured and documented separately. |
| Copy quality | Across 10-20 representative samples: Korean text presence 100%, product-name inclusion >= 90%, prohibited-claim violations 0. |
| Retrieval quality | Retrieval eval set category hit rate >= 80%; prohibited-claims guidance hit rate 100%. |
| Image quality | Product-preservation checklist pass rate >= 80%; Korean overlay rendering failures 0. Deterministic public-sample preservation first gate: pass rate 1.00, minimum top-region pixel match 1.00. Offline visual proxy gate passes 6 committed banners and includes a blank-image negative regression. Offline provider visual review first gate now combines the committed visual proxy, latest paid canary, manual local text review, and postmortem without making a paid API call. Paid OpenAI image-edit gates failed and are documented as model-quality evidence, not hidden. The latest `gpt-image-2`/`medium` canary passed ROI color/hash/edge preservation, script cost guard, and post-calibration text-contamination checks but failed latency. Paid provider-quality image editing remains unproven until latency strategy is resolved and a later gate passes. |
| Error handling | Backend failures map to Korean `AdBackendError`; unknown backend, unsupported reference image, and missing API key fail clearly. |
| Regression guard | `pytest`, `ruff`, API smoke, retrieval eval, and workflow eval commands are documented and reproducible. |

## Non-Functional Completion Criteria

| Axis | Why it matters | Required artifact |
|---|---|---|
| Evaluation | Proves quality instead of relying on visual taste. | `docs/evidence/rag-baseline.md`, eval JSON/summary. |
| Observability | Shows where the workflow is slow or failing. | OTEL trace, Phoenix screenshot, JSONL logs. |
| Deployability | Shows the service can be operated beyond a notebook demo. | Docker Compose, K8s manifests, smoke evidence. |
| Reproducibility | Lets reviewers rerun the same demo. | Sample inputs, fixed outputs, documented commands. |
| Security/privacy | Avoids persisting raw photo, prompt, API response, or secrets. | Redacted trace/log allowlist tests and `.env` guard. |
| Maintainability | Keeps backend swaps and workflow changes controlled. | Backend contract, ADRs, tests, contract reviewer. |
| Cost/operations | Controls paid model calls and runtime failures. | Usage logging, smoke scripts, per-run estimated cost guard, model config. |
| Portfolio evidence | Makes the hiring signal visible. | README, screenshots, architecture diagram, demo gallery. |

## Intermediate Milestones

| Stage | Goal | Completion evidence |
|---|---|---|
| M1 RAG baseline eval | Prove the current keyword retriever is useful before adding vector DB. | Complete: `docs/evidence/rag-baseline.md`, eval JSON, category hit rate 1.00, prohibited-claims hit rate 1.00. |
| M1.5 RAG chunking comparison | Compare chunking strategies before claiming production RAG ingestion quality. | Complete first gate: `docs/evidence/rag-chunking-comparison.md`, whole-document vs field-aware chunks, deterministic local embedding, selected `field_aware`, category hit rate 0.90, prohibited-claims hit rate 1.00, raw inputs absent. |
| M2 Hybrid retrieval | Compare Qdrant/pgvector/Chroma or a no-adoption baseline before choosing. | Complete: `docs/adr/0007-pgvector-marketing-context-retrieval.md`, `docs/evidence/pgvector-retrieval.md`, pgvector hybrid precision 1.00 vs keyword baseline precision 0.75 on the current 10-sample eval set. |
| M3 Service workflow hardening | Make generation observable and resumable enough for real UX. | Complete: Redis/RQ job queue, `/generation-jobs` status API, redacted Postgres history, Korean reference-image async rejection, API tests, Redis/RQ smoke, Postgres history smoke, full containerized API/worker smoke with Triton scorer, and Streamlit polling/history UX. |
| M4 Real product analysis | Replace mock product analysis with a real VLM-backed analyzer while preserving redaction policy. | Complete first analyzer gate: OpenAI Responses Vision adapter, ADR, no-network tests, env/compose wiring, one redacted live smoke, 10-case synthetic reference eval, pass rate 1.00, p95 latency 13.15s. |
| M5 Observability and eval package | Make quality, latency, cost, and failure behavior reviewable. | Complete first gate: Phoenix/OTEL trace screenshots, JSONL logs, `docs/evidence/workflow-eval-summary.json`, deterministic workflow score 1.00, failure_count 0, failure-case report fields, and `docs/evidence/cost-guard-summary.json`. |
| M6 Portfolio packaging | Turn implementation into a senior-reviewable artifact. | Complete first gate: evidence index at `docs/evidence/README.md`, demo gallery at `docs/evidence/demo-gallery.md`, architecture image at `docs/evidence/assets/architecture.svg`, Streamlit reviewer screenshots at `docs/evidence/streamlit-reviewer-flow.md`, demo video storyboard at `docs/evidence/demo-video-storyboard.md`, real-sample preservation evidence at `docs/evidence/real-sample-preservation.md`, paid OpenAI image-edit failure evidence at `docs/evidence/openai-image-edit-preservation.md`, README links, reproducible command map. |
| M7 Adversarial hardening | Apply independent senior-review criticism to remove overclaiming and close the strongest evidence gaps. | In progress: `docs/reference/adversarial-portfolio-review.md` captures findings; live K8s base-stack proof, K8s async overlay smoke, first async reliability matrix, live worker outage/restore smoke, explicit retry/timeout/cancel non-support, 30-scenario product-like eval, offline visual proxy gate, paid provider-quality failure evidence, provider-gate postmortem, one-sample canary CLI, first trace/log privacy allowlist gate, first cost guard, offline text-contamination proxy calibration, post-calibration one-sample paid canary, and offline provider visual review first gate are complete. Next evidence should cover latency strategy/remediation before any provider-quality image-edit claim. |
| M8 Agentic RAG graph | Add the LangGraph control plane without discarding existing workflow evidence. | First gate complete: ADR 0012/0014/0017/0018, `langgraph` and `langgraph-checkpoint-sqlite` dependencies, typed state schema, deterministic planner/tool-suite/retriever/citation/guardrail/worker/reflection/HITL/finalize nodes, conditional approval route, local mock worker route through the existing generation workflow, redacted cited ad package summary, local web/SQL/internal API tool summaries including live web search runtime policy, local SQL runtime policy, and production DB access/audit policy, FastMCP import/tool-call smoke plus loopback-only transport/auth boundary and remote client auth contract, in-memory and local SQLite checkpoint proof, redacted smoke summaries, focused tests, local FastAPI SSE wiring, local SQLite replay summary, local OpenInference graph-node trace proof, local run metrics for latency/token/cost/tool success/failure plus failed-run analysis and redacted graceful fallback summary, local approval API first gate, local reviewer approval UI first gate, same-process post-approval worker resume first gate, mock-only redacted SQLite cross-process resume first gate, retention boundary policy with deployment trace retention contract, and pending decision register. Pending: live web search provider smoke, credentialed production DB connection/audit-retention smoke, production MCP auth provider selection/remote client smoke, live-provider cross-process resume, approved production storage implementation, external trace backend selection/production customer trace capture, and live provider token/cost telemetry. |
| M9 Agentic RAG eval/guardrail gate | Prove answer/ad package faithfulness, citation quality, and tool safety. | First gate complete: 13-case local golden dataset, Ragas-compatible deterministic summary fields, faithfulness/answer relevancy/context precision/context recall proxy scores 1.00, prompt-injection HITL route, 7-tool allowlist/budget tests, redaction checks, fast-gate command, real promptfoo package smoke, reviewer-facing offline eval report, and GitHub Actions CI steps for both the compatibility script and promptfoo package gate. ADR 0016 keeps Ragas live metrics behind paid/API-key approval. Pending: run Ragas live gate only after paid eval approval. |
| M10 Streaming and reviewer approval | Make long-running graph execution reviewable in real time. | First gate complete: ADR 0013/0018, async FastAPI `POST /agentic-rag/runs/stream`, WebSocket `/agentic-rag/runs/ws`, SSE `text/event-stream`, 9 redacted node progress events/messages including local tool suite and worker completion, durable `agr-*` run id, local SQLite replay endpoint, paid-provider approval route tests, bidirectional WebSocket approval/resume, redacted approval decision API summary, Streamlit reviewer approval UI first gate, same-process post-approval worker resume, mock-only redacted SQLite cross-process resume, local failed-run graceful fallback summary, and retention boundary policy. Pending: live-provider cross-process resume, approved production replay/audit storage, and deployment-specific incident/fallback retention states. |
| M11 Cloud/demo packaging | Show deployability beyond local/kind evidence. | In progress: offline Agentic RAG eval report is complete at `docs/evidence/agentic-rag-eval-report.md`; pending decision register is complete at `docs/evidence/agentic-rag-decision-register.md`; demo video storyboard is complete at `docs/evidence/demo-video-storyboard.md`. Pending: one selected AWS/GCP/Azure deployment path, architecture diagram update, and final recorded demo video. |

## Failure Conditions

The project is not portfolio-ready if any of these remain true:

1. It lists many technologies but cannot show measured evaluation, trace, or
   deployment evidence.
2. It claims RAG quality without retrieval metrics and representative examples.
3. It uses vector DB before proving keyword retrieval limitations.
4. It asks an image model to render Korean text instead of deterministic overlay.
5. It lacks job/status, failure recovery, or clear user-facing error behavior for
   slow image generation.
6. It stores raw prompts, raw model responses, customer photos, or secrets in
   persistent traces/logs.
7. MCP/A2A, vLLM, or TensorRT distract from the core product path without a
   benchmark or integration reason.
8. The README shows a demo but not the engineering controls behind it.

## Open Decisions

These decisions still need explicit selection before implementation:

| Decision | Default until decided | Decision standard |
|---|---|---|
| Vector retrieval backend | Decided: pgvector hybrid lane; keyword remains default | Reevaluate if pgvector precision stops beating keyword baseline as the guide corpus grows, or if dedicated vector DB operations become more important than Postgres integration. |
| Queue/history stack | Decided: Redis/RQ plus Postgres redacted history | Reevaluate only if durable queued payloads, complex routing, scheduled retries, or reference-image async storage are required. |
| Real VLM provider | Decided first provider: OpenAI Responses Vision; mock remains default | Reevaluate if latency, cost, parse failures, or image privacy constraints beat the current OpenAI trade-off. |
| Agentic RAG final architecture | Decided: Agentic RAG control plane over existing multimodal workflow | See ADR 0011. Specific library-level implementation decisions still need focused ADRs when candidates are non-trivial. |
| Agent framework implementation | Decided: LangGraph StateGraph for the control plane | See ADR 0012. Reevaluate if privacy-safe checkpointing or production worker integration becomes awkward. |
| Streaming protocol | Decided: SSE first, WebSocket for bidirectional approval when needed | See ADR 0013. Reevaluate if production clients require richer duplex coordination than approval decisions. |
| Durable checkpointing | Decided: local SQLite first gate with `langgraph-checkpoint-sqlite` | See ADR 0014. Reevaluate for Postgres when multi-instance workers, approval audit retention, or cloud persistent storage become required. |
| Agent team operating model | Decided: main writer plus read-only scouts by default; opt-in disjoint writer lanes for large milestones | See ADR 0015. Reevaluate if a milestone splits into 3+ independent implementation lanes. |
| Agent eval stack | Decided: offline promptfoo regression first, optional Ragas live semantic gate | See ADR 0016. Local compatibility gate and real promptfoo package gate are complete and wired into CI; run Ragas only with paid eval approval. |
| Agent tool suite | Decided: local deterministic tool suite first, FastMCP local smoke | See ADR 0017. Live web search runtime policy, local SQL runtime policy, production DB access/audit policy, loopback-only MCP transport/auth boundary, and MCP remote client auth contract first gates are complete; live web search provider smoke, credentialed production DB smoke, production MCP auth provider selection, and remote client smoke require separate runtime/security evidence. |
| Retention boundary | Decided: redacted replay with same-process ephemeral raw context plus mock-only resume policy | See ADR 0018. Deployment trace retention contract is complete for redacted node/status/latency/tool/error/cost attributes. Durable raw request storage, live-provider cross-process resume, production approval audit retention, external trace backend selection, retention above 7 days, and production customer trace capture require explicit user decision. |
| Serving optimization lane | Keep Triton/ONNX proof | Add vLLM/TensorRT/SGLang only with a targeted benchmark and role-specific portfolio reason. |
| MCP/A2A | MCP local smoke added as thin wrapper; A2A remains later | Loopback-only MCP transport/auth boundary and remote client auth contract are defined; promote MCP to production only after auth provider selection and remote client smoke. |

## Final Deliverables

1. `README.md`: Agentic RAG positioning, run commands, architecture image, sample output, and honest proven/pending scope.
2. `src/.../agent_graph/`: LangGraph StateGraph, typed state, conditional edges, checkpointing, reflection/retry, HITL approval, and tool nodes.
3. FastAPI surface: async graph-run endpoint plus SSE/WebSocket streaming endpoint.
4. RAG surface: ingestion, chunking comparison, embeddings, pgvector/hybrid retrieval, citations, and retrieval fallback.
5. Tool suite: web search, SQL query, internal API, document retrieval, and one MCP tool server.
6. `docs/evidence/`: RAG eval, Ragas/promptfoo reports, reviewer-facing Agentic RAG eval report, workflow trace, K8s/Docker validation, evidence index, sample gallery, failed-run analysis.
7. `docs/adr/`: architecture and adoption decisions, including ADR 0011.
8. `tests/`: backend contract, graph state, tool allowlist, prompt injection, retrieval, API, eval, and streaming coverage.
9. `deploy/`: Docker Compose, Kubernetes manifests, and one selected cloud deployment path.
10. Reviewer assets: architecture diagram, demo video storyboard, final demo video, `docs/evidence/agentic-rag-eval-report.md`, and committed representative outputs.

## Final Success Statement

The project is complete when it can be described accurately as:

> A production-grade Agentic RAG system for small-business ad generation: it
> retrieves cited business evidence, orchestrates tools through a typed graph,
> validates structured outputs and guardrails, streams execution state, supports
> human approval, and ships with evaluation, tracing, cost, failure, and
> deployment evidence.

## Next Milestone

The immediate M6 portfolio-packaging gate is complete, but the adversarial
review moved the project into M7 hardening. Live K8s base-stack proof is now
captured, the K8s async overlay smoke is complete, the first async reliability
matrix is complete, the 30-scenario product-like eval is complete, the first
trace/log privacy allowlist gate is complete, the deployment trace retention
contract is complete, the first cost guard is complete, live worker
outage/restore evidence is complete, retry/timeout/cancel non-support and
scoped multi-worker policy are explicit, and the strengthened paid provider-quality image-edit
gate has failed with redacted evidence and an offline postmortem. The remaining
portfolio gap is now latency strategy/remediation. The offline provider visual
review first gate exists, but provider-quality image editing remains unproven.
A one-sample `--sample-slug` canary is available as the narrow paid gate before
any full three-sample iteration, but the next paid spend should be preceded by
an explicit latency strategy.

The next architectural milestone is to extend the local graph/SSE/checkpoint/
trace/run-metrics/reviewer-approval/resume gates plus mock-only redacted
cross-process resume and the retention boundary to live-provider cross-process
resume, approved production storage, production MCP auth provider/remote client
smoke, and provider-backed token/cost telemetry while preserving the current
evidence base. Paid provider-quality image-edit remediation remains a
downstream tool-quality track; the next paid step is a post-calibration
one-sample canary, not a broad full gate.
