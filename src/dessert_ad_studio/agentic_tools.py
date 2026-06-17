from __future__ import annotations

import sqlite3
from typing import Any


WEB_SEARCH_SNAPSHOT = (
    {
        "source_id": "hiring-agent-rag-tools",
        "topic": "agentic_rag_tooling",
        "supports": ("web_search", "sql_query", "internal_api", "document_retrieval"),
    },
    {
        "source_id": "ad-policy-local-guides",
        "topic": "small_business_ad_policy",
        "supports": ("claim_guardrails", "citation_required"),
    },
)

TEMPLATE_POLICY_ROWS = (
    ("minimal_premium", 0.78, "premium_claims_need_evidence"),
    ("cozy_cafe", 0.62, "discount_claims_need_price_context"),
    ("bold_launch", 0.71, "new_menu_claims_need_menu_context"),
)


def run_web_search_tool(*, query: str) -> dict[str, Any]:
    """Return a redacted local web-search snapshot summary.

    The query is accepted to match a real tool contract, but it is intentionally
    not persisted in the result because it can contain user text.
    """

    query_terms = {term for term in query.lower().split() if term}
    matches = [
        entry
        for entry in WEB_SEARCH_SNAPSHOT
        if not query_terms or query_terms.intersection(set(entry["supports"]) | {entry["topic"]})
    ]
    if not matches:
        matches = list(WEB_SEARCH_SNAPSHOT)
    return {
        "tool": "web_search",
        "mode": "local_curated_snapshot",
        "result_count": len(matches),
        "source_ids": [entry["source_id"] for entry in matches],
    }


def run_sql_query_tool(*, query_id: str) -> dict[str, Any]:
    if query_id != "template_policy_summary":
        return {
            "tool": "sql_query",
            "mode": "sqlite_allowlisted_query",
            "query_id": query_id,
            "row_count": 0,
            "error": "query_id_not_allowed",
        }

    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            """
            CREATE TABLE template_policy (
              template_hint TEXT NOT NULL,
              score_threshold REAL NOT NULL,
              policy_guardrail TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            "INSERT INTO template_policy VALUES (?, ?, ?)",
            TEMPLATE_POLICY_ROWS,
        )
        row = connection.execute(
            """
            SELECT
              COUNT(*) AS row_count,
              MIN(score_threshold) AS min_score_threshold,
              COUNT(DISTINCT policy_guardrail) AS policy_guardrail_count
            FROM template_policy
            """
        ).fetchone()
    finally:
        connection.close()

    return {
        "tool": "sql_query",
        "mode": "sqlite_allowlisted_query",
        "query_id": query_id,
        "row_count": int(row[0]),
        "min_score_threshold": float(row[1]),
        "policy_guardrail_count": int(row[2]),
    }


def run_internal_api_tool(*, request_summary: dict[str, Any]) -> dict[str, Any]:
    has_reference_image = bool(request_summary.get("has_reference_image", False))
    has_constraints = bool(request_summary.get("has_user_constraints", False))
    return {
        "tool": "internal_api",
        "mode": "in_process_contract",
        "endpoint": "preview_generation_policy",
        "requires_reference_image": has_reference_image,
        "recommended_review_lane": "enhanced" if has_reference_image else "standard",
        "policy_count": 3 if has_constraints else 2,
    }


def run_agentic_tool_suite(*, request_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "web_search": run_web_search_tool(query=str(request_summary.get("retrieval_query", ""))),
        "sql_query": run_sql_query_tool(query_id="template_policy_summary"),
        "internal_api": run_internal_api_tool(request_summary=request_summary),
    }
