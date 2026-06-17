# Text-Contamination Proxy Calibration

Date: 2026-06-17

This evidence records an offline calibration gate for the provider-quality
image-edit text-contamination proxy. It does not call OpenAI or any paid API.

## Scope

- Reproduces the previous proxy failure mode with synthetic dark non-text
  components.
- Keeps a dense rendered-text negative case above the provider threshold.
- Stores only summary metrics. Synthetic images are not committed.

## Result

Summary artifact:

```text
docs/evidence/text-contamination-proxy-calibration-summary.json
```

Current result:

- `text_contamination_proxy_calibration`: `passed`
- scope: `offline_synthetic_no_paid_api_call`
- threshold: `0.45`
- dark sprinkle texture score: `0.0`
- dense rendered text score: `1.0`
- paid API calls: `0`
- raw images committed: `false`

## Reproduce

```bash
.venv/bin/python scripts/text_contamination_proxy_calibration_smoke.py \
  --date 2026-06-17 \
  --output docs/evidence/text-contamination-proxy-calibration-summary.json
```

Focused tests:

```bash
.venv/bin/pytest \
  tests/test_text_contamination_proxy_calibration_script.py \
  tests/test_openai_image_edit_preservation_smoke.py::test_text_contamination_proxy_does_not_flag_dark_sprinkle_texture \
  tests/test_openai_image_edit_preservation_smoke.py::test_provider_quality_gate_fails_for_low_roi_similarity_and_text_risk \
  -q
```

## Limits

- This calibrates the local heuristic only. It does not turn the latest paid
  OpenAI image-edit run into a pass.
- Provider-quality image editing remains unproven until a later paid canary or
  full gate passes latency, ROI preservation, text-contamination, and cost
  checks together.
