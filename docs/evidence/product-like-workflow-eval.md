# Product-Like Workflow Eval Evidence

Date: 2026-06-17

## Scope

This evidence expands the deterministic workflow eval from 3 demo samples to
30 product-like small-business scenarios across cafe, bakery, dessert, brunch,
delivery-banner, smart-store, Kakao channel, and Instagram surfaces.

This is still a deterministic proxy gate. It proves workflow completeness,
Korean copy presence, product-name inclusion, image-path generation, product
analysis presence, trace step order, and non-negative latency fields. It does
not replace human visual review or real customer conversion metrics.

## Command

```bash
.venv/bin/python scripts/eval_product_like_samples.py \
  --output docs/evidence/product-like-workflow-eval-summary.json
```

Result:

```text
sample_count=30
scenario_pack=product_like_v1
average_score=1.0
failure_count=0
passed=True
```

The machine-readable summary is stored at
`docs/evidence/product-like-workflow-eval-summary.json`.

## Coverage

| Axis | Coverage |
|---|---|
| Business types | 30 synthetic/product-like business scenarios |
| Platforms | Instagram feed/story/reels cover, Naver SmartStore, Naver Place, delivery app banner, Kakao Channel |
| Tones | `clean`, `playful`, `premium`, `warm` |
| Template hints | `cozy_cafe`, `minimal_premium`, `seasonal_event` |
| Checks per sample | copy option count, Korean copy, product-name inclusion, image path, product analysis, workflow step order, elapsed times |

## Remaining Gap

The first offline visual proxy gate is now covered by
[`visual-quality.md`](visual-quality.md). The paid provider-quality image-edit
gate remains separate and requires explicit approval before another live model
run. Broader generated-asset quality claims still need human review or
provider-quality visual statistics.
