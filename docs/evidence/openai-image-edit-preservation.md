# OpenAI Image-Edit Preservation Live Evidence

Date: 2026-06-17

This is a paid live smoke for the OpenAI image-edit path using a committed
public sample reference image. It sends the public matcha-pudding reference
image to OpenAI, writes the generated output only under ignored `outputs/`, and
commits only a redacted metric summary.

## Result

- Result: `failed`
- Model: `gpt-image-1-mini`
- Quality: `low`
- Reference image: public sample `docs/evidence/assets/real-sample-preservation/references/matcha-pudding.png`
- Elapsed: `15,231 ms`
- Usage: `627 total_tokens`
- Generated file: exists, `1024x1024`, nonblank, not committed
- Color histogram similarity: `0.234960`
- Average hash similarity: `0.546875`
- Checklist failure: color histogram similarity did not meet the initial `>= 0.25` gate

This first run used the initial single-sample smoke gate. The current script
now also supports a stronger provider-quality gate for the next paid iteration.

The generated image preserved the broad cup/pudding structure enough for a
moderate structural hash score, but it also rendered visible model-generated
text in the image. That supports the existing production design choice: image
models should produce or edit visuals, while Korean marketing copy is rendered
deterministically by the overlay layer.

## Strengthened Provider-Quality Gate

The strengthened gate is intended for the next paid model/prompt iteration, not
for the historical summary above. It keeps the default command to one paid
sample, and only runs the three public references when
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

Next paid provider-quality run, if approved:

```bash
.venv/bin/python scripts/openai_image_edit_preservation_smoke.py \
  --reference-set public-samples \
  --model-id gpt-image-2 \
  --quality medium \
  --date 2026-06-17
```

## Privacy Boundary

- Raw prompt is not committed.
- Raw OpenAI response is not committed.
- Generated image is not committed.
- Reference image is a committed public sample with source/license metadata in
  `docs/evidence/real-sample-preservation.md`.
