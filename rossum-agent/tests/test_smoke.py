"""Smoke tests for rossum-agent with real API credentials.

These tests require ROSSUM_API_TOKEN and ROSSUM_API_BASE_URL environment variables.
They are skipped automatically if credentials are not available.

Run with: pytest tests/test_smoke.py -m smoke
"""

from __future__ import annotations

import os

import pytest
from rossum_agent.rossum_mcp_integration import connect_mcp_server

ROSSUM_API_TOKEN = os.environ.get("ROSSUM_API_TOKEN", "")
ROSSUM_API_BASE_URL = os.environ.get("ROSSUM_API_BASE_URL", "")

skip_without_credentials = pytest.mark.skipif(
    not (ROSSUM_API_TOKEN and ROSSUM_API_BASE_URL),
    reason="Requires ROSSUM_API_TOKEN and ROSSUM_API_BASE_URL environment variables",
)


@pytest.mark.smoke
@skip_without_credentials
class TestMCPConnectionSmoke:
    """Smoke tests for MCP connection with real credentials."""

    async def test_mcp_connection_and_list_tools(self) -> None:
        """Verify MCP server connects and lists tools."""
        async with connect_mcp_server(
            rossum_api_token=ROSSUM_API_TOKEN, rossum_api_base_url=ROSSUM_API_BASE_URL, mcp_mode="read-only"
        ) as connection:
            tools = await connection.get_tools()

            assert len(tools) > 0, "Expected at least one MCP tool"

            tool_names = [t.name for t in tools]
            assert "list_workspaces" in tool_names, "Expected list_workspaces tool"

    async def test_mcp_call_list_workspaces(self) -> None:
        """Verify MCP tool call works with list_workspaces.

        Note: The tool returns list[Workspace], but FastMCP wraps non-object returns
        (lists, ints, strings) in {"result": ...} to satisfy JSON schema requirement
        that structured content must be an object type.
        See: https://gofastmcp.com/servers/tools#extracting-structured-content
        """
        async with connect_mcp_server(
            rossum_api_token=ROSSUM_API_TOKEN, rossum_api_base_url=ROSSUM_API_BASE_URL, mcp_mode="read-only"
        ) as connection:
            result = await connection.call_tool("list_workspaces")

            # FastMCP wraps list returns in {"result": [...]} for valid structured output
            assert isinstance(result, dict), "Expected dict result from list_workspaces"
            assert "result" in result, "Expected 'result' key in response"
            assert isinstance(result["result"], list), "Expected list in result['result']"

    async def test_mcp_call_list_tool_categories(self) -> None:
        """Verify list_tool_categories returns catalog with keywords for dynamic loading."""
        async with connect_mcp_server(
            rossum_api_token=ROSSUM_API_TOKEN, rossum_api_base_url=ROSSUM_API_BASE_URL, mcp_mode="read-only"
        ) as connection:
            result = await connection.call_tool("list_tool_categories")

            # FastMCP wraps list returns in {"result": [...]}
            assert isinstance(result, dict), "Expected dict result"
            assert "result" in result, "Expected 'result' key"
            categories = result["result"]
            assert isinstance(categories, list), "Expected list of categories"
            assert len(categories) >= 10, "Expected at least 10 tool categories"

            # Verify category structure
            category_names = {cat["name"] for cat in categories}
            assert "queues" in category_names, "Expected 'queues' category"
            assert "schemas" in category_names, "Expected 'schemas' category"
            assert "hooks" in category_names, "Expected 'hooks' category"

            # Verify each category has required fields including keywords
            for cat in categories:
                assert "name" in cat, f"Category missing 'name': {cat}"
                assert "description" in cat, f"Category {cat['name']} missing 'description'"
                assert "tools" in cat, f"Category {cat['name']} missing 'tools'"
                assert "keywords" in cat, f"Category {cat['name']} missing 'keywords'"
                assert len(cat["keywords"]) > 0, f"Category {cat['name']} has no keywords"
