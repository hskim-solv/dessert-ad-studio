# 0007. pgvector Marketing Context Retrieval

- 날짜: 2026-06-15
- 상태: 채택됨

## 배경 (Context)

`docs/evidence/rag-baseline.md` shows that the current keyword retriever passes
the first RAG baseline gate across 10 representative samples:

- category hit rate: 1.00
- required `prohibited_claims` hit rate: 1.00
- category precision: 0.75

The remaining problem is over-retrieval. The next retrieval layer should keep
the safety hit rate at 1.00 while improving precision and giving the project a
clear Korean hiring signal for vector DB, backend service integration, and data
operation.

## 선택 기준 (Criteria)

- Hiring signal: clearly maps to Korean AI Agent/RAG/backend postings.
- Service integration: supports future generation history and business data in
  the same operational store.
- Testability: can be tested without paid model calls or cloud credentials.
- Operational cost: local Docker service and dependency footprint stay bounded.
- Data policy: avoids storing raw customer photos, raw prompts, raw model
  responses, or secrets.
- Upgrade path: can support hybrid retrieval and reranking later.

## 후보 비교 (Comparison)

| 기준 | Qdrant | pgvector | Chroma | 보류 |
|---|---|---|---|---|
| Hiring signal | Strong dedicated vector DB signal. | Strong vector DB plus backend/database integration signal. | Good local vector prototype signal. | Weak for current portfolio goal. |
| Service integration | Separate vector service from generation history DB. | One Postgres-backed store can later hold guide vectors and generation history. | Local persistence is simple but less representative of service DB ops. | No new operational proof. |
| Testability | Good with container fixtures, but needs collection lifecycle. | Good with SQL schema, Docker service, and deterministic embedding fixtures. | Good in-process or local persistence tests. | Best short-term testability. |
| Operational cost | Adds a vector DB container and volume. | Adds Postgres/pgvector container and volume. | Adds Python package and persistence directory. | No new cost. |
| Data policy | Must avoid storing raw guide/customer payloads in vector payloads. | Can enforce schema columns and store only curated guide docs plus metadata. | Must police local persistence path. | Safest, but no vector DB evidence. |
| Upgrade path | Strong ANN/hybrid path. | Strong SQL + vector + history path; HNSW/IVFFlat available when corpus grows. | Useful prototype path, weaker production story. | Requires another decision later. |

## 결정 (Decision)

Adopt pgvector as the first vector retrieval backend for marketing context.

The deciding factor is portfolio sharpness for the Korean market: pgvector shows
vector retrieval while also reinforcing backend/database integration, future
generation history, reproducible local deployment, and operational evidence.

Initial implementation scope:

- Add a local `pgvector` Docker Compose service.
- Add SQL schema for curated marketing guide embeddings.
- Add deterministic local embeddings for CI/eval only.
- Add a smoke/eval script that writes measured evidence.
- Keep keyword retrieval as the default workflow path until pgvector evidence
  beats or clearly complements the baseline.

## Storage, Retention, And Scope

- Storage location: local Docker named volume `pgvector-data` in this project.
- Data scope: curated marketing guide docs, category metadata, source doc IDs,
  and deterministic local test embeddings only.
- Excluded data: raw customer photos, raw prompts, raw model responses, secrets,
  and full external API responses.
- Retention: local development data persists until the Docker volume is removed;
  CI/test paths use temporary state or schema-only checks.
- Project scope: this database belongs only to `Dessert Ad Studio`; it is not a
  global user memory store and not a cross-project daemon.

## 결과 및 재평가 조건 (Consequences)

- 이 선택으로 감수하는 것:
  - Postgres/pgvector becomes an operational dependency for the vector lane.
  - The first embedding implementation is deterministic and local, not a final
    semantic embedding model.
  - Vector retrieval is evidence-gated and should not replace keyword retrieval
    by default until it improves measured quality.
- 재평가 트리거:
  - pgvector precision fails to beat the keyword baseline after the corpus grows.
  - Dedicated vector DB operations become more important than Postgres
    integration, in which case Qdrant should be reconsidered.
  - A real embedding provider is selected and changes latency/cost/privacy
    constraints.

## Source Notes

- pgvector provides vector similarity search inside Postgres and supports HNSW
  and IVFFlat indexes for approximate search.
- pgvector-python supports common Python database clients including Psycopg 3,
  SQLAlchemy, SQLModel, asyncpg, pg8000, Django, and Peewee.
