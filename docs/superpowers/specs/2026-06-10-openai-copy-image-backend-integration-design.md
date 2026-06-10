# OpenAI Copy/Image Backend Integration Design

Date: 2026-06-10
Status: Approved
Workspace: `/Users/hskim/Desktop/projects/part4`
Builds on: `docs/superpowers/specs/2026-06-09-cafe-dessert-reference-template-ad-generator-design.md`

## 1. Goal

Replace the deterministic mock generation paths with real generative backends so the
service produces actual Korean ad copy and actual SNS ad images end-to-end.

This round implements Stage 1 of the parent spec (reliable API-backed generation).
The local FLUX.2 path (Stage 2) stays deferred to a later round on the GCP L4 VM,
but this design prepares the seam it will plug into.

## 2. Decisions locked during brainstorming

| Decision | Choice |
| --- | --- |
| Scope | Both copy (LLM) and image generation, in one round |
| Image strategy | API-first via OpenAI GPT Image; FLUX.2 deferred to a later VM round |
| Reference image | Included — edit mode when an upload is present, text-to-image otherwise |
| Default copy model | GPT-5.4 Mini (env-configurable) |
| Default image model | gpt-image-1-mini (env-configurable) |
| API key | Personal key during development, swapped to the team key later via env only |
| Architecture | Separate copy-backend and image-backend adapters selected independently |
| Fallback policy | No silent mock fallback on API failure; explicit actionable errors |

Rejected approaches:

- **Single combined OpenAI backend class**: minimal refactor now, but couples copy
  and image switching and forces the adapter split anyway when FLUX.2 arrives.
- **Responses API integrated copy+image call**: shortest code, but breaks the
  backend-adapter story, weakens serving-architecture evidence for the course, and
  obscures cost control.

## 3. Architecture

### Backend protocols

New `src/dessert_ad_studio/backends/base.py`:

- `CopyBackend` protocol: `name: str`, `generate_copy(request) -> list[CopyOption]`
- `ImageBackend` protocol: `name: str`,
  `generate_image(request, image_prompt, reference_image: bytes | None) -> str`
  (returns saved image path)

`MockAdBackend` already satisfies both protocols and stays one class registered on
both sides. `Flux2Backend` keeps its current behavior; its `generate_image`
signature gains the optional `reference_image` parameter (accepted and ignored this
round) so it satisfies the protocol and stays a drop-in image backend later.

### New implementations

- `src/dessert_ad_studio/backends/openai_copy.py` — `OpenAICopyBackend`
  - Sends the existing `build_copy_prompt()` text as the user message; the role
    definition (including the no-exaggerated-claims constraint) moves to the system
    message.
  - Uses OpenAI Structured Outputs (JSON schema) to force exactly three options of
    headline/body/call_to_action, eliminating parse failures.
  - Model from `COPY_MODEL_ID`, default GPT-5.4 Mini.
- `src/dessert_ad_studio/backends/openai_image.py` — `OpenAIImageBackend`
  - Reference image present: image edit call. Absent: image generation call.
  - Model from `IMAGE_MODEL_ID`, default gpt-image-1-mini; `IMAGE_QUALITY` env
    (default `low`) keeps development iterations cheap and is raised for demo shots.
  - Decodes the base64 response, saves a PNG under `OUTPUT_DIR`, returns the path —
    the same output contract as the mock backend.

### Backend selection

In `api/main.py`:

- `COPY_BACKEND` env: `mock | openai` (default `mock`)
- `IMAGE_BACKEND` env: `mock | openai | flux2` (default `mock`)
- Defaults keep the test suite hermetic (no network); real runs enable `openai` in
  `.env`.
- Backend instances are created once per process (lazy singleton) so the OpenAI
  client is reused.

### Configuration additions (`.env.example`)

```bash
OPENAI_API_KEY=          # personal key during dev; team key later
COPY_BACKEND=mock        # mock | openai
COPY_MODEL_ID=gpt-5.4-mini
IMAGE_BACKEND=mock       # mock | openai | flux2
IMAGE_MODEL_ID=gpt-image-1-mini
IMAGE_QUALITY=low        # raise for final demo shots
```

Exact model id strings must be verified against the live API at implementation time
(course-guide display names may differ from API ids).

## 4. Data flow and schema changes

### Reference image transport

1. Streamlit encodes the uploaded file bytes as base64 into the existing JSON
   request as `reference_image_b64` (endpoint stays JSON; no multipart migration).
2. FastAPI decodes and validates: Pillow open check, format png/jpg/webp, size cap
   10MB on the decoded bytes. Validation failure returns 400 with a specific Korean
   message.
3. Validated bytes flow to `ImageBackend.generate_image(..., reference_image=...)`.
   The mock image backend draws a "REF" badge when a reference is present so the
   full pipeline is provable in tests without any API call.

### Schema changes (`schemas.py`)

- `GenerationRequest`: remove `reference_image_path` (decorative filename only);
  add `reference_image_b64: str | None` and `reference_image_name: str | None`
  (logging).
- `GenerationResponse`: add `copy_backend: str` and `used_reference: bool`,
  symmetric with the existing `image_backend`.

### Prompts

- Copy: reuse `build_copy_prompt()`; system/user split as described above.
- Image: reuse `build_image_prompt()`; in edit mode prepend an instruction to
  preserve the uploaded product photo while styling it as an ad.

### Logging

Extend the JSONL generation log with `copy_backend`, `copy_model_id`,
`image_model_id`, `used_reference`, and copy-call token usage. This feeds the $30
quota monitoring and the latency/cost tables in the final report.

## 5. Error handling

- Missing `OPENAI_API_KEY` with an openai backend selected: 503 on first request
  with an explicit "API key not configured" message. No silent fallback.
- API failures (quota exceeded, rate limit, content policy refusal): FastAPI maps
  each cause to a Korean actionable message (503/422); Streamlit displays it. No
  automatic mock fallback — fake results must never look real during a demo.
- Timeouts: OpenAI client timeout 120s, matching the existing Streamlit httpx 120s;
  spinner text explains that image generation can take tens of seconds.
- Bad reference image (corrupt, oversized, wrong format): 400 with the specific
  reason.
- Triton path unchanged: `REQUIRE_TRITON` gate and template_scorer flow stay as-is.

## 6. Testing

- **Unit (no network)**: both OpenAI backends accept an injected SDK client; tests
  inject fakes returning canned JSON / base64 to verify parsing, saving, and the
  edit-vs-generate branch. Existing tests pass unchanged because defaults stay
  `mock`.
- **Plumbing**: round-trip `reference_image_b64` and assert the mock backend's
  "REF" badge proves delivery; invalid base64 and oversized payloads return 400.
- **Manual real-API smoke**: new `scripts/openai_smoke.py` makes one copy call and
  one cheap image call, printing token usage and elapsed time. Excluded from
  pytest/CI for cost control; documented in the README as a manual step.

## 7. Acceptance criteria

All four must work in Streamlit with a real key:

1. Three Korean ad-copy candidates are generated by the LLM.
2. An ad image is generated without a reference image (text-to-image).
3. An uploaded reference image visibly influences the generated ad image (edit).
4. The JSONL log records backend names, model ids, token usage, and latency.

Plus: `pytest -q` passes without network access, and the Triton smoke flow is
unaffected.

## 8. Non-goals this round

- FLUX.2 execution or VM verification (next round; the image-backend slot is ready).
- Local reference conditioning (IP-Adapter/ControlNet) — separate topic.
- GCP VM deployment and team-accessible hosting.
- Automatic fallback chains between backends.
- Copy regeneration/editing UX changes in Streamlit beyond wiring the new fields.

## 9. Open items for implementation

1. Verify exact API model id strings for GPT-5.4 Mini and gpt-image-1-mini.
2. Verify the current image-edit endpoint parameter shape for gpt-image-1-mini
   (image input encoding, quality/size params) against official docs.
3. Confirm the personal-key quota is sufficient for the smoke script before running
   repeated image calls.
