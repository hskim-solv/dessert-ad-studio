# Upload Studio Demo Quality Design

- Date: 2026-06-12
- Status: User approved
- Project: Dessert Ad Studio
- Scope: Streamlit demo quality upgrade for the upload-centered product-preserving ad banner flow

## 1. Goal

This round improves the live demo experience for Dessert Ad Studio. The project should present itself as a service for small business owners, not as an image-model research demo.

The target demo promise is:

> A store owner uploads one product photo and a short marketing request, then receives a service-ready ad banner preview, Korean ad copy, and a downloadable result.

The primary product direction is "소상공인을 위한 제품 사진 보존형 AI 광고 배너 생성 서비스." FastMCP, real VLM integration, real RAG, and true three-image generation remain useful follow-up work, but they are outside this round.

## 2. Decisions

| Topic | Decision | Rationale |
| --- | --- | --- |
| Demo priority | Upload-centered single-screen Studio | Shows the core promise directly: one photo in, usable ad asset out. |
| Layout | Two-column Streamlit Studio | Keeps inputs and outputs visible together during the demo. |
| Generated image count | Keep backend at one generated image | Avoids API/schema churn, higher cost, and longer latency. |
| "Three banner" feel | Use one representative banner plus copy/style variant slots | Preserves demo polish without pretending to generate three real images. |
| Product analysis | Mock Product Analysis | Prepares the VLM story without claiming real VLM behavior. |
| Korean text | Render via deterministic overlay | Avoids broken Korean text from image models and creates a stronger portfolio point. |
| Implementation locus | Streamlit UI plus small reusable helpers | Improves demo quality without large backend changes. |

## 3. In Scope

- Change `app/streamlit_app.py` from a centered form into a wide, two-column Studio UI.
- Keep the existing `/generate` request and response contract.
- Show uploaded product image preview in the input panel.
- Show a deterministic `Demo product analysis` result after generation.
- Show a representative completed banner made by overlaying Korean text on the generated image.
- Provide a download button for the overlaid banner image.
- Keep original generated image, template ranking, backend information, elapsed time, and prompt summary in expanders.
- Add a small helper module, likely `src/dessert_ad_studio/banner_overlay.py`, for image overlay and mock analysis logic.
- Add focused helper tests for overlay output and mock analysis.

## 4. Out of Scope

- FastMCP server or MCP tools.
- Real VLM/Qwen2.5-VL integration.
- Real RAG, vector DB, LlamaIndex, or LangChain integration.
- API schema expansion for product analysis, variants, or banner paths.
- Celery, Redis, or long-running job orchestration.
- Real three-image generation.
- React, Next.js, Gradio, or other UI framework migration.

## 5. UI Structure

Set Streamlit page config to `layout="wide"` and use two columns.

Left column, about 35-40% width:

- Product photo uploader with preview.
- Product name input.
- Campaign purpose select.
- Tone select.
- Visual template select.
- Price or promotion input.
- Extra request textarea.
- `광고 배너 만들기` submit button.
- Short backend/status caption, including reference-image support guidance where useful.

Right column, about 60-65% width:

- Before generation: result placeholder that communicates the expected output.
- After generation:
  - Demo product analysis card.
  - Representative completed banner preview.
  - Recommended copy cards.
  - Variant slots that present alternate copy/style choices without claiming three real image generations.
  - Download button for the final overlaid banner.
  - Expanders for original generated image, selected template JSON, prompt summary, backend names, reference usage, and elapsed time.

## 6. Data Flow

1. Streamlit builds the existing `GenerationRequest` payload from form inputs.
2. Streamlit calls the existing FastAPI `POST /generate` endpoint.
3. The API returns three copy options and one generated image path.
4. Streamlit selects the first copy option as the representative banner copy.
5. Streamlit opens the returned image path locally.
6. The overlay helper renders the headline, body, price/promotion, and CTA onto the image with PIL.
7. The overlaid banner is saved under `outputs/streamlit-banners/`.
8. The UI displays and downloads the overlaid banner.
9. The mock analysis helper returns deterministic product-analysis copy from the submitted inputs and upload state.

## 7. Korean Text Overlay

The overlay helper should:

- Use PIL `ImageDraw`.
- Load a Korean-capable system font when available.
- Fall back gracefully if the preferred font is unavailable.
- Render a semi-transparent text panel or readable text treatment over the generated image.
- Use:
  - headline from the first copy option.
  - body from the first copy option.
  - CTA from the first copy option.
  - price/promotion from `price_text`.
- Wrap text by pixel width, not only by character count.
- Truncate extremely long text rather than failing.
- Save output as PNG with a deterministic suffix such as `*_banner.png`.

This explicitly demonstrates the design choice that image generation handles the visual composition, while deterministic rendering handles Korean text, prices, CTA, and ad layout.

## 8. Mock Product Analysis

The analysis must be labeled as demo/mock analysis, not real VLM output.

It should return structured display data such as:

- Product context: product name and dessert-cafe context.
- Ad goal: campaign purpose and promotion.
- Visual strategy: selected tone and template.
- Photo strategy:
  - If a reference image was uploaded: product-photo-based banner flow.
  - If no reference image was uploaded: no reference image supplied.
- Rendering strategy: Korean copy is rendered by overlay instead of asking the image model to draw text.

This keeps the UI aligned with the future VLM story while avoiding a misleading claim.

## 9. Error Handling

- Preserve current API error behavior and Korean `st.error` messages.
- If the API returns an image path that does not exist, show the current warning and skip overlay creation.
- If overlay creation fails, show a clear Streamlit warning and still display the original generated image and copy options.
- Do not fail a completed generation only because banner overlay failed.
- Keep expensive backend details in expanders so user-facing demo flow remains clean.

## 10. Testing

Add focused tests around helper logic:

- Overlay creates an output PNG from a small local input image.
- Overlay handles long Korean headline/body text without raising.
- Overlay falls back when a preferred font path is unavailable.
- Mock product analysis returns expected fields for uploaded and non-uploaded states.

Streamlit end-to-end browser automation is out of scope for this design. Existing API and backend tests should continue to pass.

## 11. Acceptance Criteria

- Streamlit starts with a wide two-column Studio layout.
- A user can upload/select inputs and generate using the existing API.
- The result view shows demo product analysis, recommended copy, and a representative completed banner.
- The downloaded asset is the overlaid Korean banner image, not only the raw generated image.
- Original generated image and technical details remain available in expanders.
- The backend still generates one image per request.
- Tests for overlay and mock analysis pass.

## 12. Follow-Up Candidates

- Real VLM analysis using Qwen2.5-VL or an API VLM.
- Industry/platform RAG for marketing copy guidance.
- Real three-variant image generation.
- User revision loop for copy, tone, platform, and regeneration.
- FastMCP layer exposing `generate_dessert_ad`, generation log lookup, result retrieval, and template scoring to agent clients.
