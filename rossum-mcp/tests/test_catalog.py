"""Tests for the tool catalog and discovery modules."""

from __future__ import annotations

import pytest
from fastmcp import FastMCP
from rossum_mcp.tools.catalog import TOOL_CATALOG, get_catalog_summary
from rossum_mcp.tools.discovery import register_discovery_tools


class TestToolCatalog:
    """Tests for TOOL_CATALOG structure."""

    def test_catalog_has_all_expected_categories(self) -> None:
        expected_categories = {
            "annotations",
            "queues",
            "schemas",
            "engines",
            "hooks",
            "email_templates",
            "document_relations",
            "relations",
            "rules",
            "users",
            "workspaces",
        }
        assert set(TOOL_CATALOG.keys()) == expected_categories

    def test_each_category_has_tools(self) -> None:
        for category_name, category in TOOL_CATALOG.items():
            assert len(category.tools) > 0, f"Category {category_name} has no tools"

    def test_each_category_has_description(self) -> None:
        for category_name, category in TOOL_CATALOG.items():
            assert category.description, f"Category {category_name} has no description"

    def test_each_category_has_keywords(self) -> None:
        for category_name, category in TOOL_CATALOG.items():
            assert len(category.keywords) > 0, f"Category {category_name} has no keywords"

    def test_annotations_category_tools(self) -> None:
        annotations = TOOL_CATALOG["annotations"]
        tool_names = {t.name for t in annotations.tools}
        expected = {
            "upload_document",
            "get_annotation",
            "list_annotations",
            "start_annotation",
            "bulk_update_annotation_fields",
            "confirm_annotation",
        }
        assert tool_names == expected

    def test_queues_category_tools(self) -> None:
        queues = TOOL_CATALOG["queues"]
        tool_names = {t.name for t in queues.tools}
        expected = {
            "get_queue",
            "list_queues",
            "get_queue_schema",
            "get_queue_engine",
            "create_queue",
            "update_queue",
            "get_queue_template_names",
            "create_queue_from_template",
        }
        assert tool_names == expected


class TestCatalogSummary:
    """Tests for get_catalog_summary function."""

    def test_summary_contains_all_categories(self) -> None:
        summary = get_catalog_summary()
        for category_name in TOOL_CATALOG:
            assert category_name in summary

    def test_summary_contains_tool_names(self) -> None:
        summary = get_catalog_summary()
        # Check a few sample tools are in the summary
        assert "get_queue" in summary
        assert "list_annotations" in summary
        assert "patch_schema" in summary


class TestDiscoveryTools:
    """Tests for discovery MCP tools."""

    @pytest.fixture
    def mcp_with_discovery(self) -> FastMCP:
        """Create FastMCP instance with discovery tools registered."""
        mcp = FastMCP("test-discovery")
        register_discovery_tools(mcp)
        return mcp

    async def test_list_tool_categories_returns_all_categories(self, mcp_with_discovery: FastMCP) -> None:
        tools = mcp_with_discovery._tool_manager._tools
        list_categories_tool = tools["list_tool_categories"]

        result = await list_categories_tool.fn()

        assert len(result) == len(TOOL_CATALOG)
        category_names = {cat["name"] for cat in result}
        assert category_names == set(TOOL_CATALOG.keys())

    async def test_list_tool_categories_includes_tool_info(self, mcp_with_discovery: FastMCP) -> None:
        tools = mcp_with_discovery._tool_manager._tools
        list_categories_tool = tools["list_tool_categories"]

        result = await list_categories_tool.fn()

        # Find queues category
        queues_cat = next(cat for cat in result if cat["name"] == "queues")
        assert "description" in queues_cat
        assert "tool_count" in queues_cat
        assert "tools" in queues_cat
        assert queues_cat["tool_count"] == len(TOOL_CATALOG["queues"].tools)

    async def test_list_tool_categories_includes_keywords(self, mcp_with_discovery: FastMCP) -> None:
        tools = mcp_with_discovery._tool_manager._tools
        list_categories_tool = tools["list_tool_categories"]

        result = await list_categories_tool.fn()

        # Find queues category
        queues_cat = next(cat for cat in result if cat["name"] == "queues")
        assert "keywords" in queues_cat
        assert "queue" in queues_cat["keywords"]

        # Find hooks category
        hooks_cat = next(cat for cat in result if cat["name"] == "hooks")
        assert "hook" in hooks_cat["keywords"]
        assert "webhook" in hooks_cat["keywords"]
