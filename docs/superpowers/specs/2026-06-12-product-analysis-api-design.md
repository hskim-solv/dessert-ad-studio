# Product Analysis API Pipeline Design

## Goal

Move the demo product analysis out of the Streamlit-only overlay helper and into the FastAPI generation pipeline, so the service has a clear analyzer boundary for future VLM backends.

## Scope

This phase does not add a real VLM call. It creates the production-facing seam that a VLM backend can replace later:

- A typed `ProductAnalysis` response model.
- A small product analyzer module with a deterministic mock analyzer.
- API wiring that runs analysis inside `/generate` after reference image validation.
- Streamlit rendering from the API response instead of local demo-only analysis.
- Tests that prove the analyzer output, API response, and Streamlit persistence path work.

Out of scope:

- Qwen/OpenAI VLM integration.
- Segmentation, masking, or product-preserving composition.
- RAG marketing guidance.
- FastMCP implementation.

## Design

### Data Model

Add `ProductAnalysis` to `src/dessert_ad_studio/schemas.py`.

Fields:

- `label`
- `product_context`
- `ad_goal`
- `visual_strategy`
- `photo_strategy`
- `copy_focus`
- `rendering_strategy`
- `analyzer_backend`

Add `product_analysis: ProductAnalysis` to `GenerationResponse`.

The `/generate` request shape stays unchanged. Existing clients can keep sending the same payload; the response gains one structured object.

### Analyzer Module

Create `src/dessert_ad_studio/product_analysis.py`.

The module owns:

- Korean label maps for campaign purpose, tone, and template.
- `ProductAnalyzer` protocol.
- `MockProductAnalyzer`.

`MockProductAnalyzer.analyze(request, reference_image)` returns deterministic analysis from the request and whether a validated reference image exists. It does not inspect image bytes yet. The reference image bytes are still passed into the analyzer interface so a future VLM implementation can use the same call shape.

### API Wiring

Add `get_product_analyzer()` to `api/main.py`.

For now:

- `PRODUCT_ANALYSIS_BACKEND=mock` or unset returns `MockProductAnalyzer`.
- Unknown values return HTTP 501.

In `/generate`:

1. Validate/decode `reference_image_b64`.
2. Reject unsupported reference image backends as before.
3. Run `product_analysis = product_analyzer.analyze(request, reference_image)`.
4. Continue copy/image generation as before.
5. Include `product_analysis` in `GenerationResponse`.
6. Include `product_analysis_backend` in generation logs.

### Streamlit Wiring

Remove Streamlit’s direct dependency on `build_demo_product_analysis`.

On successful API response, Streamlit stores the response and reads `result["product_analysis"]` for the right-panel analysis. Saved generation restore should tolerate older session-state entries by checking both `saved_generation["analysis"]` and `result["product_analysis"]`.

`build_demo_product_analysis` can remain as a compatibility wrapper for existing tests/imports, but its implementation should delegate to `MockProductAnalyzer` so there is only one source of analysis text.

### Testing

Add focused tests:

- `tests/test_product_analysis.py`
  - mock analyzer returns required display fields.
  - uploaded reference image changes `photo_strategy`.
  - compatibility wrapper returns the same public fields as the mock analyzer.

Extend API tests:

- `/generate` response includes `product_analysis`.
- `product_analysis.analyzer_backend == "mock"`.
- upload/reference behavior is reflected in `photo_strategy`.
- unknown `PRODUCT_ANALYSIS_BACKEND` returns 501.

Keep existing full-suite verification:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
```

## Risks

- Response model expansion can break tests with strict response keys. Fix tests to assert the new object intentionally.
- Streamlit saved state may contain old data while the app is hot-reloaded. The renderer should gracefully read either the stored analysis object or the response object.
- The analyzer must not silently become another UI-only mock; API ownership is the important architectural step for future VLM replacement.

## Self-Review

- Placeholder scan: none.
- Scope check: focused on product analysis API boundary only.
- Ambiguity check: real VLM is explicitly out of scope; mock analyzer is a stable backend with the future call shape.
