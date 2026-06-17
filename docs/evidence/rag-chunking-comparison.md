# RAG Chunking Strategy Comparison

Date: 2026-06-17

This evidence records the first offline chunking comparison for the marketing
context RAG corpus. It compares whole-document chunks with field-aware chunks
using the same deterministic local hash embedding family used by the pgvector
first gate. No paid APIs, external vector services, or raw user inputs are
stored.

## Scope

- Corpus: 5 committed marketing guide documents.
- Eval set: 10 marketing-context retrieval cases.
- Compared strategies:
  - `whole_document`: one chunk per guide document.
  - `field_aware`: one chunk per non-empty guide field such as keywords, copy
    guidelines, tone examples, platform notes, prohibited claims, and CTA
    examples.
- Ranking: deterministic local embedding plus lexical category prior.
- Required safety fallback: `prohibited_claims` must stay retrievable.

## Result

Summary artifact:

```text
docs/evidence/rag-chunking-comparison-results.json
```

Current result:

- `rag_chunking_comparison`: `passed`
- `scope`: `offline_marketing_context_chunking_no_paid_api_call`
- document count: `5`
- eval cases: `10`
- selected strategy: `field_aware`
- selected category hit rate: `0.90`
- selected required category hit rate: `1.00`
- average top-k chunks: `4.00`
- raw inputs committed: `false`

`whole_document` and `field_aware` tie on the current small eval set. The first
selected strategy is `field_aware` because it preserves field-level citation and
reranking boundaries as the corpus grows, while keeping the current safety
category coverage intact.

## Reproduce

```bash
.venv/bin/python scripts/eval_rag_chunking_strategies.py \
  --date 2026-06-17 \
  --output docs/evidence/rag-chunking-comparison-results.json
```

Focused test:

```bash
.venv/bin/pytest tests/test_rag_chunking_comparison_script.py -q
```

## Limits

- This is an offline first gate over a small committed corpus.
- The embedding is deterministic and local for CI stability, not a production
  semantic embedding model.
- The comparison does not yet replace the production retrieval path.
- Reevaluate when the guide corpus exceeds 25 documents, when real document
  ingestion is added, or when a production embedding model is selected.
