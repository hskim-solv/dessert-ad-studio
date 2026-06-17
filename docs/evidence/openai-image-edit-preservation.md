# OpenAI Image-Edit Preservation Live Evidence

Date: 2026-06-17

This is paid live smoke evidence for the OpenAI image-edit path using committed
public sample reference images. It sends public references to OpenAI, writes the
generated output only under ignored `outputs/`, and commits only a redacted
metric summary.

## Latest Result

- Result: `failed`
- Model: `gpt-image-2`
- Quality: `medium`
- Reference set: 3 committed public samples
- Elapsed: `197,305 ms`
- Usage: `8,860 total_tokens`
- Estimated cost: `$0.2658`
- Budget guard: failed, over `$0.20` by `$0.0658`
- Provider-quality pass rate: `0.00` (`0/3`)
- Generated files: all exist, all `1024x1024`, all nonblank, not committed
- ROI preservation: all samples passed color histogram, average hash, and edge
  similarity thresholds
- Checklist failures: all samples exceeded the `30,000 ms` latency threshold and
  failed the text-contamination heuristic

The strengthened run improved measurable ROI preservation but still does not
prove provider-quality image editing. It reinforces the production boundary:
image models should produce or edit visuals, while Korean marketing copy should
be rendered deterministically by the overlay layer.

## Historical Initial Run

The first paid run used `gpt-image-1-mini`, `quality=low`, and one
matcha-pudding public sample. It failed the initial single-sample gate with
color histogram similarity `0.234960` against the `>= 0.25` threshold.

## Strengthened Provider-Quality Gate

The strengthened gate runs the three public references when
`--reference-set public-samples` is passed.

Hard checks:

- Generated file exists, is nonblank, and is `1024x1024`.
- Per-sample elapsed time is `<= 30,000 ms`.
- Generated image path is redacted; raw prompt and raw model response are not
  committed.

Preservation checks:

- Product-region color histogram similarity `>= 0.30`.
- Product-region average hash similarity `>= 0.60`.
- Product-region edge similarity `>= 0.55`.
- Public-sample pass rate `>= 0.80`, which requires all 3 current samples to
  pass.

Design-safety check:

- Text-contamination risk score `<= 0.45`. This is a lightweight connected
  component heuristic, not OCR. Any borderline pass should still receive visual
  review before being claimed as final provider quality.

## Evidence Artifact

- Summary: [`openai-image-edit-preservation-live-summary.json`](openai-image-edit-preservation-live-summary.json)

## Reproduce

This command costs real money and requires `OPENAI_API_KEY`:

```bash
.venv/bin/python scripts/openai_image_edit_preservation_smoke.py --date 2026-06-17
```

The command is expected to exit non-zero when the live gate fails. It still
writes the redacted summary for review.

Latest paid provider-quality run:

```bash
.venv/bin/python scripts/openai_image_edit_preservation_smoke.py \
  --reference-set public-samples \
  --model-id gpt-image-2 \
  --quality medium \
  --max-estimated-cost-usd 0.20 \
  --date 2026-06-17
```

The `--max-estimated-cost-usd` guard uses the token usage returned by the image
API. If pricing for the selected model is unavailable and no override is set,
the budget gate fails closed instead of silently passing.

The latest run exceeded the `$0.20` budget after usage was returned. This guard
is therefore a post-response evidence gate, not a pre-spend hard cap.

## Privacy Boundary

- Raw prompt is not committed.
- Raw OpenAI response is not committed.
- Generated image is not committed.
- Reference image is a committed public sample with source/license metadata in
  `docs/evidence/real-sample-preservation.md`.
