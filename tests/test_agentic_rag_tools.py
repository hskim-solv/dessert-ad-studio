from __future__ import annotations

import json
from pathlib import Path

from dessert_ad_studio.agentic_rag import (
    build_agentic_rag_graph,
    build_agentic_rag_initial_state,
)
from dessert_ad_studio.agentic_tools import (
    run_internal_api_tool,
    run_sql_query_tool,
    run_web_search_tool,
)
from dessert_ad_studio.schemas import GenerationRequest


ROOT = Path(__file__).resolve().parents[1]


def test_local_agentic_tools_return_redacted_summaries() -> None:
    request_summary = {
        "campaign_purpose": "new_menu",
        "tone": "premium",
        "template_hint": "minimal_premium",
        "has_price_text": True,
        "has_user_constraints": True,
        "retrieval_query": "new_menu premium minimal_premium",
    }

    web = run_web_search_tool(query="new_menu premium minimal_premium")
    sql = run_sql_query_tool(query_id="template_policy_summary")
    internal = run_internal_api_tool(request_summary=request_summary)

    assert web == {
        "tool": "web_search",
        "mode": "local_curated_snapshot",
        "result_count": 2,
        "source_ids": ["hiring-agent-rag-tools", "ad-policy-local-guides"],
    }
    assert sql == {
        "tool": "sql_query",
        "mode": "sqlite_allowlisted_query",
        "query_id": "template_policy_summary",
        "policy": {
            "read_only": True,
            "allowlisted_query_ids": ["template_policy_summary"],
            "raw_sql_allowed": False,
            "mutation_statements_allowed": False,
            "row_limit": 25,
            "timeout_ms": 250,
        },
        "row_count": 3,
        "min_score_threshold": 0.62,
        "policy_guardrail_count": 3,
    }
    assert internal == {
        "tool": "internal_api",
        "mode": "in_process_contract",
        "endpoint": "preview_generation_policy",
        "requires_reference_image": False,
        "recommended_review_lane": "standard",
        "policy_count": 3,
    }

    serialized = json.dumps({"web": web, "sql": sql, "internal": internal}, ensure_ascii=False)
    assert "new_menu premium minimal_premium" not in serialized


def test_agentic_rag_graph_runs_local_tool_suite_before_retrieval_without_raw_inputs() -> None:
    graph = build_agentic_rag_graph()
    state = build_agentic_rag_initial_state(
        GenerationRequest(
            campaign_purpose="new_menu",
            product_name="비공개 말차 푸딩",
            tone="premium",
            template_hint="minimal_premium",
            price_text="7,500원",
            user_constraints="VIP 고객에게만 보일 문구",
        ),
        requires_paid_provider=False,
        estimated_cost_usd=0.0,
        approval_cost_threshold_usd=0.10,
    )

    result = graph.invoke(state)

    assert result["node_trace"][:3] == [
        "plan_campaign",
        "run_tool_suite",
        "retrieve_context",
    ]
    assert result["tool_results"]["web_search"]["result_count"] == 2
    assert result["tool_results"]["sql_query"]["query_id"] == "template_policy_summary"
    assert result["tool_results"]["internal_api"]["endpoint"] == "preview_generation_policy"
    assert result["plan"]["tool_budget"] == {
        "max_tool_calls": 7,
        "planned_tools": [
            "document_retrieval",
            "web_search",
            "sql_query",
            "internal_api",
            "citation_builder",
            "guardrail_check",
            "generation_workflow",
        ],
    }
    assert result["approval"] == {"required": False, "reasons": []}

    serialized = json.dumps(result, ensure_ascii=False)
    assert "비공개 말차 푸딩" not in serialized
    assert "VIP 고객에게만 보일 문구" not in serialized


def test_sql_query_tool_rejects_non_allowlisted_queries_with_policy_summary() -> None:
    result = run_sql_query_tool(query_id="drop_template_policy")

    assert result == {
        "tool": "sql_query",
        "mode": "sqlite_allowlisted_query",
        "query_id": "drop_template_policy",
        "policy": {
            "read_only": True,
            "allowlisted_query_ids": ["template_policy_summary"],
            "raw_sql_allowed": False,
            "mutation_statements_allowed": False,
            "row_limit": 25,
            "timeout_ms": 250,
        },
        "row_count": 0,
        "error": "query_id_not_allowed",
    }


def test_agentic_tool_suite_adr_and_mcp_server_are_recorded() -> None:
    adr = (ROOT / "docs" / "adr" / "0017-agentic-rag-tool-suite.md").read_text(encoding="utf-8")
    mcp_server = (ROOT / "mcp_servers" / "dessert_ad_studio_server.py").read_text(encoding="utf-8")
    evidence = (ROOT / "docs" / "evidence" / "agentic-rag-tools.md").read_text(encoding="utf-8")

    assert "web_search" in adr
    assert "sql_query" in adr
    assert "internal_api" in adr
    assert "document_retrieval" in adr
    assert "FastMCP" in adr
    assert "from mcp.server.fastmcp import FastMCP" in mcp_server
    assert "@mcp.tool()" in mcp_server
    assert "search_marketing_guides" in mcp_server
    assert "query_template_policy" in mcp_server
    assert "preview_generation_policy" in mcp_server
    assert "docs/evidence/agentic-rag-tools-summary.json" in evidence
