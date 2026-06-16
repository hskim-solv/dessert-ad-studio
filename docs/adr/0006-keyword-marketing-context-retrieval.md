# 0006. Keyword Marketing Context Retrieval

- 날짜: 2026-06-15
- 상태: 채택됨

## 배경 (Context)

Dessert Ad Studio needs lightweight RAG marketing guidance so generated Korean
copy can use industry, platform, CTA, and prohibited-claim guidance. The current
corpus is small and curated, and the immediate goal is to prove the workflow
boundary: `GenerationRequest -> ProductAnalysis -> MarketingContext -> copy
prompt -> trace`.

## 선택 기준 (Criteria)

- Workflow fit: can be added without changing the product flow heavily.
- Testability: deterministic in unit tests and CI.
- Operational cost: storage, indexing, Docker volume, and dependency footprint.
- Portfolio path: leaves a credible upgrade path to vector or hybrid retrieval.
- Sensitive trace policy: stores only redacted retrieval metadata in logs/traces.

## 후보 비교 (Comparison)

| 기준 | Keyword retriever | Chroma | Qdrant |
|---|---|---|---|
| Workflow fit | In-process and simple for the current guide size. | Requires embedding/index setup. | Requires service or embedded client setup. |
| Testability | Deterministic text fixtures, no model dependency. | Needs stable embedding fixtures or mocks. | Needs collection lifecycle and client fixtures. |
| Operational cost | No new dependency, no persistence volume. | Adds package and local persistence path. | Adds service/container and collection management. |
| Portfolio path | Good first step if wrapped by a retriever contract. | Shows vector DB basics. | Stronger production signal for later hybrid retrieval. |
| Trace safety | Easy to log document ids/counts only. | Must avoid logging chunks/embeddings. | Must avoid logging chunks/embeddings and collection payloads. |

## 결정 (Decision)

Adopt an in-process keyword retriever as the first `MarketingContextRetriever`
implementation. Keep the public boundary typed so a later `QdrantRetriever` or
hybrid retriever can replace the implementation without rewriting the workflow.

The decisive criteria are deterministic CI behavior and low operational cost.
The current guide set is too small to justify vector infrastructure before the
workflow, prompt, and trace contract are proven.

## 결과 및 재평가 조건 (Consequences)

- 이 선택으로 감수하는 것:
  - No semantic similarity search yet.
  - Retrieval quality depends on curated keywords and metadata.
  - It is a workflow proof, not the final retrieval engine.
- 재평가 트리거:
  - Marketing guides exceed roughly 30-50 documents.
  - Keyword retrieval fails relevance tests for cross-wording queries.
  - Portfolio needs explicit vector DB evidence after the RAG workflow is stable.
  - Hybrid retrieval/reranking evaluation becomes a planned milestone.
