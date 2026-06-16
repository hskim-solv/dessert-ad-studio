# RAG Baseline Evaluation Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reproducible evaluation pack for the current keyword marketing-context retriever.

**Architecture:** Keep retrieval evaluation independent from model calls. Evaluate `MarketingContext` category hits, required prohibited-claims coverage, and source-doc metadata, then expose the same logic through tests and a CLI script that can write evidence JSON.

**Tech Stack:** Python dataclasses, existing `GenerationRequest`, `MarketingContext`, `KeywordMarketingContextRetriever`, `MockProductAnalyzer`, pytest.

---

### Task 1: Retrieval Evaluation Model

**Files:**
- Modify: `src/dessert_ad_studio/evaluation.py`
- Test: `tests/test_marketing_context.py`

- [ ] **Step 1: Write failing tests for category hit-rate and required category checks**

```python
def test_evaluate_marketing_context_retrieval_reports_missing_categories() -> None:
    context = MarketingContext(
        retriever_backend="keyword",
        guide_categories=["cafe", "prohibited_claims"],
        source_doc_ids=["guide-cafe-dessert-core-v1", "guide-ad-claims-safety-v1"],
        retrieved_docs_count=2,
    )

    result = evaluate_marketing_context_retrieval(
        sample_label="missing-platform",
        context=context,
        expected_categories=("cafe", "instagram", "prohibited_claims"),
        required_categories=("prohibited_claims",),
        threshold=0.8,
    )

    assert result.passed is False
    assert result.category_hit_rate == pytest.approx(2 / 3)
    assert result.missing_categories == ["instagram"]
```

- [ ] **Step 2: Run the focused test and verify it fails because the evaluator is missing**

Run: `.venv/bin/pytest tests/test_marketing_context.py -q`

- [ ] **Step 3: Add `MarketingContextEvalResult`, `MarketingContextEvalSummary`, `evaluate_marketing_context_retrieval`, and `summarize_marketing_context_eval_results`**

- [ ] **Step 4: Run the focused test and verify it passes**

Run: `.venv/bin/pytest tests/test_marketing_context.py -q`

### Task 2: Baseline CLI And Evidence

**Files:**
- Create: `scripts/eval_marketing_context.py`
- Create: `docs/evidence/rag-baseline.md`
- Generated: `docs/evidence/rag-baseline-results.json`
- Test: `tests/test_marketing_context.py`

- [ ] **Step 1: Write failing tests for the canonical keyword baseline samples**

The test should run the keyword retriever over representative cafe/dessert samples and require:

```python
assert summary.sample_count >= 3
assert summary.average_category_hit_rate >= 0.8
assert summary.required_category_hit_rate == 1.0
assert summary.passed is True
```

- [ ] **Step 2: Run the focused test and verify it fails until the CLI/eval sample helpers exist**

Run: `.venv/bin/pytest tests/test_marketing_context.py -q`

- [ ] **Step 3: Add the CLI script with deterministic sample cases and JSON output**

Run: `.venv/bin/python scripts/eval_marketing_context.py --output docs/evidence/rag-baseline-results.json`

- [ ] **Step 4: Add `docs/evidence/rag-baseline.md` documenting the command, thresholds, current results, and next vector/hybrid gate**

- [ ] **Step 5: Run focused and full verification**

Run:

```bash
.venv/bin/pytest tests/test_marketing_context.py tests/test_evaluation.py -q
.venv/bin/python scripts/eval_marketing_context.py --output docs/evidence/rag-baseline-results.json
.venv/bin/pytest -q
.venv/bin/ruff check .
git diff --check
```
