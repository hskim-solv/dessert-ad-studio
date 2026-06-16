# pgvector Retrieval Evidence

Date: 2026-06-15

## Scope

This evidence covers the pgvector-first retrieval lane selected in
`docs/adr/0007-pgvector-marketing-context-retrieval.md`.

The current implementation is not a production semantic embedding stack. It uses
a deterministic local embedding for reproducible CI and local smoke tests, then
uses pgvector as the storage/query layer for curated marketing-guide rows.
Final selection is done by hybrid reranking: vector candidates are filtered and
ordered by request-level keyword evidence, while `prohibited_claims` remains an
always-on safety category.

## Local Storage Boundary

- Docker service: `pgvector`
- Host port: `5433`
- Database: `dessert_ad_studio`
- Volume: `pgvector-data`
- Stored data: curated marketing guide text, category metadata, source doc IDs,
  and deterministic test embeddings
- Excluded data: raw customer photos, raw prompts, raw model responses, secrets,
  and external API responses

## Commands

Offline candidate eval:

```bash
.venv/bin/python scripts/eval_pgvector_marketing_context.py --output docs/evidence/pgvector-baseline-results.json
```

Database smoke:

```bash
docker compose up -d pgvector
.venv/bin/python scripts/eval_pgvector_marketing_context.py \
  --dsn postgresql://dessert:dessert_dev_password@localhost:5433/dessert_ad_studio \
  --output docs/evidence/pgvector-db-smoke-results.json
```

API feature flag:

```bash
MARKETING_CONTEXT_BACKEND=pgvector_hybrid
PGVECTOR_DSN=postgresql://dessert:dessert_dev_password@localhost:5433/dessert_ad_studio
```

API readiness/failure mapping:

```bash
.venv/bin/pytest \
  tests/test_api.py::test_readyz_maps_pgvector_connection_failure_to_503 \
  tests/test_api.py::test_generate_maps_pgvector_connection_failure_to_503 \
  -q
```

## Current Results

| Metric | Keyword baseline | pgvector hybrid candidate | pgvector DB smoke |
|---|---:|---:|---:|
| Sample count | 10 | 10 | 10 |
| Category hit rate | 1.00 | 1.00 | 1.00 |
| Category precision | 0.75 | 1.00 | 1.00 |
| Required prohibited-claims hit rate | 1.00 | 1.00 | 1.00 |
| Result | pass | pass | pass |

## Interpretation

pgvector is now adopted as the vector retrieval lane and has working local
storage, schema, upsert, and vector query evidence.

The hybrid reranker improves precision over the original keyword baseline on the
current 10-sample eval set:

- It preserves hit rate and safety-category recall.
- It removes keyword baseline over-retrieval caused by broad guide keywords and
  generic product-analysis text.
- It treats weak premium terms such as "선물" as insufficient unless stronger
  premium signals are present.

The default workflow remains keyword-backed. The pgvector lane is available
behind `MARKETING_CONTEXT_BACKEND=pgvector_hybrid`, so reviewers can inspect the
same generation API with either retrieval backend.

When `pgvector_hybrid` is configured with an unavailable database, `/readyz` and
`/generate` return HTTP 503 with a redacted retriever readiness message instead
of leaking low-level connection errors.

The next proof point is not another vector DB choice. It is to expand the eval
set and run workflow-level comparison: generated copy with keyword context vs.
generated copy with pgvector hybrid context.
