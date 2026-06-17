from __future__ import annotations

from dessert_ad_studio.agentic_tools import (
    run_internal_api_tool,
    run_sql_query_tool,
    run_web_search_tool,
)

try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError as exc:  # pragma: no cover - exercised only without mcp extra.
    raise SystemExit(
        "Install the optional MCP extra before running this server: "
        'python -m pip install -e ".[mcp]"'
    ) from exc


mcp = FastMCP("Dessert Ad Studio", json_response=True)


def transport_auth_policy() -> dict:
    return {
        "served_transport": "streamable-http",
        "manual_command": "python -m mcp_servers.dessert_ad_studio_server",
        "bind_host": "127.0.0.1",
        "mount_path": "/mcp",
        "local_loopback_only": True,
        "production_auth_required": True,
        "production_auth_status": "pending_auth_provider_selection",
        "remote_client_contract": "pending_transport_auth_smoke",
        "raw_inputs_committed": False,
    }


@mcp.tool()
def search_marketing_guides(query: str) -> dict:
    """Search local curated marketing guide snapshots without external web calls."""

    return run_web_search_tool(query=query)


@mcp.tool()
def query_template_policy(query_id: str = "template_policy_summary") -> dict:
    """Run an allowlisted SQLite template-policy summary query."""

    return run_sql_query_tool(query_id=query_id)


@mcp.tool()
def preview_generation_policy(
    campaign_purpose: str,
    tone: str,
    template_hint: str,
    has_reference_image: bool = False,
    has_user_constraints: bool = False,
) -> dict:
    """Preview the in-process generation policy lane for a redacted request summary."""

    return run_internal_api_tool(
        request_summary={
            "campaign_purpose": campaign_purpose,
            "tone": tone,
            "template_hint": template_hint,
            "has_reference_image": has_reference_image,
            "has_user_constraints": has_user_constraints,
        }
    )


def main() -> None:
    mcp.run(transport=transport_auth_policy()["served_transport"])


if __name__ == "__main__":
    main()
