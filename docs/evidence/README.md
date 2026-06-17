# Dessert Ad Studio Evidence Index

Date: 2026-06-17

This index maps the repository evidence to the senior portfolio signals behind
Dessert Ad Studio: retrieval quality, workflow reliability, observability,
deployment readiness, privacy boundaries, and model-backed product analysis.

## Quick Reviewer Path

1. Start with the final target:
   [`docs/reference/dessert-ad-studio-final-outcome.md`](../reference/dessert-ad-studio-final-outcome.md)
2. Check the measured evidence in this file.
3. Run the regression gate:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest -q
docker compose config -q
```

Latest local regression snapshot: `261 passed`.

## Evidence Map

| Signal | Evidence | Current result | Reproduce |
|---|---|---|---|
| Retrieval baseline | [`rag-baseline.md`](rag-baseline.md), [`rag-baseline-results.json`](rag-baseline-results.json) | 10 samples, category hit rate 1.00, prohibited-claims hit rate 1.00, precision 0.75 | `.venv/bin/python scripts/eval_marketing_context.py --output docs/evidence/rag-baseline-results.json` |
| Hybrid vector retrieval | [`pgvector-retrieval.md`](pgvector-retrieval.md), [`pgvector-baseline-results.json`](pgvector-baseline-results.json), [`pgvector-db-smoke-results.json`](pgvector-db-smoke-results.json) | pgvector hybrid preserves hit rate 1.00 and improves precision to 1.00 on the current 10-sample set | `.venv/bin/python scripts/eval_pgvector_marketing_context.py --output docs/evidence/pgvector-baseline-results.json` |
| Agentic RAG graph first gate | [`agentic-rag-graph.md`](agentic-rag-graph.md), [`agentic-rag-graph-summary.json`](agentic-rag-graph-summary.json) | Offline LangGraph control plane passed: typed state, local tool-suite node, conditional HITL route, keyword retrieval, 3 citations, 8 approval checkpoints, local mock worker execution, 9 worker checkpoints, retry/reflection test coverage, redacted summary artifact | `.venv/bin/python scripts/agentic_rag_graph_smoke.py --date 2026-06-17 --output docs/evidence/agentic-rag-graph-summary.json` |
| Agentic RAG SQLite checkpoint | [`agentic-rag-sqlite-checkpoint.md`](agentic-rag-sqlite-checkpoint.md), [`agentic-rag-sqlite-checkpoint-summary.json`](agentic-rag-sqlite-checkpoint-summary.json) | Local SQLite checkpointer passed: `langgraph-checkpoint-sqlite`, 8 persisted checkpoints, reopened connection lists 8 checkpoints, worker route completed, raw inputs absent from checkpoint file | `.venv/bin/python scripts/agentic_rag_sqlite_checkpoint_smoke.py --date 2026-06-17 --output docs/evidence/agentic-rag-sqlite-checkpoint-summary.json` |
| Agentic RAG SSE/WebSocket streaming and replay | [`agentic-rag-streaming.md`](agentic-rag-streaming.md), [`agentic-rag-stream-summary.json`](agentic-rag-stream-summary.json), [`agentic-rag-websocket-summary.json`](agentic-rag-websocket-summary.json) | Local FastAPI SSE and WebSocket streams passed: async routes, `text/event-stream`, JSON WebSocket messages, 9 events/messages, durable `agr-*` run id, SQLite replay endpoint, 9 replay checkpoints, node progress through local tool suite and mock worker, paid-provider approval route tests, redacted event/replay payloads | `.venv/bin/python scripts/agentic_rag_stream_smoke.py --date 2026-06-17 --output docs/evidence/agentic-rag-stream-summary.json` |
| Agentic RAG graph trace | [`agentic-rag-trace.md`](agentic-rag-trace.md), [`agentic-rag-trace-summary.json`](agentic-rag-trace-summary.json) | Local OpenInference trace gate passed: 7 LangGraph node spans including `run_tool_suite`, AGENT/TOOL/RETRIEVER/CHAIN/GUARDRAIL span kinds, API stream tracer wiring, redacted attributes only | `.venv/bin/python scripts/agentic_rag_trace_smoke.py --date 2026-06-17 --output docs/evidence/agentic-rag-trace-summary.json` |
| Agentic RAG local tool suite | [`agentic-rag-tools.md`](agentic-rag-tools.md), [`agentic-rag-tools-summary.json`](agentic-rag-tools-summary.json), [`agentic-rag-mcp-server-summary.json`](agentic-rag-mcp-server-summary.json), [`../adr/0017-agentic-rag-tool-suite.md`](../adr/0017-agentic-rag-tool-suite.md) | Local tool-suite first gate passed: planned tools cover document retrieval, web search, SQL query, internal API, citation builder, guardrail check, and generation workflow; web search uses local snapshot, SQL uses allowlisted in-memory SQLite, internal API uses in-process policy preview, FastMCP package import/tool-call smoke passed with `mcp` 1.28.0 | `.venv/bin/python scripts/agentic_rag_tools_smoke.py --date 2026-06-17 --output docs/evidence/agentic-rag-tools-summary.json` |
| Agentic RAG eval and guardrails | [`agentic-rag-eval-guardrail.md`](agentic-rag-eval-guardrail.md), [`agentic-rag-eval-guardrail-summary.json`](agentic-rag-eval-guardrail-summary.json), [`../adr/0016-agentic-rag-eval-runtime.md`](../adr/0016-agentic-rag-eval-runtime.md) | Local Ragas/promptfoo-compatible first gate passed and is wired as a GitHub Actions CI step: 13 golden cases, faithfulness/answer relevancy/context precision/context recall all 1.00, prompt-injection route blocked before worker, 7-tool allowlist/budget passed, raw inputs absent. ADR 0016 selects offline promptfoo package execution next and keeps Ragas live metrics paid/API-key gated; first `npx promptfoo@0.121.17` local attempt exceeded 150s before completion, so package execution is not yet claimed. | `.venv/bin/python scripts/agentic_rag_eval_guardrail.py --date 2026-06-17 --output docs/evidence/agentic-rag-eval-guardrail-summary.json` |
| AI agent team operating model | [`agent-team-operating-model.md`](agent-team-operating-model.md), [`agent-team-fast-gate-summary.json`](agent-team-fast-gate-summary.json), [`../agent-workflow/README.md`](../agent-workflow/README.md) | ADR-backed operating model passed: main writer plus read-only scouts by default, task-lock template, lane fast-gate CLI, paid-provider tripwire lane, dry-run tests | `.venv/bin/pytest tests/test_agent_team_fast_gate.py -q` |
| Async job reliability | [`generation-jobs.md`](generation-jobs.md) | Redis/RQ queue, redacted Postgres history, job status API, Streamlit polling/history UX | See focused test and smoke commands in the evidence note |
| Async reliability matrix | [`async-reliability-matrix.md`](async-reliability-matrix.md), [`async-reliability-matrix.json`](async-reliability-matrix.json) | Burst submit, failure state, queue enqueue failure, duplicate polling, worker startup wait, K8s async smoke, live worker outage/restore, and explicit retry/timeout/cancel non-support evidence passed | `.venv/bin/pytest tests/test_async_reliability.py tests/test_generation_jobs.py::test_generation_worker_waits_for_redis_until_ready tests/test_api.py::test_generation_job_policy_reports_explicit_async_limits tests/test_api.py::test_cancel_generation_job_is_explicit_non_support tests/test_k8s_async_failure_smoke.py -q` |
| AgentOps observability | [`agentops-phoenix.md`](agentops-phoenix.md), [`assets/phoenix-workflow-trace.png`](assets/phoenix-workflow-trace.png), [`assets/phoenix-trace-detail.png`](assets/phoenix-trace-detail.png) | OTEL console smoke, Phoenix OTLP trace export, UI screenshots, trace count verification, trace/log privacy allowlist tests | `WORKFLOW_TRACING=otel WORKFLOW_TRACE_EXPORT=console .venv/bin/python scripts/otel_trace_smoke.py` |
| Workflow eval and failure report | [`workflow-eval-summary.json`](workflow-eval-summary.json) | 3 demo samples, average score 1.00, failure_count 0, failure_cases present | `.venv/bin/python scripts/eval_demo_samples.py --output docs/evidence/workflow-eval-summary.json` |
| Product-like workflow eval | [`product-like-workflow-eval.md`](product-like-workflow-eval.md), [`product-like-workflow-eval-summary.json`](product-like-workflow-eval-summary.json) | 30 product-like scenarios, average score 1.00, failure_count 0 | `.venv/bin/python scripts/eval_product_like_samples.py --output docs/evidence/product-like-workflow-eval-summary.json` |
| Visual quality proxy | [`visual-quality.md`](visual-quality.md), [`visual-quality-summary.json`](visual-quality-summary.json) | Offline proxy passed: 6 committed banner assets, pass rate 1.00, blank-image negative regression covered | `.venv/bin/python scripts/eval_visual_quality.py --output docs/evidence/visual-quality-summary.json` |
| Cost guard | [`cost-guard.md`](cost-guard.md), [`cost-guard-summary.json`](cost-guard-summary.json) | Offline cost estimate passed: `gpt-image-2`, 627 image tokens, estimated cost `$0.01881` under `$0.02`; live image-edit smoke supports `--max-estimated-cost-usd` | `.venv/bin/python scripts/cost_guard_smoke.py --model-id gpt-image-2 --image-total-tokens 627 --max-estimated-cost-usd 0.02 --output docs/evidence/cost-guard-summary.json` |
| Demo gallery | [`demo-gallery.md`](demo-gallery.md), [`demo-gallery-manifest.json`](demo-gallery-manifest.json), [`assets/demo-gallery/`](assets/demo-gallery/) | 3 deterministic reviewer-visible banners generated from the local workflow with Korean overlay rendering | `.venv/bin/python scripts/build_demo_gallery.py --date 2026-06-16` |
| Streamlit reviewer flow | [`streamlit-reviewer-flow.md`](streamlit-reviewer-flow.md), [`assets/streamlit-reviewer-input.png`](assets/streamlit-reviewer-input.png), [`assets/streamlit-reviewer-result.png`](assets/streamlit-reviewer-result.png) | Local reviewer flow shows input form, revision request, generated banner, revised copy, and download action | See the API, Streamlit, and Playwright capture steps in the evidence note |
| Real-sample preservation | [`real-sample-preservation.md`](real-sample-preservation.md), [`real-sample-preservation-results.json`](real-sample-preservation-results.json), [`assets/real-sample-preservation/`](assets/real-sample-preservation/) | 3 public sample photos, pass rate 1.00, minimum top-region pixel match 1.00 for deterministic composition | `.venv/bin/python scripts/build_real_sample_preservation_evidence.py --date 2026-06-16` |
| OpenAI image-edit preservation | [`openai-image-edit-preservation.md`](openai-image-edit-preservation.md), [`openai-image-edit-preservation-live-summary.json`](openai-image-edit-preservation-live-summary.json) | Strengthened paid `gpt-image-2`/`medium` provider-quality gate failed: pass rate 0.00, ROI preservation checks passed, latency/text-contamination/cost guard failed, estimated cost `$0.2658` over `$0.20` budget; script now supports `--sample-slug` one-sample canary before another paid full gate | `.venv/bin/python scripts/openai_image_edit_preservation_smoke.py --reference-set public-samples --sample-slug matcha-pudding --model-id gpt-image-2 --quality medium --max-estimated-cost-usd 0.10 --date 2026-06-17` |
| Provider gate postmortem | [`provider-gate-postmortem.md`](provider-gate-postmortem.md), [`provider-gate-postmortem-summary.json`](provider-gate-postmortem-summary.json) | Offline postmortem complete: root causes are latency threshold exceeded, text-contamination heuristic failed, and cost budget exceeded; ROI preservation checks passed | `.venv/bin/python scripts/analyze_provider_gate_failure.py --input docs/evidence/openai-image-edit-preservation-live-summary.json --output docs/evidence/provider-gate-postmortem-summary.json` |
| Adversarial portfolio review | [`../reference/adversarial-portfolio-review.md`](../reference/adversarial-portfolio-review.md) | Three independent subagents identified overclaiming and converted it into an M7 hardening roadmap | Review-only artifact; no paid/API calls |
| Architecture preview | [`assets/architecture.svg`](assets/architecture.svg) | README-ready architecture image maps UX, workflow, RAG/eval/ops/deploy/privacy layers | `rsvg-convert docs/evidence/assets/architecture.svg -o /tmp/dessert-ad-studio-architecture.png` |
| Kubernetes deployability | [`k8s-deployment.md`](k8s-deployment.md), [`k8s-live-smoke-summary.json`](k8s-live-smoke-summary.json), [`k8s-async-smoke-summary.json`](k8s-async-smoke-summary.json), [`k8s-async-failure-smoke.md`](k8s-async-failure-smoke.md), [`k8s-async-failure-smoke-summary.json`](k8s-async-failure-smoke-summary.json) | Base, GPU, AgentOps, and async overlays render; live `kind` smokes passed base API/Triton `/generate`, async Redis/RQ worker plus Postgres history, and worker outage/restore behavior | `.venv/bin/python scripts/k8s_async_failure_smoke.py --context kind-dessert-ad-studio --namespace dessert-ad-studio --local-port 18082 --timeout 240 --pending-observation-count 3 --poll-interval 2 --summary docs/evidence/k8s-async-failure-smoke-summary.json` |
| OpenAI product analysis | [`product-analysis-openai.md`](product-analysis-openai.md), [`product-analysis-openai-live-summary.json`](product-analysis-openai-live-summary.json), [`product-analysis-openai-eval-results.json`](product-analysis-openai-eval-results.json) | Live smoke passed; 10-case synthetic reference eval pass rate 1.00, p95 latency 13.15s | `.venv/bin/python scripts/openai_product_analysis_smoke.py --eval --eval-count 10 --output docs/evidence/product-analysis-openai-eval-results.json` |

## Decision Records

| Area | ADR |
|---|---|
| Kubernetes evidence path | [`docs/adr/0005-kubernetes-deployment-evidence.md`](../adr/0005-kubernetes-deployment-evidence.md) |
| Keyword retrieval baseline | [`docs/adr/0006-keyword-marketing-context-retrieval.md`](../adr/0006-keyword-marketing-context-retrieval.md) |
| pgvector hybrid retrieval | [`docs/adr/0007-pgvector-marketing-context-retrieval.md`](../adr/0007-pgvector-marketing-context-retrieval.md) |
| Redis/RQ and Postgres history | [`docs/adr/0008-redis-rq-generation-jobs-history.md`](../adr/0008-redis-rq-generation-jobs-history.md) |
| OpenAI vision product analysis | [`docs/adr/0009-openai-vision-product-analysis.md`](../adr/0009-openai-vision-product-analysis.md) |
| Kubernetes live smoke | [`docs/adr/0010-kubernetes-live-deployability-smoke.md`](../adr/0010-kubernetes-live-deployability-smoke.md) |
| Agentic RAG final target | [`docs/adr/0011-agentic-rag-control-plane-final-target.md`](../adr/0011-agentic-rag-control-plane-final-target.md) |
| LangGraph control plane | [`docs/adr/0012-langgraph-agentic-rag-control-plane.md`](../adr/0012-langgraph-agentic-rag-control-plane.md) |
| Agentic RAG run streaming | [`docs/adr/0013-agentic-rag-run-streaming-protocol.md`](../adr/0013-agentic-rag-run-streaming-protocol.md) |
| Agentic RAG durable checkpointer | [`docs/adr/0014-agentic-rag-durable-checkpointer.md`](../adr/0014-agentic-rag-durable-checkpointer.md) |
| Agent team operating model | [`docs/adr/0015-agent-team-operating-model.md`](../adr/0015-agent-team-operating-model.md) |
| Agentic RAG eval runtime | [`docs/adr/0016-agentic-rag-eval-runtime.md`](../adr/0016-agentic-rag-eval-runtime.md) |
| Agentic RAG tool suite | [`docs/adr/0017-agentic-rag-tool-suite.md`](../adr/0017-agentic-rag-tool-suite.md) |

## Privacy And Storage Boundary

- Raw customer photos are excluded from durable evidence artifacts.
- Raw prompts, raw model responses, generated copy text, and secrets are not
  stored in job history or eval summaries.
- Workflow trace/log and image-failure usage log surfaces store reference
  filenames, image paths, and log paths as `has_*` plus `*_sha256` fields.
- OpenAI product-analysis evidence stores only redacted checklist counts,
  booleans, latency, backend/model id, and pass/fail fields.
- AgentOps/Phoenix evidence is scoped to local/demo workflows. Production use
  would require another trace-attribute review before storing customer inputs.

## Next Packaging Polish

- Extend the M8/M10 Agentic RAG first gates from local
  graph/tool-suite/SSE/WebSocket/SQLite/replay/trace proof to reviewer approval UI, production stream
  replay retention policy, Postgres or production storage policy if needed, and
  deployment-specific trace retention policy.
- Do not claim provider-quality image editing from the paid OpenAI gate; the
  latest `gpt-image-2`/`medium` run failed latency, text-contamination, and cost
  checks.
- Treat the provider-gate postmortem and a `--sample-slug` canary as
  preconditions for any further paid full-gate iteration.
- Add human visual review or provider-quality visual statistics before making
  broader generated-asset quality claims.
