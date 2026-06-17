# Visual Quality Proxy Evidence

Date: 2026-06-17

## Scope

This evidence records an offline visual quality proxy gate for committed banner
assets. It checks basic reviewer-visible image quality signals without calling a
paid provider:

- dimensions are at least 768x768;
- square output is preserved for SNS-safe banner review;
- luminance variation, edge density, and downsampled color diversity are high
  enough to reject blank or near-blank images;
- the lower overlay region has enough contrast for Korean copy placement.

This is not a human rating study and does not replace the paid provider-quality
image-edit gate.

## Command

```bash
.venv/bin/python scripts/eval_visual_quality.py \
  --output docs/evidence/visual-quality-summary.json
```

## Result

Summary: [`visual-quality-summary.json`](visual-quality-summary.json)

- `visual_quality_eval`: `passed`
- `sample_count`: 6
- `passed_count`: 6
- `pass_rate`: 1.00

The covered assets are the three deterministic demo-gallery banners and the
three deterministic real-sample preservation banners.

## Failure Behavior

The regression tests include a blank-image negative case and a structured-image
positive case:

```bash
.venv/bin/pytest tests/test_visual_quality_eval_script.py -q
```

The blank image must fail `luminance_stddev` and `edge_density`, which prevents
the proxy gate from becoming a file-exists-only check.

## Remaining Gap

The paid provider-quality image-edit gate remains separate and requires explicit
approval before another live model run. Broader generated-asset quality claims
still need human review or provider-quality visual statistics.
