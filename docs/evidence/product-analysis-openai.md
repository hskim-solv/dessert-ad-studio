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

This slice does not claim final image-generation product-preservation quality
yet. It proves the real OpenAI analyzer path with one redacted live smoke and a
fixed 10-case synthetic reference-image eval gate.

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

Live 10-case eval. This also uses a paid external API and writes only redacted
per-case checklist counts and booleans:

```bash
.venv/bin/python scripts/openai_product_analysis_smoke.py \
  --eval \
  --eval-count 10 \
  --output docs/evidence/product-analysis-openai-eval-results.json \
  --image-dir outputs/product-analysis-eval
```

## Current Result

Verified on 2026-06-16:

| Check | Result |
|---|---|
| ADR | `docs/adr/0009-openai-vision-product-analysis.md` records OpenAI vs Gemini vs local VLM decision. |
| Focused no-network tests | `15 passed` |
| Full test suite | `180 passed, 1 warning` |
| Ruff | pass |
| Compose config | pass |
| Diff whitespace | pass |
| API wiring | `/readyz` accepts `PRODUCT_ANALYSIS_BACKEND=openai` with an injected API key and does not call OpenAI. |
| Data URL handling | Unit test verifies `input_image` with `data:image/png;base64,...` and `detail=low`. |
| Structured output | Unit test verifies `text_format=OpenAIProductAnalysisPayload` and `output_parsed` mapping to `ProductAnalysis`. |
| Storage opt-out | Unit test verifies `store=False`. |
| Smoke script | `scripts/openai_product_analysis_smoke.py` writes only redacted checklist evidence: latency, backend/model, reference usage, field counts, and pass/fail booleans. |
| Live smoke | Passed with `gpt-5.4-mini`, reference image enabled, elapsed `10,361 ms`, checklist passed. Summary: `docs/evidence/product-analysis-openai-live-summary.json`. |
| Live eval | Passed with `gpt-5.4-mini`, 10/10 cases passed, pass rate `1.00`, p95 latency `13,150 ms`, below the `30,000 ms` target. Summary: `docs/evidence/product-analysis-openai-eval-results.json`. |

## Remaining M4 Work

- The first OpenAI analyzer eval gate is complete for fixed synthetic
  reference-image cases: pass rate `1.00` against the `>= 0.80` threshold and
  p95 latency `13,150 ms` against the `<= 30s` target.
- Remaining product-quality proof should move to real uploaded product photos
  and final banner/image preservation, not raw analyzer output.
