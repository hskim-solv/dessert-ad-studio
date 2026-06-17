# Demo Video Storyboard

Date: 2026-06-17

This is the reproducible recording plan for a portfolio demo video. It shows
Dessert Ad Studio as a Production-grade Agentic RAG System for small-business
ad generation while keeping proven and pending scope explicit.

## Recording Boundary

- Actual video file committed: `false`
- Paid API calls required: `0`
- Raw customer data committed: `false`
- Do not claim provider-quality image editing; the paid provider-quality gate
  remains failed and documented.

## Shot List

### 1. Positioning and architecture

- Duration: `20s`
- Visual: Open README and architecture diagram.
- Narration: Dessert Ad Studio is positioned as an Agentic RAG control plane for small-business ad generation, not as a custom image model.
- Evidence:
  - `README.md`
  - `docs/evidence/assets/architecture.svg`
  - `docs/reference/dessert-ad-studio-final-outcome.md`

### 2. Reviewer-facing product flow

- Duration: `25s`
- Visual: Show Streamlit input and generated result screenshots.
- Narration: A reviewer can inspect the request, product image, generated banner, revised Korean copy, and download action.
- Evidence:
  - `docs/evidence/streamlit-reviewer-flow.md`
  - `docs/evidence/assets/streamlit-reviewer-input.png`
  - `docs/evidence/assets/streamlit-reviewer-result.png`

### 3. Representative outputs

- Duration: `20s`
- Visual: Show the committed deterministic demo gallery.
- Narration: The demo gallery proves Korean overlay rendering and repeatable small-business ad scenarios without external API keys.
- Evidence:
  - `docs/evidence/demo-gallery.md`
  - `docs/evidence/assets/demo-gallery/demo-01.png`
  - `docs/evidence/assets/demo-gallery/demo-02.png`
  - `docs/evidence/assets/demo-gallery/demo-03.png`

### 4. Agentic RAG control plane

- Duration: `22s`
- Visual: Show graph, streaming, checkpoint, and replay evidence.
- Narration: LangGraph typed state, conditional HITL routing, local tools, citations, checkpointing, retry/reflection, and run replay are recorded as reproducible first gates.
- Evidence:
  - `docs/evidence/agentic-rag-graph.md`
  - `docs/evidence/agentic-rag-streaming.md`
  - `docs/evidence/agentic-rag-sqlite-checkpoint.md`
  - `docs/evidence/agentic-rag-approval.md`

### 5. Tool suite and retrieval quality

- Duration: `22s`
- Visual: Show tool-suite, RAG baseline, chunking, and pgvector evidence.
- Narration: The system uses document retrieval, local web-search snapshot, allowlisted SQL, internal API policy preview, FastMCP smoke, chunking comparison, and pgvector hybrid retrieval evidence.
- Evidence:
  - `docs/evidence/agentic-rag-tools.md`
  - `docs/evidence/rag-baseline.md`
  - `docs/evidence/rag-chunking-comparison.md`
  - `docs/evidence/pgvector-retrieval.md`

### 6. Evaluation, guardrails, and observability

- Duration: `26s`
- Visual: Show eval report and Phoenix trace screenshots.
- Narration: The reviewer sees golden eval, Ragas-compatible metrics, promptfoo, prompt-injection blocking, tool budgets, raw-input absence, run metrics, and Phoenix/OpenInference trace evidence.
- Evidence:
  - `docs/evidence/agentic-rag-eval-report.md`
  - `docs/evidence/agentic-rag-run-metrics.md`
  - `docs/evidence/agentic-rag-trace.md`
  - `docs/evidence/agentops-phoenix.md`
  - `docs/evidence/assets/phoenix-workflow-trace.png`
  - `docs/evidence/assets/phoenix-trace-detail.png`

### 7. Deployability and reliability

- Duration: `25s`
- Visual: Show Docker/Kubernetes and async reliability evidence.
- Narration: Docker, GitHub Actions, Kubernetes render/live-kind smokes, async worker outage/restore, and explicit retry/timeout/cancel boundaries are documented.
- Evidence:
  - `docs/evidence/k8s-deployment.md`
  - `docs/evidence/async-reliability-matrix.md`
  - `docs/evidence/generation-jobs.md`

### 8. Honest pending scope

- Duration: `20s`
- Visual: Show provider-quality failure, offline provider visual review, and final outcome pending rows.
- Narration: Provider-quality OpenAI image editing is not claimed as proven; the offline provider visual review first gate is reviewer-rubric evidence, not a success claim. live web search provider smoke, credentialed production DB smoke, production MCP auth, cloud deployment, and the final recorded video remain pending.
- Evidence:
  - `docs/evidence/openai-image-edit-preservation.md`
  - `docs/evidence/provider-visual-review.md`
  - `docs/evidence/provider-gate-postmortem.md`
  - `docs/reference/dessert-ad-studio-final-outcome.md`

## Referenced Artifacts

- `README.md`
- `docs/evidence/assets/architecture.svg`
- `docs/reference/dessert-ad-studio-final-outcome.md`
- `docs/evidence/streamlit-reviewer-flow.md`
- `docs/evidence/assets/streamlit-reviewer-input.png`
- `docs/evidence/assets/streamlit-reviewer-result.png`
- `docs/evidence/demo-gallery.md`
- `docs/evidence/assets/demo-gallery/demo-01.png`
- `docs/evidence/assets/demo-gallery/demo-02.png`
- `docs/evidence/assets/demo-gallery/demo-03.png`
- `docs/evidence/agentic-rag-graph.md`
- `docs/evidence/agentic-rag-streaming.md`
- `docs/evidence/agentic-rag-sqlite-checkpoint.md`
- `docs/evidence/agentic-rag-approval.md`
- `docs/evidence/agentic-rag-tools.md`
- `docs/evidence/rag-baseline.md`
- `docs/evidence/rag-chunking-comparison.md`
- `docs/evidence/pgvector-retrieval.md`
- `docs/evidence/agentic-rag-eval-report.md`
- `docs/evidence/agentic-rag-run-metrics.md`
- `docs/evidence/agentic-rag-trace.md`
- `docs/evidence/agentops-phoenix.md`
- `docs/evidence/assets/phoenix-workflow-trace.png`
- `docs/evidence/assets/phoenix-trace-detail.png`
- `docs/evidence/k8s-deployment.md`
- `docs/evidence/async-reliability-matrix.md`
- `docs/evidence/generation-jobs.md`
- `docs/evidence/openai-image-edit-preservation.md`
- `docs/evidence/provider-visual-review.md`
- `docs/evidence/provider-gate-postmortem.md`

## Reproduce

```bash
.venv/bin/python scripts/build_demo_video_storyboard.py \
  --date 2026-06-17 \
  --storyboard-output docs/evidence/demo-video-storyboard.md \
  --summary-output docs/evidence/demo-video-storyboard-summary.json
```

## Remaining Work

Record and commit or link the final demo video only after this storyboard is
used to capture the reviewer flow. Keep the provider-quality image-edit failure
visible in the narration and avoid presenting paid OpenAI image editing as a
proven capability.
