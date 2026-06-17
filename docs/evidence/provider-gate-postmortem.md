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
- Samples: 1
- Provider-quality pass rate: `0.00`
- Estimated cost: `$0.08859`, under the `$0.10` script budget
- ROI preservation checks: passed
- Root causes:
  - `latency_threshold_exceeded`
  - `text_contamination_heuristic_failed`

## Interpretation

The latest paid run should not be treated as a provider-quality success. It is
still useful evidence because it separates what worked from what did not:

- Product-region preservation was measurably strong enough under the current
  ROI metrics.
- Operational readiness failed because the sample exceeded the 30 second
  threshold.
- Design safety needs remediation because the sample triggered the
  text-contamination heuristic. Manual local review found no visible text, so
  the current proxy likely over-flags dark components or edges.
- Budget control passed for this one-sample canary, but the script guard is
  still an evidence gate, not a pre-spend hard cap.

## Next Paid Gate Conditions

Before another paid image-edit provider gate:

- review generated outputs locally;
- use the 2026-06-17 one-sample canary result as the current baseline: API and
  cost guard passed, ROI preservation passed, latency failed, and the
  text-contamination proxy likely over-flagged a no-visible-text output;
- set an OpenAI dashboard hard budget because the script budget is
  post-response only;
- keep deterministic Korean overlay rendering outside the image model.

## Privacy Boundary

- Raw prompt is not committed.
- Raw OpenAI response is not committed.
- Generated images are not committed.
