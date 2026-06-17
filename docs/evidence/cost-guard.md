# Cost Guard Evidence

Date: 2026-06-17

## Scope

This evidence proves the first offline cost-control gate for paid OpenAI image
smokes. It does not call the OpenAI API. It estimates cost from recorded token
usage, records the pricing source, supports environment-variable rate overrides,
and fails closed when a budget is set but the cost cannot be estimated.

The current provider-quality target is `gpt-image-2`. The image backend records
only `total_tokens`, so the estimator uses the image output token rate as a
conservative ceiling until separate input/output image token buckets are
available.

## Command

```bash
.venv/bin/python scripts/cost_guard_smoke.py \
  --model-id gpt-image-2 \
  --image-total-tokens 627 \
  --max-estimated-cost-usd 0.02 \
  --output docs/evidence/cost-guard-summary.json
```

Result:

```text
cost_guard_smoke=passed
model_id=gpt-image-2
total_tokens=627
estimated_cost_usd=0.01881
max_estimated_cost_usd=0.02
```

The machine-readable summary is stored at
[`cost-guard-summary.json`](cost-guard-summary.json).

## Live Gate Integration

`scripts/openai_image_edit_preservation_smoke.py` now accepts
`--max-estimated-cost-usd` or `OPENAI_MAX_ESTIMATED_COST_USD`. When the budget
is provided:

- estimated cost below the budget keeps the cost guard passing;
- estimated cost above the budget makes the smoke fail;
- missing token pricing for the selected model fails closed instead of silently
  passing the budget gate.

Pricing defaults are intentionally small and explicit. Current built-in defaults
cover `gpt-5.4-mini` text usage and `gpt-image-2` image usage, with overrides
available through:

- `OPENAI_COPY_INPUT_USD_PER_1M_TOKENS`
- `OPENAI_COPY_OUTPUT_USD_PER_1M_TOKENS`
- `OPENAI_IMAGE_USD_PER_1M_TOKENS`

The pricing source recorded in the summary is
<https://openai.com/api/pricing/>, checked on 2026-06-17.

## Remaining Gap

This is a per-run guard, not account-level spend enforcement. OpenAI project
billing limits should still be configured in the API dashboard before repeated
paid evaluations.
