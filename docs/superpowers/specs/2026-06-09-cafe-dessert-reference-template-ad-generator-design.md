# Cafe/Dessert Reference-Template Ad Generator Design

Date: 2026-06-09
Status: Draft approved for advanced-scope planning
Workspace: `/Users/hskim/Desktop/projects/part4`

## 1. Project framing

This project builds a generative AI service that helps small cafe and dessert business owners create advertising content without design expertise or paid creative tools.

The selected MVP direction is a **cafe/dessert reference-template ad generator**. Users upload reference/product images, choose a campaign purpose and visual template, receive generated ad copy, and generate a polished SNS-ready promotional image.

The advanced technical direction adds controllable image generation through a staged pipeline instead of a single free-form prompt.

## 2. Fixed requirements from the course guide

- User: small business owners.
- Purpose: help small business owners create advertising content using generative AI.
- Service output: advertising content such as product images, banners, detail-page visuals, menu images, or ad copy.
- At least one implementation-level function must be delivered.
- The final result should be evaluated as a service, not only as a model demo.
- Evaluation should consider prompt fit, style consistency, response speed, UI usability, service completeness, and controllability.
- Security constraints: do not expose API keys, SSH keys, or other credentials in source control or model conversations.
- Runtime constraints: one provided GCP VM, L4 GPU, disk <= 100GB, OpenAI API budget limit around the course-provided quota.

## 3. Product concept

Working title: **Dessert Ad Studio**

A Streamlit web app for cafe/dessert owners who need fast SNS ad images.

Primary user story:

> As a cafe owner, I upload a dessert or brand mood image, choose a campaign purpose and style template, and receive a ready-to-post square ad image plus short Korean promotional copy.

## 4. MVP user flow

1. User opens the Streamlit app.
2. User selects campaign purpose:
   - new menu launch
   - seasonal event
   - discount/promotion
   - brand awareness SNS post
3. User uploads one or more reference images:
   - product photo
   - store/brand mood photo
   - optional style reference
4. User selects a visual template:
   - cozy cafe
   - minimal premium
   - cute dessert
   - seasonal event
5. User enters optional text constraints:
   - product name
   - price or discount
   - tone: warm, premium, playful, clean
6. System generates 3 Korean ad-copy candidates.
7. User selects or edits one copy candidate.
8. System generates an SNS-ready square ad image.
9. User views result, prompt summary, and download button.
10. System records a generation log for evaluation and debugging.

## 5. Advanced image-generation architecture

The system should not make every advanced technique mandatory on day one. It should expose one consistent service interface and support three backends/stages.

### Stage 1: Reliable API-backed image edit/generation

Purpose: produce a working demo early.

- Use an image-generation API adapter for reference-image-based generation/editing.
- Prefer API-backed generation when GPU setup is unstable or when demo reliability matters.
- Keep request/response logging, prompt templates, and output storage provider-agnostic.

Official OpenAI docs checked on 2026-06-09 indicate:

- The OpenAI Image API supports image generations and edits.
- The Responses API supports image generation as a built-in tool for multi-step or conversational flows.
- GPT Image models support reference/input images for image editing/generation workflows.
- `gpt-image-1.5`, `gpt-image-1`, and `gpt-image-1-mini` are the relevant GPT Image family names shown in current official docs; exact availability and cost must be verified with the project API key before final implementation.

### Stage 2: Local Diffusers FLUX.2 image generation

Purpose: show model-deployment competence on the provided L4 GPU.

Candidate local stack:

- Python
- PyTorch
- Hugging Face Diffusers
- FLUX.2-class local image-generation pipeline when the VM/GPU can support it
- configurable model id through `FLUX2_MODEL_ID`
- API fallback when the full local model is too large or too slow for the L4 VM
- optional CPU/model offload for memory safety

SDXL is no longer the primary model choice for this project. It remains only a fallback/reference ecosystem option because it has broad ControlNet/IP-Adapter examples, but the main plan should present FLUX.2 as the modern local-generation target and keep the exact model id configurable.

This stage should be a backend option, not the only demo path, because the final demonstration must remain reliable even if the L4 VM cannot run the chosen FLUX.2 variant comfortably.

### Stage 2.5: Mandatory Triton helper-model serving

Purpose: satisfy the required model-serving-framework component from the course while avoiding an unrealistic attempt to serve the entire text-to-image diffusion pipeline through Triton.

Mandatory Triton path:

- Export a small ONNX `template_scorer` helper model.
- Serve it from a Triton model repository at `models/template_scorer/1/model.onnx`.
- Use Triton HTTP inference in the FastAPI backend to rank visual templates before image generation.
- Include `/v2/health/ready`, `/v2/models/template_scorer/ready`, and `/v2/models/template_scorer/infer` smoke checks.
- Treat successful Triton inference as a required final acceptance gate.

### Stage 3: Controllable reference/template generation

Purpose: satisfy the user's requested higher technical difficulty.

Candidate controls:

- **Reference/template scoring through Triton**: pick the most suitable ad template before image generation.
- **Image-to-image/reference conditioning**: preserve style or visual identity from a reference image when the selected backend supports it.
- **ControlNet Canny/Depth fallback on SDXL only if needed**: preserve layout/shape guidance from a reference or generated control image if FLUX.2 control support is unstable in the available environment.
- **Inpainting/mask editing**: preserve product area while changing background, typography zone, or decorative context.

Implementation should start with one stable control path, then add the next only if demo quality and speed remain acceptable.

Recommended advanced path order:

1. API-backed reference edit/generation for reliable service demo.
2. Triton ONNX `template_scorer` for mandatory model-serving evidence.
3. Local FLUX.2 backend for modern model-deployment evidence.
4. Reference/template conditioning supported by the selected image backend.
5. SDXL ControlNet/IP-Adapter fallback only if the FLUX.2 path is unavailable on the VM.

## 6. System components

### Streamlit UI

Responsibilities:

- Collect campaign purpose, images, template, tone, product metadata, and optional constraints.
- Preview uploaded images and chosen template.
- Display generated copy and generated image.
- Provide download and retry controls.
- Show generation status and errors in user-friendly Korean.

### Prompt/template engine

Responsibilities:

- Convert user selections into structured prompts.
- Maintain reusable prompt templates per campaign purpose and style.
- Generate separate prompts for:
  - copy generation
  - image generation/editing
  - negative constraints
  - evaluation metadata

### Copy generator

Responsibilities:

- Generate 3 concise Korean ad-copy options.
- Respect tone, product name, event, and target channel.
- Avoid hallucinated unsupported claims.

### Image generation service

Responsibilities:

- Provide a stable interface regardless of backend.
- Support backends:
  - API image adapter
  - local FLUX.2 Diffusers adapter when feasible
  - SDXL fallback adapter only when needed for control examples
  - optional ControlNet/IP-Adapter fallback pipeline
- Save output image, parameters, seed when available, and elapsed time.

### Triton template scorer

Responsibilities:

- Convert the campaign purpose, tone, and selected user constraints into numeric template features.
- Call Triton HTTP inference for `template_scorer`.
- Return template ranking metadata to FastAPI and Streamlit.
- Log Triton latency and readiness status for the final report.

### Evaluation/logging module

Responsibilities:

- Store each generation request and result metadata.
- Track latency, selected template, backend, prompt, image path, and user rating fields.
- Enable later analysis for presentation/report.

## 7. Data and assets

Initial assets should be small and curated:

- 4 visual templates.
- 8-12 sample cafe/dessert reference images for demo fallback.
- 5-10 prompt examples per campaign purpose.
- Optional generated sample outputs for README/report.

Avoid collecting unnecessary personal data. Uploaded images should remain local during prototype development unless the chosen API backend requires upload.

## 8. Error handling and safety

- Missing image: allow text/template-only generation as fallback.
- API quota/error: show actionable message and suggest local backend if available.
- GPU OOM: reduce resolution, enable offload, or fall back to API backend.
- Slow generation: show spinner/progress and log elapsed time.
- Bad output: allow retry with same settings and edited prompt.
- Secrets: `.env` must be ignored; no API key in Git, logs, screenshots, or prompts.
- Copyright/style: do not claim exact brand imitation; frame templates as broad moods.

## 9. Acceptance criteria

The MVP is acceptable when all of the following are true:

1. A user can complete the full flow from input to generated image in the Streamlit UI.
2. The app produces at least one SNS-ready cafe/dessert ad image and three Korean copy candidates.
3. The user can choose a style template and campaign purpose that visibly affect the prompt and output.
4. At least one reference image can influence the generated result.
5. Generation latency and backend choice are logged.
6. Triton serves the ONNX `template_scorer`, and FastAPI can call it successfully in the normal generation path.
7. The app handles missing/failed image generation with a clear fallback or error message.
8. The README explains setup, environment variables, run command, Triton smoke command, and demo flow.
9. The final report/presentation can cite evaluation results across prompt fit, consistency, speed, UI usability, completeness, and controllability.

## 10. Non-goals for MVP

- Multi-user accounts, payments, or persistent cloud database.
- Full menu-board editor.
- Full brand-kit management.
- Production deployment hardening.
- Training a custom LoRA as a required MVP feature.
- Perfect product identity preservation for all arbitrary uploads.

## 11. Stretch goals

Add only after the MVP works end-to-end:

1. Product mask editor for stronger product preservation.
2. ControlNet Canny/Depth mode toggle.
3. IP-Adapter style-reference strength slider.
4. Batch generation of 3 visual variants.
5. Human evaluation dashboard.
6. Short demo video for portfolio use.

## 12. Open decisions before implementation

1. Whether the first image backend should be API, local FLUX.2, or both behind an adapter.
2. Whether to initialize a Git repository in the currently empty `part4` workspace.
3. Exact FLUX.2 model id, precision, and memory settings after checking the provided VM.
4. Exact image API model names/costs after checking the provided project credentials and quota.

## 13. Recommended implementation sequence

1. Create repository skeleton and docs.
2. Build Streamlit UI with mocked copy/image outputs.
3. Add prompt/template engine and local asset structure.
4. Add copy-generation backend.
5. Add image-generation adapter interface.
6. Implement Triton ONNX `template_scorer` and smoke checks.
7. Implement one reliable image backend.
8. Add local FLUX.2 experiment path.
9. Add one advanced control path through reference/template conditioning or SDXL fallback ControlNet.
10. Add logging/evaluation export.
11. Polish README, report outline, and demo script.

## 14. Verification plan

- Unit-level checks:
  - prompt template rendering
  - log schema writing
  - file path/output handling
- Integration checks:
  - Streamlit flow with mocked backend
  - copy generation response shape
  - image backend response shape
- Manual QA:
  - 3 campaign purposes x 2 templates
  - upload valid and invalid images
  - API failure fallback
  - local backend OOM fallback if applicable
- Presentation evidence:
  - before/after examples
  - latency table
  - evaluation rubric table
  - design tradeoff explanation

## 15. Course-material alignment

The provided Part 4 notebooks are now treated as project implementation references:

- 4-3 Streamlit prototype is the primary UI implementation guide.
- 4-4 FastAPI serving is the backend/API boundary guide.
- 4-1 Docker/Kubernetes is the reproducible deployment guide.
- 4-2 model conversion/quantization is a stretch performance/evidence path, not a required SDXL delivery path.
- 4-5 Triton/model-serving framework content is a stretch serving-framework comparison or smoke-test path if an ONNX-compatible artifact exists.

The detailed mapping is stored in `docs/reference/class-materials-alignment.md`.

## 16. Sources consulted

- Course project guide provided by the user: `/Users/hskim/Downloads/[AI] 고급프로젝트 가이드 650fc8105e0d838e920181b4c15e7593.md`
- OpenAI official docs, image generation guide and image API references, checked 2026-06-09.
- Context7 Hugging Face Diffusers docs for SDXL img2img, inpainting, ControlNet, and IP-Adapter, checked 2026-06-09.
