"""Tests for rossum_agent.tools.__init__ module."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from rossum_agent.tools import (
    INTERNAL_TOOLS,
    INTERNAL_WRITE_TOOL_NAMES,
    execute_tool,
    get_internal_tool_names,
    get_internal_tools,
)
from rossum_agent.tools.core import AgentContext, set_context

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

    def test_internal_tool_names_superset_of_visible_tools(self) -> None:
        """Test that executable tool names are a superset of visible tools.

        get_internal_tool_names() returns all executable tools (for dispatch routing),
        while get_internal_tools() returns only currently visible tools (some tools
        are hidden until their skill is loaded).
        """
        tools = get_internal_tools()
        names = get_internal_tool_names()
        tool_names = {t["name"] for t in tools}
        assert tool_names.issubset(names)

    def test_known_tools_are_registered(self) -> None:
        """Test that known internal tools are registered."""
        names = get_internal_tool_names()
        assert "write_file" in names
        assert "search_knowledge_base" in names
        assert "load_skill" in names
        assert "ask_user_question" in names

    def test_ask_user_question_in_internal_tools(self) -> None:
        """Test that ask_user_question appears in get_internal_tools."""
        tools = get_internal_tools()
        tool_names = {t["name"] for t in tools}
        assert "ask_user_question" in tool_names

    def test_ask_user_question_definition_structure(self) -> None:
        """Test that ask_user_question has correct tool definition structure."""
        tools = get_internal_tools()
        ask_tool = next(t for t in tools if t["name"] == "ask_user_question")
        assert "description" in ask_tool
        assert "input_schema" in ask_tool
        schema = ask_tool["input_schema"]
        assert schema["type"] == "object"
        assert "question" in schema["properties"]
        assert "options" in schema["properties"]
        assert "multi_select" in schema["properties"]
        assert "questions" in schema["properties"]

    def test_execute_python_always_visible(self) -> None:
        """execute_python is always available as an internal tool."""
        set_context(AgentContext())
        try:
            tools = get_internal_tools()
            tool_names = {t["name"] for t in tools}
            assert "execute_python" in tool_names
            assert "execute_python" in get_internal_tool_names()
        finally:
            set_context(AgentContext())

    def test_write_tools_hidden_in_read_only_mode(self) -> None:
        """Write tools (patch_schema_with_subagent, etc.) are hidden in read-only mode."""
        set_context(AgentContext(mcp_mode="read-only"))
        try:
            tools = get_internal_tools()
            tool_names = {t["name"] for t in tools}
            for name in INTERNAL_WRITE_TOOL_NAMES:
                assert name not in tool_names, f"{name} should be hidden in read-only mode"
        finally:
            set_context(AgentContext())

    def test_write_tools_visible_in_read_write_mode(self) -> None:
        """Write tools are visible in read-write mode."""
        set_context(AgentContext(mcp_mode="read-write"))
        try:
            tools = get_internal_tools()
            tool_names = {t["name"] for t in tools}
            assert "patch_schema_with_subagent" in tool_names
        finally:
            set_context(AgentContext())


class TestExecuteTool:
    """Tests for execute_tool function."""

    def test_execute_unknown_tool_raises_error(self) -> None:
        """Test that executing unknown tool raises ValueError."""
        with pytest.raises(ValueError, match="Unknown tool: nonexistent_tool"):
            execute_tool("nonexistent_tool", {}, INTERNAL_TOOLS)

    def test_execute_write_file_tool(self, tmp_path: Path) -> None:
        """Test executing write_file through execute_tool."""
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = execute_tool("write_file", {"filename": "test.txt", "content": "Hello"}, INTERNAL_TOOLS)
            result = json.loads(result_json)
            assert result["status"] == "success"
            assert (tmp_path / "test.txt").read_text() == "Hello"
        finally:
            set_context(AgentContext())

    def test_execute_load_skill_tool(self) -> None:
        """Test executing load_skill through execute_tool."""
        result_json = execute_tool("load_skill", {"name": "nonexistent_skill"}, INTERNAL_TOOLS)
        result = json.loads(result_json)
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    def test_execute_tool_with_missing_args(self, tmp_path: Path) -> None:
        """Test executing tool with missing required arguments."""
        set_context(AgentContext(output_dir=tmp_path))
        try:
            with pytest.raises(TypeError):
                execute_tool("write_file", {}, INTERNAL_TOOLS)
        finally:
            set_context(AgentContext())


class TestExecuteInternalTool:
    """Tests for execute_internal_tool function."""

    def test_execute_unknown_tool_raises_error(self) -> None:
        """Test that executing unknown tool raises ValueError."""
        from rossum_agent.tools import execute_internal_tool

        with pytest.raises(ValueError, match="Unknown internal tool: nonexistent_tool"):
            execute_internal_tool("nonexistent_tool", {})

    def test_execute_load_tool(self) -> None:
        """Test executing load_tool through execute_internal_tool."""
        from unittest.mock import patch

        from rossum_agent.tools import execute_internal_tool

        with patch("rossum_agent.tools.load_tool") as mock_load:
            mock_load.return_value = "Loaded tools: get_queue"
            result = execute_internal_tool("load_tool", {"tool_names": ["get_queue"]})

        mock_load.assert_called_once_with(["get_queue"])
        assert result == "Loaded tools: get_queue"

    def test_execute_load_tool_converts_to_string_list(self) -> None:
        """Test that tool_names are converted to string list."""
        from unittest.mock import patch

        from rossum_agent.tools import execute_internal_tool

        with patch("rossum_agent.tools.load_tool") as mock_load:
            mock_load.return_value = "Loaded tools"
            execute_internal_tool("load_tool", {"tool_names": ["get_queue", 123]})

        mock_load.assert_called_once_with(["get_queue", "123"])

    def test_execute_load_tool_handles_non_list(self) -> None:
        """Test that non-list tool_names argument is converted to list."""
        from unittest.mock import patch

        from rossum_agent.tools import execute_internal_tool

        with patch("rossum_agent.tools.load_tool") as mock_load:
            mock_load.return_value = "Loaded tools"
            execute_internal_tool("load_tool", {"tool_names": "get_queue"})

        mock_load.assert_called_once_with(["get_queue"])

    def test_execute_load_tool_handles_empty(self) -> None:
        """Test that empty tool_names list is handled."""
        from unittest.mock import patch

        from rossum_agent.tools import execute_internal_tool

        with patch("rossum_agent.tools.load_tool") as mock_load:
            mock_load.return_value = "No tools to load"
            execute_internal_tool("load_tool", {})

        mock_load.assert_called_once_with([])

    def test_execute_beta_tool(self, tmp_path: Path) -> None:
        """Test executing a BetaTool through execute_internal_tool."""
        from rossum_agent.tools import execute_internal_tool

        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = execute_internal_tool("write_file", {"filename": "test.txt", "content": "Hello"})
            result = json.loads(result_json)
            assert result["status"] == "success"
            assert (tmp_path / "test.txt").read_text() == "Hello"
        finally:
            set_context(AgentContext())

    def test_execute_python_alias_dispatches(self) -> None:
        from rossum_agent.tools import execute_internal_tool

        result = json.loads(execute_internal_tool("execute_python", {"code": "1 + 2"}))
        assert result["status"] == "success"
        assert result["result"] == 3

    def test_load_tool_is_in_internal_tools(self) -> None:
        """Test that load_tool is listed as an internal tool."""
        names = get_internal_tool_names()
        assert "load_tool" in names

        tools = get_internal_tools()
        tool_names = {t["name"] for t in tools}
        assert "load_tool" in tool_names

    def test_load_tool_definition_structure(self) -> None:
        """Test that load_tool has correct tool definition structure."""
        tools = get_internal_tools()
        load_tool_def = next(t for t in tools if t["name"] == "load_tool")

        assert "description" in load_tool_def
        assert "input_schema" in load_tool_def
        assert load_tool_def["input_schema"]["type"] == "object"
        assert "tool_names" in load_tool_def["input_schema"]["properties"]
        assert load_tool_def["input_schema"]["properties"]["tool_names"]["type"] == "array"
