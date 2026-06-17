# Dessert Ad Studio

Small-business ad banner studio for cafe, bakery, and local-store owners.

The app turns a product photo and a short marketing request into Korean ad copy,
a generated or composed visual, and a downloadable banner with deterministic
Korean text overlay.

Final portfolio target: a production-grade Agentic RAG workflow for
small-business ad generation. The current multimodal ad workflow remains the
business domain; the next architecture layer is a typed graph control plane for
retrieval, tool orchestration, guardrails, approval, streaming, eval, trace, and
deployment evidence.

## Problem

Small business owners often need SNS banners, menu images, and promotion copy, but design tools and prompt engineering add friction. A raw image-generation model also tends to distort Korean text, so the service separates visual generation from Korean text rendering.

## What The Demo Does

1. Choose a demo sample or enter a product manually in Streamlit.
2. Generate three Korean ad-copy options through FastAPI.
3. Generate one representative ad visual through the selected image backend.
4. Optionally add a concise revision request such as premium tone, discount emphasis, or shorter copy.
5. Render headline, price, and CTA with a PIL overlay.
6. Download the finished PNG banner.

## Current Verification Scope

Verified:

- Deterministic Korean overlay and demo banner generation.
- Curated marketing retrieval eval plus a measured pgvector storage/query lane.
- Offline LangGraph control-plane first gate with typed state, conditional
  HITL routing, keyword retrieval, citations, checkpoint evidence, local mock
  worker execution, retry/reflection test coverage, and redacted summary
  artifact.
- Docker Compose smoke, Redis/RQ job path, redacted Postgres history, and
  local AgentOps trace evidence.
- Kubernetes manifests that render through Kustomize with probes, ingress, HPA,
  Triton, Streamlit, and AgentOps overlays, plus a live `kind` smoke that
  applied the base stack, synced Triton models, reached pod readiness, and
  passed full API `/generate`.

Known gaps:

- Paid OpenAI image-edit provider gates have failed; the deterministic
  preservation path and offline visual proxy pass, but provider-quality image
  editing is not proven.
- Agentic RAG is still at the offline control-plane stage. Production durable
  checkpointing, API streaming, API wiring, and full agent eval gates are still
  pending.
- Current eval sets are demo-scale and need a larger real/product-like scenario
  matrix before broader quality claims.

## Core Features

- Upload-centered Streamlit Studio UI
- Three reusable demo scenarios
- Korean copy candidates
- Mock Product Analysis by default, with an opt-in OpenAI vision analyzer
- Deterministic Korean banner overlay
- Concise revision-request field for regenerated variants
- Downloadable finished banner
- Backend adapter slots for mock, OpenAI, and FLUX.2
- JSONL generation logging

## Architecture

![Dessert Ad Studio architecture](docs/evidence/assets/architecture.svg)

The core service boundary is FastAPI. Streamlit is the reviewer-facing upload
studio, while retrieval, product analysis, copy/image generation, deterministic
Korean overlay, async state, tracing, evals, and deployment evidence are kept as
separate verifiable layers.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the API:

```bash
uvicorn api.main:app --reload --port 8000
```

## Optional A2A Interoperability Spike

The API exposes a narrow A2A-compatible surface for portfolio interoperability evidence.
It does not replace the normal REST API or the Streamlit UI.

Discovery:

```text
GET /.well-known/agent-card.json
```

Task execution:

```text
POST /message:send
Content-Type: application/a2a+json
```

The supported skill is `generate_ad_banner`. The first message part must contain a JSON
`data` object using the same fields as `POST /generate`.

Run a local smoke test after starting the API:

```bash
python scripts/a2a_smoke.py --base-url http://127.0.0.1:8000
```

Use A2A when another agent needs to discover and call Dessert Ad Studio as a remote
agent capability. Use the normal REST API for app/frontend calls. FastMCP remains a
future tool-server layer for exposing lower-level typed tools.

Run Streamlit:

```bash
streamlit run app/streamlit_app.py
```

Open:

```text
http://localhost:8501
```

The default mock backends work without API keys.

## Demo Scenarios

The Streamlit `데모 샘플` selector includes:

| Scenario | Product | Platform | Goal |
| --- | --- | --- | --- |
| Dessert cafe | 딸기 크림 크루아상 | Instagram feed | New menu launch |
| Bakery | 말차 푸딩 | Instagram story | Seasonal event |
| Flower shop | 봄 플라워 박스 | Smartstore thumbnail | Reservation discount |

Generated assets are written to:

```text
outputs/
outputs/streamlit-banners/
logs/generations.jsonl
```

## Configuration

Copy `.env.example` to `.env` and edit local values. Do not commit `.env`.

| Variable | Values | Default |
| --- | --- | --- |
| `COPY_BACKEND` | `mock`, `openai` | `mock` |
| `PRODUCT_ANALYSIS_BACKEND` | `mock`, `openai` | `mock` |
| `IMAGE_BACKEND` | `mock`, `openai`, `flux2` | `mock` |
| `COPY_MODEL_ID` | any chat model id | `gpt-5.4-mini` |
| `PRODUCT_ANALYSIS_MODEL_ID` | any vision-capable Responses model id | `gpt-5.4-mini` |
| `IMAGE_MODEL_ID` | any GPT image model id | `gpt-image-1-mini` |
| `IMAGE_QUALITY` | `low`, `medium`, `high` | `low` |
| `OPENAI_MAX_ESTIMATED_COST_USD` | optional per-run smoke budget | unset |
| `OPENAI_COPY_INPUT_USD_PER_1M_TOKENS` | optional text input price override | unset |
| `OPENAI_COPY_OUTPUT_USD_PER_1M_TOKENS` | optional text output price override | unset |
| `OPENAI_IMAGE_USD_PER_1M_TOKENS` | optional image token price override | unset |

Real OpenAI backends need `OPENAI_API_KEY` in `.env`.
`PRODUCT_ANALYSIS_BACKEND=openai` sends the product request and optional
reference image to OpenAI through the Responses API with structured output and
`store=False`.

Uploading a reference image in Streamlit switches the OpenAI image backend from text-to-image to edit mode. The `flux2` backend is text-to-image only for now: uploading a reference image with it returns a 400 instead of silently ignoring the photo.

## Tests

```bash
pytest -q
ruff check .
```

## Portfolio Evidence

The senior-review path is collected in
[`docs/evidence/README.md`](docs/evidence/README.md): retrieval evals,
pgvector comparison, async job/history hardening, OTEL/Phoenix traces,
workflow failure reports, Kubernetes render evidence, and OpenAI product
analysis evals. The reviewer-visible result gallery is
[`docs/evidence/demo-gallery.md`](docs/evidence/demo-gallery.md), with
committed PNG banners under
[`docs/evidence/assets/demo-gallery/`](docs/evidence/assets/demo-gallery/).
The Streamlit reviewer flow screenshots are in
[`docs/evidence/streamlit-reviewer-flow.md`](docs/evidence/streamlit-reviewer-flow.md).
Real-sample deterministic preservation evidence is in
[`docs/evidence/real-sample-preservation.md`](docs/evidence/real-sample-preservation.md).
The paid OpenAI image-edit preservation failures and the strengthened
provider-quality gate definition are documented in
[`docs/evidence/openai-image-edit-preservation.md`](docs/evidence/openai-image-edit-preservation.md).
The README architecture image is
[`docs/evidence/assets/architecture.svg`](docs/evidence/assets/architecture.svg).

Rebuild the deterministic gallery:

```bash
python scripts/build_demo_gallery.py --date 2026-06-16
```

Manual smoke:

```bash
python scripts/openai_smoke.py                      # copy + text-to-image
python scripts/openai_smoke.py my_product_photo.jpg # copy + reference edit
python scripts/flux2_smoke.py                       # needs [image] deps
```

## AgentOps Evidence

Run deterministic local evals over the bundled demo samples:

```bash
python scripts/eval_demo_samples.py --output docs/evidence/workflow-eval-summary.json
```

Run a local console trace smoke:

```bash
WORKFLOW_TRACING=otel WORKFLOW_TRACE_EXPORT=console python scripts/otel_trace_smoke.py
```

Run Phoenix locally through the optional compose override:

```bash
python scripts/export_template_scorer_onnx.py
docker compose -f docker-compose.yml -f docker-compose.agentops.yml up --build
```

In another shell, trigger a workflow span through the API smoke. Keep the
default generate step enabled for Phoenix evidence:

```bash
python scripts/api_smoke.py --base-url http://127.0.0.1:8080
```

Open:

```text
Phoenix: http://localhost:6006
```

The override sends API workflow spans to Phoenix through OTLP HTTP at
`http://phoenix:6006/v1/traces`; look for `dessert-ad-studio-api` spans after
the smoke request. Phoenix remains optional; normal local evals, REST calls, and
Streamlit usage do not require it.

## Docker Compose Demo

Generate the ONNX model before starting Triton:

```bash
python scripts/export_template_scorer_onnx.py
docker compose up --build
```

To use `openai` backends in the compose demo, put `OPENAI_API_KEY` and backend overrides in `.env` beside `docker-compose.yml`.

Open:

```text
Streamlit: http://localhost:8501
FastAPI:   http://localhost:8080
Triton:    http://localhost:8000
```

## Kubernetes Deployability Evidence

Kubernetes manifests live under `deploy/k8s`:

```bash
kubectl kustomize deploy/k8s/base
kubectl kustomize deploy/k8s/overlays/gpu
kubectl kustomize deploy/k8s/overlays/agentops
```

The base stack includes FastAPI, Streamlit, Triton, PVCs, NGINX Ingress, health
probes, resource requests/limits, and API HPA. Live `kind` evidence now covers
base apply, Triton model PVC sync, `api`/`app`/`triton` readiness, API
port-forward, and full `/generate` smoke. The AgentOps overlay routes API
workflow traces through OpenTelemetry Collector to Phoenix.

Evidence:

```text
docs/evidence/k8s-deployment.md
```

## Advanced GPU / FLUX.2 Validation

On an NVIDIA GPU machine, start only the API service with the GPU overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d --no-deps api
```

The overlay installs `[image]` extras, switches `IMAGE_BACKEND=flux2`, and sets `REQUIRE_TRITON=0` so template scoring falls back to the local scorer. The first request downloads model weights into the `hf-cache` volume.

Full VM procedure:

```text
docs/runbooks/gcp-flux2-validation.md
```

## Roadmap

1. Extend the Agentic RAG control plane from the offline LangGraph first gate to worker execution, retry/reflection, durable checkpointing, and SSE/WebSocket streaming.
2. Add Ragas + promptfoo golden eval gates, prompt-injection/tool-budget tests, and citation-quality reporting.
3. Implement remediation for the failed paid `gpt-image-2` + `quality=medium` provider-quality gate before any further paid full-gate iteration.
4. Add human visual review or provider-quality visual statistics for generated assets.
5. Keep FastMCP/A2A as optional thin wrappers after the workflow/API evidence is stable.

FastMCP is intentionally deferred. It can later expose the studio as agent-callable tools such as `generate_dessert_ad`, generation log lookup, result retrieval, and template scoring.
