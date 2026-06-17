from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dessert_ad_studio.agentic_rag import (  # noqa: E402
    build_agentic_rag_graph,
    build_agentic_rag_initial_state,
)
from dessert_ad_studio.agentic_tools import (  # noqa: E402
    build_sql_production_access_audit_policy,
)
from dessert_ad_studio.schemas import GenerationRequest  # noqa: E402


DEFAULT_OUTPUT_PATH = Path("docs/evidence/agentic-rag-tools-summary.json")


def build_agentic_rag_tools_summary(*, evidence_date: str) -> dict[str, Any]:
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
    tool_results = result["tool_results"]
    planned_tools = result["plan"]["tool_budget"]["planned_tools"]
    return {
        "agentic_rag_tools_smoke": "passed",
        "scope": "local_tool_suite_no_network_no_paid_api_call",
        "evidence_date": evidence_date,
        "planned_tools": planned_tools,
        "max_tool_calls": result["plan"]["tool_budget"]["max_tool_calls"],
        "tool_result_keys": sorted(tool_results.keys()),
        "web_search": tool_results["web_search"],
        "sql_query": tool_results["sql_query"],
        "production_db_access_audit_policy": build_sql_production_access_audit_policy(),
        "internal_api": tool_results["internal_api"],
        "document_retrieval": {
            "retriever_backend": result["marketing_context"]["retriever_backend"],
            "retrieved_docs_count": result["marketing_context"]["retrieved_docs_count"],
            "source_doc_count": len(result["marketing_context"]["source_doc_ids"]),
        },
        "approval_required": result["approval"]["required"],
        "approval_reasons": result["approval"]["reasons"],
        "node_trace": result["node_trace"],
        "mcp_server_scaffold": "mcp_servers/dessert_ad_studio_server.py",
        "raw_inputs_committed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build local Agentic RAG tool-suite evidence.",
        allow_abbrev=False,
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    summary = build_agentic_rag_tools_summary(evidence_date=args.date)
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    print(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
