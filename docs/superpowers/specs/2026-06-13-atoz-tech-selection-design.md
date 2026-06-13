# A-to-Z Technology Selection Design

- Date: 2026-06-13
- Status: approved in chat for documentation
- Project: Dessert Ad Studio
- Primary goal: hiring-oriented portfolio strength
- Secondary goals: real-service posture, current technology fit, assignment completion

## Context

Dessert Ad Studio is positioned as a small-business ad content creation service, not as an image-generation model research project. The current implementation already has:

- Streamlit upload-centered studio UI
- FastAPI `/generate` API
- mock, OpenAI, and FLUX.2 image/copy backend slots
- deterministic Korean text overlay with PIL
- mock product analysis response for the future VLM flow
- Triton/ONNX template scorer proof
- Docker and Docker Compose
- Kubernetes manifests with health/readiness/metrics work already started
- JSONL generation logging

The next decisions should improve the story:

> A product-photo-preserving multimodal ad generation service with controlled agent workflow, measurable quality, and production deployment evidence.

## Design Principles

1. Prefer service reliability evidence over model novelty.
2. Prefer controlled workflows over unconstrained autonomous agents.
3. Separate visual generation from Korean text rendering.
4. Keep product preservation as a first-class quality target.
5. Add tools only when they produce demonstrable portfolio evidence.
6. Preserve the existing FastAPI/Triton/Docker/K8s direction unless a replacement has a measurable benefit.

## Technology Decision Matrix

| Area | Current state | Candidate options | Decision | Rationale |
| --- | --- | --- | --- | --- |
| Product framing | Small-business ad banner studio | broaden to generic image generator, stay local ad service | Keep local ad service | Best fit for assignment and portfolio: concrete user, concrete workflow, concrete evaluation. |
| Agent workflow | Planned pipeline only | LangGraph, OpenAI Agents SDK, PydanticAI, CrewAI, AutoGen, custom step runner | Add LangGraph-style typed workflow next | Strong hiring signal and fits deterministic multi-step flow. OpenAI Agents SDK/PydanticAI stay as simpler alternatives. |
| Agent autonomy level | API calls backend adapters directly | free-form agent, fixed graph, hybrid planner | Use fixed graph with typed state | More controllable and easier to evaluate than letting an LLM choose every step. |
| RAG | planned lightweight marketing guidance | Chroma, Qdrant, pgvector, Milvus, Pinecone, LlamaIndex, LangChain | Add small Qdrant or local Chroma-backed RAG with reranking; Qdrant preferred for production story | RAG should improve copy quality and policy grounding, not become a large subsystem. Hybrid retrieval plus reranking is the strongest version if time allows. |
| RAG evaluation | none | Ragas, DeepEval, LangSmith evals, custom pytest fixtures | Add DeepEval/Ragas-style eval harness | Evaluate retrieval relevance, context grounding, copy quality, and policy safety separately. |
| Observability | JSONL generation logs, `/metrics` | OpenTelemetry GenAI/MCP semantic conventions, OpenInference, Langfuse, Phoenix, LangSmith, Prometheus/Grafana | Add OpenTelemetry + OpenInference-style instrumentation with Langfuse or Phoenix after workflow exists | Agent/tool/RAG trace standardization is a high-value hiring signal. Keep JSONL as fallback/local audit log. |
| Async backend | synchronous generation path | FastAPI BackgroundTasks, RQ, Celery, Dramatiq, Redis Streams | Add Redis + RQ first, Celery if stronger production signal is needed | Image generation is long-running. A `202 Accepted -> job status -> artifact` flow is more service-like. |
| LLM gateway | direct backend selection by environment variables | LiteLLM Gateway, Portkey, OpenRouter, custom router | Add LiteLLM only when multiple text/eval model providers are active | Useful for fallback, routing, budget tracking, and cost attribution, but premature while the default mock/OpenAI paths are enough. |
| Serving | Triton/ONNX template scorer; OpenAI/FLUX.2 backends | vLLM, SGLang, TensorRT, TensorRT-LLM, KServe, Ray Serve, BentoML | Keep Triton/ONNX; add vLLM only as optional LLM/VLM lane; TensorRT only as benchmark | Triton already proves model serving. Extra serving stacks should not dilute the architecture without measurable evidence. |
| Image pipeline | OpenAI reference edit; FLUX.2 text-to-image only | rembg, SAM/SAM2, IP-Adapter, ControlNet, ComfyUI, Diffusers, Qwen-Image/Qwen-Image-Edit, PIL composition | Add product segmentation/compositing before more model serving; keep Qwen-Image as an experiment candidate | The business-critical quality is product preservation. Product cutout/composite plus Korean overlay is more valuable than pure t2i novelty. |
| Korean text rendering | PIL overlay | diffusion-rendered text, Canvas, HTML/CSS rasterization, PIL | Keep deterministic overlay | Diffusion text rendering remains unreliable for Korean ad copy. Overlay separation is a strong engineering decision. |
| Deployment | Docker, Compose, K8s manifests | Nginx Ingress, Helm, Kustomize, Argo CD, Terraform, KEDA/HPA | Add Ingress + Helm + Prometheus/Grafana first; KEDA after queue; Argo CD/Terraform later | This gives visible deployment skill without turning the project into a platform project. |
| Storage | local outputs/logs | SQLite, PostgreSQL, S3, MinIO, Redis | Add Redis for jobs; keep local files for MVP artifacts; add S3/MinIO or PostgreSQL only when history/user state is built | Avoid premature database work. Storage should support generated assets and reproducible history when needed. |
| Security/guardrails | basic schemas | prompt injection checks, tool allowlist, ad policy checker, audit log, secrets hygiene, container scanning | Add small policy checker + allowlisted tools + audit trail | Strong AI-agent engineering signal with low scope if kept schema-driven. |
| Tool protocol | FastMCP deferred | FastMCP, MCP, OpenAI MCP tools | Add later after workflow/eval/queue | FastMCP is useful as an agent-callable facade, but should wrap stable functions rather than precede them. |
| Agent interoperability | not implemented | A2A, ADK A2A bridge, custom webhook facade | Add narrow A2A spike after the workflow contract is stable | A2A is worth trying as portfolio evidence for agent-to-agent interoperability, but it should expose one finished service capability rather than reshape the core architecture. |
| UI/UX | upload studio and demo samples | brand kit, multi-size export, rating loop, platform presets, creative scoring | Add platform presets + rating feedback loop before complex brand kit | These features make the service feel real and help evaluation/presentation. |

## Recommended Build Order

### Phase 1: Controlled Agent Core

Add a typed workflow around the existing generation path:

```text
Input validation
  -> product analysis
  -> marketing brief
  -> RAG guidance lookup
  -> copy generation
  -> image prompt generation
  -> image generation
  -> Korean overlay
  -> result evaluation
```

Expected evidence:

- typed state schema
- step-level logs
- golden workflow tests
- before/after architecture diagram

### Phase 2: Evaluation and Observability

Add quality gates and traceability:

- copy quality checklist
- product preservation checklist
- RAG context relevance and faithfulness checks
- latency and cost logging
- OpenTelemetry traces exported to Langfuse or Phoenix

Expected evidence:

- sample trace screenshot or exported trace
- eval report for demo scenarios
- failure-case report and regeneration reason

### Phase 3: Async Service Path

Add job-oriented API:

```text
POST /jobs
  -> 202 Accepted + job_id
GET /jobs/{job_id}
  -> queued/running/succeeded/failed + progress
GET /jobs/{job_id}/artifact
  -> final PNG
```

Use Redis + RQ first unless Celery is selected for stronger production framing.

Expected evidence:

- API smoke test
- job failure/retry behavior
- queue metrics
- optional SSE or polling progress UI

### Phase 4: RAG and Guardrails

Add small, explicit marketing guidance:

- industry guides for cafe, bakery, flower shop, restaurant, beauty salon
- platform rules for Instagram, Smartstore, menu images, delivery apps
- prohibited or risky claims
- seasonal promotion templates

Use Qdrant when production signal is prioritized. Chroma is acceptable for local-first MVP, but the spec should state migration criteria.

Expected evidence:

- retrieved sources shown in logs or UI
- no-context fallback behavior
- malicious or irrelevant retrieved document tests

### Phase 5: Deployment Evidence

Build on the existing Docker/K8s work:

- Nginx Ingress
- Helm chart or Kustomize overlay
- Prometheus/Grafana dashboard
- HPA baseline
- KEDA only after Redis queue exists
- Argo CD/Terraform only as a stretch target

Expected evidence:

- `docker compose` smoke
- `kubectl` deploy/runbook
- dashboard screenshot or exported dashboard JSON
- rollback/redeploy notes

### Phase 6: A2A Interoperability Spike

Add a thin A2A-compatible facade around one stable service capability:

```text
A2A AgentCard
  -> generate_ad_banner task
  -> existing FastAPI/workflow path
  -> job status or final artifact URL
```

This is not a replacement for FastAPI, Streamlit, FastMCP, or the internal workflow. It is a narrow interoperability proof that another agent can discover the studio's capability and request an ad-generation task through an A2A-compatible surface.

Expected evidence:

- AgentCard or equivalent capability metadata
- one happy-path client smoke test
- failure response for invalid inputs
- short README section explaining when to use A2A versus FastMCP

## Deferred or Rejected Choices

| Technology | Decision | Re-evaluation trigger |
| --- | --- | --- |
| FastMCP | Defer | Workflow functions are stable and worth exposing as tools. |
| A2A | Narrow spike | The workflow exposes one stable service-level capability that can be wrapped as an interoperable agent task. |
| OpenInference | Add with observability | Workflow spans, model calls, tool calls, retrieval, and reranking need portable trace semantics. |
| LiteLLM Gateway | Conditional | At least two active text/eval providers need routing, fallback, budgets, or per-provider cost attribution. |
| Qwen-Image/Qwen-Image-Edit | Experiment only | A product-editing or text-rendering comparison is useful, while deterministic Korean PIL overlay remains the default production path. |
| vLLM | Defer | Self-hosted LLM/VLM lane is needed for copy/eval or API dependency reduction. |
| SGLang | Defer | Structured-generation serving becomes a measurable bottleneck or research focus. |
| TensorRT/TensorRT-LLM | Benchmark only | A GPU benchmark can show latency/cost improvement over baseline. |
| KServe | Defer | Multiple model servers or Kubernetes-native model lifecycle becomes necessary. |
| Ray Serve | Defer | Python-native multi-model serving graph becomes more important than FastAPI simplicity. |
| BentoML | Defer | Model packaging/deployment abstraction becomes the main portfolio story. |
| Full custom diffusion training | Reject for MVP | Project shifts from service portfolio to model research. |
| Diffusion-rendered Korean text | Reject for MVP | A specialized text rendering model is explicitly selected and verified. |
| SQLite as primary production DB | Reject | Only use as local dev cache or single-user demo persistence. |

## Source Notes

Research signals used for this decision:

- LangGraph durable workflow, state, persistence, and production-oriented agent orchestration: https://docs.langchain.com/oss/python/langgraph/overview
- OpenAI Agents SDK orchestration and guardrails as a simpler alternative: https://openai.github.io/openai-agents-python/agents/
- MCP/FastMCP tool-layer fit: https://modelcontextprotocol.io/docs/learn/server-concepts
- A2A official protocol documentation: https://a2a-protocol.org/latest/
- Google ADK with A2A documentation: https://adk.dev/a2a/
- Google MCP, ADK, and A2A codelab: https://codelabs.developers.google.com/codelabs/currency-agent
- Qdrant hybrid retrieval and reranking: https://qdrant.tech/documentation/advanced-tutorials/reranking-hybrid-search/
- Ragas evaluation concepts: https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/
- DeepEval RAG and CI-oriented evaluation: https://deepeval.com/docs/getting-started-rag
- OpenTelemetry GenAI observability: https://opentelemetry.io/docs/what-is-opentelemetry/
- OpenTelemetry MCP semantic conventions: https://opentelemetry.io/docs/specs/semconv/gen-ai/mcp/
- OpenInference instrumentation: https://github.com/Arize-ai/openinference
- LiteLLM gateway and routing: https://docs.litellm.ai/docs/
- KEDA Prometheus scaler and event-driven autoscaling: https://keda.sh/docs/2.21/scalers/prometheus/
- Kubernetes HPA: https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/
- NGINX Ingress: https://kubernetes.github.io/ingress-nginx/deploy/
- Helm charts: https://helm.sh/docs/topics/charts/
- Argo CD GitOps: https://argo-cd.readthedocs.io/en/stable/
- Triton inference server: https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/
- vLLM production metrics: https://docs.vllm.ai/en/stable/usage/metrics/
- RAG empirical evaluation: https://consensus.app/papers/an-empirical-evaluation-of-retrieval-reranking-and-elkiran-rasheed/7a0393178d7e5451ae02d0e57b8d12f6/
- Hybrid RAG with BM25, dense retrieval, reranking, and LangGraph: https://consensus.app/papers/hybrid-retrieval-augmented-generation-reliable-and-dalali-zeguendry/feee2238b5675e1a91d4ad82523dc629/
- IP-Adapter reference-image conditioning: https://arxiv.org/abs/2308.06721
- Qwen-Image model and Qwen-Image-Edit candidate: https://huggingface.co/Qwen/Qwen-Image and https://huggingface.co/Qwen/Qwen-Image-Edit
- TextDiffuser and AnyText text-rendering limitations/alternatives: https://arxiv.org/abs/2305.10855 and https://arxiv.org/abs/2311.03054

## Acceptance Criteria for This Design

- The next implementation plan starts with workflow/eval/async service evidence, not another model-serving migration.
- FastMCP remains explicitly preserved as a later tool-server layer.
- A2A is included as a narrow interoperability spike, not a core rewrite or replacement for FastAPI/FastMCP.
- OpenInference and OpenTelemetry GenAI/MCP semantic conventions are the preferred observability implementation detail.
- LiteLLM Gateway and Qwen-Image/Qwen-Image-Edit are recorded as conditional experiment candidates, not immediate dependencies.
- Triton/ONNX remains the concrete serving proof unless a benchmark justifies change.
- RAG is scoped to marketing guidance and policy grounding, not a broad knowledge platform.
- Deployment work emphasizes visible operator evidence: Ingress, Helm/Kustomize, metrics, dashboard, and runbook.
