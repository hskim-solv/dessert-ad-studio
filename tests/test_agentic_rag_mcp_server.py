from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

from mcp.server.fastmcp import FastMCP

from mcp_servers import dessert_ad_studio_server


ROOT = Path(__file__).resolve().parents[1]


def test_fastmcp_server_imports_and_tools_return_redacted_summaries() -> None:
    assert importlib.metadata.version("mcp")
    assert isinstance(dessert_ad_studio_server.mcp, FastMCP)

    web = dessert_ad_studio_server.search_marketing_guides("비공개 말차 푸딩 launch")
    sql = dessert_ad_studio_server.query_template_policy()
    internal = dessert_ad_studio_server.preview_generation_policy(
        campaign_purpose="new_menu",
        tone="premium",
        template_hint="minimal_premium",
        has_reference_image=True,
        has_user_constraints=True,
    )

    assert web["tool"] == "web_search"
    assert web["mode"] == "local_curated_snapshot"
    assert sql["tool"] == "sql_query"
    assert sql["query_id"] == "template_policy_summary"
    assert sql["policy"] == {
        "read_only": True,
        "allowlisted_query_ids": ["template_policy_summary"],
        "raw_sql_allowed": False,
        "mutation_statements_allowed": False,
        "row_limit": 25,
        "timeout_ms": 250,
    }
    assert internal["tool"] == "internal_api"
    assert internal["endpoint"] == "preview_generation_policy"
    assert internal["requires_reference_image"] is True

    serialized = json.dumps({"web": web, "sql": sql, "internal": internal}, ensure_ascii=False)
    assert "비공개 말차 푸딩" not in serialized


def test_mcp_server_smoke_script_writes_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "agentic-rag-mcp-server-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/agentic_rag_mcp_server_smoke.py",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["agentic_rag_mcp_server_smoke"] == "passed"
    assert summary["scope"] == "local_fastmcp_import_and_tool_call_no_network"
    assert summary["mcp_package_imported"] is True
    assert summary["server_name"] == "Dessert Ad Studio"
    assert summary["tool_names"] == [
        "search_marketing_guides",
        "query_template_policy",
        "preview_generation_policy",
    ]
    assert summary["raw_inputs_committed"] is False

    serialized = json.dumps(summary, ensure_ascii=False)
    assert "비공개 말차 푸딩" not in serialized
