# RAG Baseline Evidence: Keyword Marketing Context Retrieval

Date: 2026-06-15

## Scope

This evidence covers the current in-process keyword retrieval baseline for
marketing context. It does not claim vector retrieval, semantic search, or
reranking quality.

The goal is to prove that the baseline retrieves the required guide categories
before adopting a vector DB or hybrid search stack.

## Command

```bash
.venv/bin/python scripts/eval_marketing_context.py --output docs/evidence/rag-baseline-results.json
```

## Gate

| Metric | Target | Current |
|---|---:|---:|
| Sample count | >= 10 | 10 |
| Category hit rate | >= 0.80 | 1.00 |
| Category precision | tracked, not gating v1 | 0.75 |
| Required prohibited-claims hit rate | 1.00 | 1.00 |
| Result | pass | pass |

## Samples

| Sample | Expected categories | Matched categories | Missing | Extra retrieved |
|---|---|---|---|---|
| `instagram-cafe-new-menu` | `cafe`, `instagram`, `prohibited_claims` | `cafe`, `instagram`, `prohibited_claims` | none | `discount` |
| `premium-seasonal-dessert` | `cafe`, `instagram`, `premium`, `prohibited_claims` | `cafe`, `instagram`, `premium`, `prohibited_claims` | none | `discount` |
| `discount-promotion` | `discount`, `prohibited_claims` | `discount`, `prohibited_claims` | none | `cafe`, `premium` |
| `premium-cake-gift` | `cafe`, `premium`, `prohibited_claims` | `cafe`, `premium`, `prohibited_claims` | none | `discount` |
| `sns-reels-madeleine` | `cafe`, `instagram`, `prohibited_claims` | `cafe`, `instagram`, `prohibited_claims` | none | `discount` |
| `coupon-cheesecake` | `cafe`, `discount`, `prohibited_claims` | `cafe`, `discount`, `prohibited_claims` | none | none |
| `signature-cafe-brand` | `cafe`, `prohibited_claims` | `cafe`, `prohibited_claims` | none | `discount` |
| `premium-flower-gift` | `premium`, `prohibited_claims` | `premium`, `prohibited_claims` | none | `cafe`, `discount` |
| `instagram-hashtag-cake` | `cafe`, `instagram`, `prohibited_claims` | `cafe`, `instagram`, `prohibited_claims` | none | `discount` |
| `benefit-pudding-set` | `cafe`, `discount`, `prohibited_claims` | `cafe`, `discount`, `prohibited_claims` | none | none |

## Interpretation

The keyword baseline is sufficient as the first retrieval layer:

- It retrieves all expected guide categories for the current representative
  samples.
- It always includes `prohibited_claims`, which is the required safety category.
- It produces deterministic source doc IDs that can be inspected in
  `docs/evidence/rag-baseline-results.json`.

The baseline also over-retrieves on some cases. This is acceptable for v1 because
the guidance corpus is small and curated, but it is the main reason to evaluate
hybrid/vector retrieval later.

Current average category precision is 0.75, with the weakest case at 0.50. This
means the next retriever should not only keep hit rate at 1.00, but also reduce
unnecessary categories.

## Next Gate

Do not add vector DB as a default path until a comparison shows measurable
improvement over this baseline.

The next retrieval ADR should compare at least:

- current keyword baseline
- Qdrant
- pgvector
- Chroma or a no-adoption baseline

The comparison must report:

- category hit rate
- required safety-category hit rate
- unexpected category rate or precision
- deterministic source IDs
- runtime/dependency cost
