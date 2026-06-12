# Demo Samples, Gallery, and README Design

- Date: 2026-06-12
- Status: User approved
- Project: Dessert Ad Studio
- Phase: Phase 1, real-user demo flow polish

## 1. Goal

Make Dessert Ad Studio understandable and demoable within a few minutes.

The evaluator should be able to open Streamlit, choose a prepared small-business scenario, generate a representative Korean ad banner, and understand from the README what problem the service solves and how the AI pipeline is structured.

This phase builds on the completed Upload Studio work:

- Wide two-column Streamlit UI
- Mock Product Analysis
- Korean PIL text overlay
- Downloadable completed banner
- Existing FastAPI `/generate` flow

## 2. Recommended Approach

Use approach A: **sample scenarios + lightweight gallery/readme polish**.

Add reusable demo sample data, expose it in the Streamlit input panel, and rewrite the README around the product story and evaluator flow. Do not add real VLM, RAG, segmentation, or true multi-image generation in this phase.

## 3. In Scope

- Add three demo scenarios:
  - Dessert cafe / strawberry cream croissant / new menu launch
  - Bakery or dessert shop / matcha pudding / seasonal event
  - Flower shop or restaurant / promotion scenario
- Add a `데모 샘플` selector to the Streamlit input panel.
- Keep `직접 입력` as the default option.
- When a sample is selected, prefill:
  - product name
  - campaign purpose
  - tone
  - visual template
  - price or promotion
  - extra request
- Keep file upload manual. The app must not try to auto-upload local images because browser upload requires user action.
- Keep the existing generation, overlay, saved-result, and download flow.
- Add a small reusable sample-data module.
- Rewrite README into a portfolio/evaluator-oriented structure.
- Mention where screenshots and generated outputs are stored.

## 4. Out of Scope

- Real VLM integration.
- Real RAG or vector database.
- Product segmentation/background removal.
- Actual three-image generation.
- FastMCP.
- New frontend framework.
- New persistent database.

## 5. Data Model

Create `src/dessert_ad_studio/demo_samples.py`.

Define:

- `DemoSample`, a frozen dataclass.
- `DEMO_SAMPLES`, a tuple of at least three samples.

Fields:

- `label: str`
- `business_type: str`
- `platform: str`
- `product_name: str`
- `campaign_purpose: CampaignPurpose`
- `tone: Tone`
- `template_hint: TemplateHint`
- `price_text: str`
- `user_constraints: str`

The module should not import Streamlit. It may import schema type aliases from `dessert_ad_studio.schemas`.

## 6. Streamlit UI

Add a sample selector near the top of the left input column.

Options:

- `직접 입력`
- one option per sample label

Behavior:

- `직접 입력` uses the current default values.
- Selecting a sample changes the default values used by the form widgets.
- Manual edits after selecting a sample remain possible.
- Uploaded image behavior remains unchanged.
- The API payload still uses `GenerationRequest` and `request.model_dump()`.
- Result rendering still uses the existing saved-result and overlay flow.

The result area does not need a separate static gallery in this phase. It is enough that choosing a sample and generating produces a polished result. README can point to `outputs/` and Playwright screenshots as evidence artifacts.

## 7. README Structure

Rewrite README around evaluator comprehension:

1. Project one-liner
2. Problem definition
3. What the demo does
4. Core features
5. Architecture
6. Quick start
7. Run API and Streamlit
8. Demo scenarios
9. Configuration and backend options
10. Tests and smoke checks
11. Advanced GPU / FLUX.2 validation
12. Roadmap

Keep existing setup, backend, OpenAI, Docker, Triton, and GCP/Flux2 details, but move advanced material below the quick demo path.

## 8. Tests

Add `tests/test_demo_samples.py`.

Test cases:

- There are at least three demo samples.
- Sample labels are unique.
- Every sample can be converted into a valid `GenerationRequest`.
- `business_type`, `platform`, and `user_constraints` are non-empty.

Streamlit browser E2E is out of scope for automated tests. Manual smoke after implementation should still open Streamlit and verify the sample selector appears.

## 9. Acceptance Criteria

- Streamlit shows `직접 입력` plus at least three demo sample choices.
- Selecting each sample prefills the form with that scenario.
- Existing generation, overlay, download, and saved-result behavior still works.
- README explains the service, demo flow, architecture, scenario set, setup, and roadmap clearly.
- `pytest -q` passes.
- `ruff check .` passes.
- Manual Streamlit smoke confirms the sample selector is visible.

## 10. Follow-Up

- Add real uploaded sample images once appropriate rights/ownership are clear.
- Add a static result gallery after sample artifacts are intentionally curated.
- Replace Mock Product Analysis with real VLM analysis.
- Add lightweight RAG copy guidance.
- Add product-preserving segmentation/composition.
- Add FastMCP only as a later agent-callable integration layer.
