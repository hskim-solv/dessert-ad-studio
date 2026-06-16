# OpenAI Product Analysis Evidence

Date: 2026-06-16

## Scope

This evidence covers the first M4 real product-analysis slice:

- `PRODUCT_ANALYSIS_BACKEND=openai` selects an OpenAI vision-capable analyzer.
- The analyzer uses OpenAI Responses API structured output through
  `client.responses.parse(..., text_format=OpenAIProductAnalysisPayload)`.
- Optional reference image bytes are sent as an in-request PNG data URL only.
- The request sets `store=False`.
- Default workflow behavior remains `PRODUCT_ANALYSIS_BACKEND=mock`, so local
  tests and compose demo do not require a paid API call.

This slice does not claim final product-preservation quality yet. The remaining
M4 proof is a live smoke plus a small evaluation set once API spend is approved.

## Storage Boundary

- Local durable storage: none for raw analyzer prompt, raw reference image, or
  raw model response.
- Provider request: product request text and optional reference-image data URL
  are sent to OpenAI only when `PRODUCT_ANALYSIS_BACKEND=openai`.
- Provider storage: the adapter passes `store=False`.
- Job/history logs: existing generation history remains redacted and stores only
  summaries, not raw photos or model responses.

## Commands

Focused no-network tests:

```bash
.venv/bin/pytest \
  tests/test_product_analysis.py \
  tests/test_openai_product_analysis_smoke.py \
  tests/test_api.py::test_readyz_accepts_openai_product_analysis_backend_without_calling_api \
  -q
```

Config validation:

```bash
docker compose config -q
```

Live product-analysis smoke. This uses a paid external API and writes only a
redacted checklist summary:

```bash
PRODUCT_ANALYSIS_BACKEND=openai \
OPENAI_API_KEY=... \
.venv/bin/python scripts/openai_product_analysis_smoke.py \
  --reference-image outputs/smoke-product-reference.png \
  --output docs/evidence/product-analysis-openai-live-summary.json
```

## Current Result

Verified on 2026-06-16:

| Check | Result |
|---|---|
| ADR | `docs/adr/0009-openai-vision-product-analysis.md` records OpenAI vs Gemini vs local VLM decision. |
| Focused no-network tests | `9 passed` |
| Full test suite | `174 passed, 1 warning` |
| Ruff | pass |
| Compose config | pass |
| Diff whitespace | pass |
| API wiring | `/readyz` accepts `PRODUCT_ANALYSIS_BACKEND=openai` with an injected API key and does not call OpenAI. |
| Data URL handling | Unit test verifies `input_image` with `data:image/png;base64,...` and `detail=low`. |
| Structured output | Unit test verifies `text_format=OpenAIProductAnalysisPayload` and `output_parsed` mapping to `ProductAnalysis`. |
| Storage opt-out | Unit test verifies `store=False`. |
| Smoke script | `scripts/openai_product_analysis_smoke.py` writes only redacted checklist evidence: latency, backend/model, reference usage, field counts, and pass/fail booleans. |
| Live smoke | Blocked on 2026-06-16 because local `.env`/environment has no `OPENAI_API_KEY`. |

## Remaining M4 Work

- Set `OPENAI_API_KEY` locally and run the product-analysis smoke command above.
- Build 10-20 representative product-photo eval cases.
- Add a product-preservation checklist and report pass rate; target remains
  `>= 80%`.
- Measure OpenAI path latency and compare against the `p95 <= 30s` target.
