"""Tests for rossum_agent.tools.__init__ module."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from rossum_agent.tools import (
    INTERNAL_TOOLS,
    execute_tool,
    get_internal_tool_names,
    get_internal_tools,
    set_output_dir,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestInternalToolsRegistration:
    """Tests for internal tools registration."""

    def test_internal_tools_list_not_empty(self) -> None:
        """Test that INTERNAL_TOOLS list contains tools."""
        assert len(INTERNAL_TOOLS) > 0

    def test_get_internal_tools_returns_list(self) -> None:
        """Test that get_internal_tools returns a list of dicts."""
        tools = get_internal_tools()
        assert isinstance(tools, list)
        assert all(isinstance(t, dict) for t in tools)

    def test_get_internal_tools_has_required_fields(self) -> None:
        """Test that each tool dict has required fields."""
        tools = get_internal_tools()
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool

    def test_get_internal_tool_names_returns_set(self) -> None:
        """Test that get_internal_tool_names returns a set."""
        names = get_internal_tool_names()
        assert isinstance(names, set)
        assert len(names) > 0

    def test_internal_tool_names_match_tools(self) -> None:
        """Test that tool names match between list and set."""
        tools = get_internal_tools()
        names = get_internal_tool_names()
        tool_names = {t["name"] for t in tools}
        assert tool_names == names

    def test_known_tools_are_registered(self) -> None:
        """Test that known internal tools are registered."""
        names = get_internal_tool_names()
        assert "write_file" in names
        assert "search_knowledge_base" in names
        assert "evaluate_python_hook" in names
        assert "debug_hook" in names
        assert "load_skill" in names


class TestExecuteTool:
    """Tests for execute_tool function."""

    def test_execute_unknown_tool_raises_error(self) -> None:
        """Test that executing unknown tool raises ValueError."""
        with pytest.raises(ValueError, match="Unknown tool: nonexistent_tool"):
            execute_tool("nonexistent_tool", {}, INTERNAL_TOOLS)

    def test_execute_write_file_tool(self, tmp_path: Path) -> None:
        """Test executing write_file through execute_tool."""
        set_output_dir(tmp_path)
        try:
            result_json = execute_tool("write_file", {"filename": "test.txt", "content": "Hello"}, INTERNAL_TOOLS)
            result = json.loads(result_json)
            assert result["status"] == "success"
            assert (tmp_path / "test.txt").read_text() == "Hello"
        finally:
            set_output_dir(None)

    def test_execute_load_skill_tool(self) -> None:
        """Test executing load_skill through execute_tool."""
        result_json = execute_tool("load_skill", {"name": "nonexistent_skill"}, INTERNAL_TOOLS)
        result = json.loads(result_json)
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    def test_execute_tool_with_missing_args(self, tmp_path: Path) -> None:
        """Test executing tool with missing required arguments."""
        set_output_dir(tmp_path)
        try:
            with pytest.raises(TypeError):
                execute_tool("write_file", {}, INTERNAL_TOOLS)
        finally:
            set_output_dir(None)
