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

The generated image preserved the broad cup/pudding structure enough for a
moderate structural hash score, but it also rendered visible model-generated
text in the image. That supports the existing production design choice: image
models should produce or edit visuals, while Korean marketing copy is rendered
deterministically by the overlay layer.

## Evidence Artifact

- Summary: [`openai-image-edit-preservation-live-summary.json`](openai-image-edit-preservation-live-summary.json)

## Reproduce

This command costs real money and requires `OPENAI_API_KEY`:

```bash
.venv/bin/python scripts/openai_image_edit_preservation_smoke.py --date 2026-06-17
```

The command is expected to exit non-zero when the live gate fails. It still
writes the redacted summary for review.

## Privacy Boundary

- Raw prompt is not committed.
- Raw OpenAI response is not committed.
- Generated image is not committed.
- Reference image is a committed public sample with source/license metadata in
  `docs/evidence/real-sample-preservation.md`.
