# Provider Gate Postmortem Evidence

Date: 2026-06-17

## Scope

This evidence turns the failed paid OpenAI image-edit provider-quality run into
a reproducible postmortem. It does not call the OpenAI API. It reads the
redacted summary in
[`openai-image-edit-preservation-live-summary.json`](openai-image-edit-preservation-live-summary.json)
and classifies the failure modes that must be fixed before another paid run.

## Command

```bash
.venv/bin/python scripts/analyze_provider_gate_failure.py \
  --input docs/evidence/openai-image-edit-preservation-live-summary.json \
  --output docs/evidence/provider-gate-postmortem-summary.json
```

## Result

Summary:
[`provider-gate-postmortem-summary.json`](provider-gate-postmortem-summary.json)

- `provider_gate_postmortem`: `failed_gate_analyzed`
- Model/quality: `gpt-image-2` / `medium`
- Samples: 3
- Provider-quality pass rate: `0.00`
- Estimated cost: `$0.2658`, over the `$0.20` script budget by `$0.0658`
- ROI preservation checks: passed
- Root causes:
  - `latency_threshold_exceeded`
  - `text_contamination_heuristic_failed`
  - `cost_budget_exceeded`

## Interpretation

The latest paid run should not be treated as a provider-quality success. It is
still useful evidence because it separates what worked from what did not:

- Product-region preservation was measurably strong enough under the current
  ROI metrics.
- Operational readiness failed because every sample exceeded the 30 second
  threshold.
- Design safety failed because every sample triggered the text-contamination
  heuristic.
- Budget control failed after usage was returned; the script guard is an
  evidence gate, not a pre-spend hard cap.

## Next Paid Gate Conditions

Before another paid image-edit provider gate:

- review ignored generated outputs locally;
- run a one-sample paid canary with `--sample-slug` before the three-sample
  provider gate;
- set an OpenAI dashboard hard budget because the script budget is
  post-response only;
- keep deterministic Korean overlay rendering outside the image model.

## Privacy Boundary

- Raw prompt is not committed.
- Raw OpenAI response is not committed.
- Generated images are not committed.
