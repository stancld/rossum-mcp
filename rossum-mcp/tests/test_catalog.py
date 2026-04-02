"""Tests for the tool catalog and discovery modules."""

from __future__ import annotations

import pytest
from fastmcp import FastMCP
from rossum_mcp.tools.catalog import CATEGORY_META
from rossum_mcp.tools.discovery import register_discovery_tools


class TestCategoryMeta:
    """Tests for CATEGORY_META structure."""

    def test_has_all_expected_categories(self) -> None:
        expected_categories = {
            "read",
            "annotations",
            "queues",
            "schemas",
            "engines",
            "hooks",
            "email_templates",
            "rules",
            "users",
            "workspaces",
        }
        assert set(CATEGORY_META.keys()) == expected_categories

    def test_each_category_has_description(self) -> None:
        for name, meta in CATEGORY_META.items():
            assert meta.description, f"Category {name} has no description"

    def test_each_category_has_keywords(self) -> None:
        for name, meta in CATEGORY_META.items():
            assert len(meta.keywords) > 0, f"Category {name} has no keywords"


class TestDiscoveryTools:
    """Tests for discovery MCP tools."""

    @pytest.fixture
    def mcp_with_tools(self) -> FastMCP:
        """Create FastMCP instance with discovery + a few tagged tools registered."""
        mcp = FastMCP("test-discovery")
        register_discovery_tools(mcp, mcp_mode="read-write")

        # Register a few tagged tools to test dynamic grouping
        @mcp.tool(tags={"queues"}, annotations={"readOnlyHint": True})
        async def get_queue(queue_id: int) -> dict:
            return {}

        @mcp.tool(tags={"queues", "write"}, annotations={"readOnlyHint": False})
        async def create_queue_from_template(name: str) -> dict:
            return {}

        @mcp.tool(tags={"hooks"}, annotations={"readOnlyHint": True})
        async def list_hooks() -> list:
            return []

        return mcp

    async def test_list_tool_categories_returns_all_categories(self, mcp_with_tools: FastMCP) -> None:
        list_categories_tool = await mcp_with_tools.get_tool("list_tool_categories")

        result = await list_categories_tool.fn()

        assert len(result) == len(CATEGORY_META)
        category_names = {cat["name"] for cat in result}
        assert category_names == set(CATEGORY_META.keys())

    async def test_list_tool_categories_groups_by_tag(self, mcp_with_tools: FastMCP) -> None:
        list_categories_tool = await mcp_with_tools.get_tool("list_tool_categories")

        result = await list_categories_tool.fn()

        queues_cat = next(cat for cat in result if cat["name"] == "queues")
        assert queues_cat["tool_count"] == 2
        tool_names = {t["name"] for t in queues_cat["tools"]}
        assert tool_names == {"get_queue", "create_queue_from_template"}

    async def test_list_tool_categories_marks_write_tools(self, mcp_with_tools: FastMCP) -> None:
        list_categories_tool = await mcp_with_tools.get_tool("list_tool_categories")

        result = await list_categories_tool.fn()

        queues_cat = next(cat for cat in result if cat["name"] == "queues")
        tools_by_name = {t["name"]: t for t in queues_cat["tools"]}
        assert tools_by_name["get_queue"]["read_only"] is True
        assert tools_by_name["create_queue_from_template"]["read_only"] is False

    async def test_list_tool_categories_includes_keywords(self, mcp_with_tools: FastMCP) -> None:
        list_categories_tool = await mcp_with_tools.get_tool("list_tool_categories")

        result = await list_categories_tool.fn()

        queues_cat = next(cat for cat in result if cat["name"] == "queues")
        assert "keywords" in queues_cat
        assert "queue" in queues_cat["keywords"]

        hooks_cat = next(cat for cat in result if cat["name"] == "hooks")
        assert "hook" in hooks_cat["keywords"]
        assert "webhook" in hooks_cat["keywords"]

    async def test_get_mcp_mode_returns_current_mode(self, mcp_with_tools: FastMCP) -> None:
        tool = await mcp_with_tools.get_tool("get_mcp_mode")

        result = await tool.fn()

        assert result == {"mode": "read-write"}

    async def test_get_mcp_mode_returns_read_only(self) -> None:
        mcp = FastMCP("test-mode")
        register_discovery_tools(mcp, mcp_mode="read-only")

        tool = await mcp.get_tool("get_mcp_mode")

        result = await tool.fn()

        assert result == {"mode": "read-only"}

    async def test_list_tool_categories_empty_categories_have_zero_tools(self, mcp_with_tools: FastMCP) -> None:
        list_categories_tool = await mcp_with_tools.get_tool("list_tool_categories")

        result = await list_categories_tool.fn()

        # Categories without registered tools should show 0
        engines_cat = next(cat for cat in result if cat["name"] == "engines")
        assert engines_cat["tool_count"] == 0
        assert engines_cat["tools"] == []
