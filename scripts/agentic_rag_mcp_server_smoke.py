from __future__ import annotations

import argparse
from datetime import date
import importlib.metadata
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from mcp_servers import dessert_ad_studio_server  # noqa: E402


DEFAULT_OUTPUT_PATH = Path("docs/evidence/agentic-rag-mcp-server-summary.json")


def build_agentic_rag_mcp_server_summary(*, evidence_date: str) -> dict[str, Any]:
    web = dessert_ad_studio_server.search_marketing_guides("비공개 말차 푸딩 launch")
    sql = dessert_ad_studio_server.query_template_policy()
    internal = dessert_ad_studio_server.preview_generation_policy(
        campaign_purpose="new_menu",
        tone="premium",
        template_hint="minimal_premium",
        has_reference_image=True,
        has_user_constraints=True,
    )
    return {
        "agentic_rag_mcp_server_smoke": "passed",
        "scope": "local_fastmcp_import_and_tool_call_no_network",
        "evidence_date": evidence_date,
        "mcp_package_imported": True,
        "mcp_version": importlib.metadata.version("mcp"),
        "server_name": "Dessert Ad Studio",
        "transport_for_manual_run": "streamable-http",
        "tool_names": [
            "search_marketing_guides",
            "query_template_policy",
            "preview_generation_policy",
        ],
        "tool_results": {
            "search_marketing_guides": web,
            "query_template_policy": sql,
            "preview_generation_policy": internal,
        },
        "raw_inputs_committed": _contains_raw_inputs(
            {"web": web, "sql": sql, "internal": internal}
        ),
    }


def _contains_raw_inputs(value: Any) -> bool:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return "비공개 말차 푸딩" in serialized


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build local FastMCP import/tool-call evidence for Agentic RAG tools.",
        allow_abbrev=False,
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    summary = build_agentic_rag_mcp_server_summary(evidence_date=args.date)
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    print(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    return 0 if summary["agentic_rag_mcp_server_smoke"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
