"""Tests for rossum_agent.async_tools module."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from rossum_agent.agent.subagents.types import SubagentResult, SubagentType
from rossum_agent.async_tools import (
    TASK_TOOL_NAME,
    execute_task_tool,
    get_async_tool_definitions,
    get_async_tool_names,
    get_task_tool_definition,
    is_task_tool,
)


class TestTaskToolDefinition:
    """Test Task tool definition."""

    def test_task_tool_name(self):
        """Test that the task tool has the expected name."""
        assert TASK_TOOL_NAME == "delegate_task"

    def test_get_task_tool_definition_structure(self):
        """Test that the task tool definition has the correct structure."""
        definition = get_task_tool_definition()

        assert definition["name"] == "delegate_task"
        assert "description" in definition
        assert "input_schema" in definition

    def test_get_task_tool_definition_schema(self):
        """Test that the task tool schema has required properties."""
        definition = get_task_tool_definition()
        schema = definition["input_schema"]

        assert schema["type"] == "object"
        assert "subagent_type" in schema["properties"]
        assert "task" in schema["properties"]
        assert "subagent_type" in schema["required"]
        assert "task" in schema["required"]

    def test_get_task_tool_definition_includes_subagent_types(self):
        """Test that the task tool includes all subagent types."""
        definition = get_task_tool_definition()
        schema = definition["input_schema"]
        enum_values = schema["properties"]["subagent_type"]["enum"]

        assert "document_analyzer" in enum_values
        assert "hook_debugger" in enum_values
        assert "schema_expert" in enum_values
        assert "rule_optimizer" in enum_values

    def test_get_task_tool_definition_description(self):
        """Test that the description mentions available subagents."""
        definition = get_task_tool_definition()
        description = definition["description"]

        assert "document_analyzer" in description
        assert "hook_debugger" in description
        assert "schema_expert" in description
        assert "rule_optimizer" in description


class TestIsTaskTool:
    """Test is_task_tool function."""

    def test_returns_true_for_task_tool(self):
        """Test that is_task_tool returns True for the task tool name."""
        assert is_task_tool("delegate_task") is True

    def test_returns_false_for_other_tools(self):
        """Test that is_task_tool returns False for other tool names."""
        assert is_task_tool("get_annotation") is False
        assert is_task_tool("write_file") is False
        assert is_task_tool("") is False


class TestGetAsyncToolDefinitions:
    """Test get_async_tool_definitions function."""

    def test_returns_list_with_task_tool(self):
        """Test that get_async_tool_definitions includes the task tool."""
        definitions = get_async_tool_definitions()

        assert len(definitions) >= 1
        tool_names = [d["name"] for d in definitions]
        assert "delegate_task" in tool_names


class TestGetAsyncToolNames:
    """Test get_async_tool_names function."""

    def test_returns_set_with_task_tool(self):
        """Test that get_async_tool_names includes the task tool name."""
        names = get_async_tool_names()

        assert isinstance(names, set)
        assert "delegate_task" in names


class TestExecuteTaskTool:
    """Test execute_task_tool function."""

    @pytest.mark.asyncio
    async def test_executes_subagent(self):
        """Test that execute_task_tool runs a subagent and returns result."""
        mock_connection = AsyncMock()

        with patch("rossum_agent.async_tools.run_subagent") as mock_run:
            mock_run.return_value = SubagentResult(
                subagent_type=SubagentType.DOCUMENT_ANALYZER,
                task="Test task",
                result="Analysis complete",
                steps_taken=3,
                input_tokens=100,
                output_tokens=50,
                tool_calls=["get_annotation"],
            )

            result = await execute_task_tool(mock_connection, "document_analyzer", "Test task")

        mock_run.assert_called_once_with(mock_connection, "document_analyzer", "Test task")
        assert "Analysis complete" in result
        assert "document_analyzer" in result

    @pytest.mark.asyncio
    async def test_returns_error_on_failure(self):
        """Test that execute_task_tool returns error message on failure."""
        mock_connection = AsyncMock()

        with patch("rossum_agent.async_tools.run_subagent") as mock_run:
            mock_run.return_value = SubagentResult(
                subagent_type=SubagentType.HOOK_DEBUGGER,
                task="Debug task",
                error="Connection failed",
            )

            result = await execute_task_tool(mock_connection, "hook_debugger", "Debug task")

        assert "Subagent failed" in result
        assert "Connection failed" in result

    @pytest.mark.asyncio
    async def test_result_includes_execution_summary(self):
        """Test that the result includes execution summary."""
        mock_connection = AsyncMock()

        with patch("rossum_agent.async_tools.run_subagent") as mock_run:
            mock_run.return_value = SubagentResult(
                subagent_type=SubagentType.SCHEMA_EXPERT,
                task="Analyze schema",
                result="Schema has 5 sections",
                steps_taken=2,
                input_tokens=150,
                output_tokens=75,
                tool_calls=["get_schema", "list_schemas"],
            )

            result = await execute_task_tool(mock_connection, "schema_expert", "Analyze schema")

        assert "Steps taken: 2" in result
        assert "get_schema" in result
        assert "list_schemas" in result
        assert "150 input" in result
        assert "75 output" in result
