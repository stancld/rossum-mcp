"""Tests for rossum_agent.agent.subagents module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rossum_agent.agent.subagents import (
    SubagentDefinition,
    SubagentRegistry,
    SubagentResult,
    SubagentRunner,
    SubagentType,
    get_subagent_registry,
    run_subagent,
)
from rossum_agent.agent.subagents.runner import FilteredMCPConnection


class TestSubagentType:
    """Test SubagentType enum."""

    def test_all_types_defined(self):
        """Test that all expected subagent types are defined."""
        assert SubagentType.DOCUMENT_ANALYZER == "document_analyzer"
        assert SubagentType.HOOK_DEBUGGER == "hook_debugger"
        assert SubagentType.SCHEMA_EXPERT == "schema_expert"
        assert SubagentType.RULE_OPTIMIZER == "rule_optimizer"

    def test_types_are_strings(self):
        """Test that SubagentType values are strings."""
        for t in SubagentType:
            assert isinstance(t.value, str)


class TestSubagentDefinition:
    """Test SubagentDefinition dataclass."""

    def test_creation(self):
        """Test SubagentDefinition creation."""
        definition = SubagentDefinition(
            type=SubagentType.DOCUMENT_ANALYZER,
            description="Test description",
            tools=["get_annotation", "list_annotations"],
            system_prompt="Test prompt",
            max_steps=10,
        )

        assert definition.type == SubagentType.DOCUMENT_ANALYZER
        assert definition.description == "Test description"
        assert definition.tools == ["get_annotation", "list_annotations"]
        assert definition.system_prompt == "Test prompt"
        assert definition.max_steps == 10

    def test_default_max_steps(self):
        """Test that max_steps has a default value."""
        definition = SubagentDefinition(
            type=SubagentType.HOOK_DEBUGGER,
            description="Test",
            tools=[],
            system_prompt="Test",
        )

        assert definition.max_steps == 15


class TestSubagentResult:
    """Test SubagentResult dataclass."""

    def test_successful_result(self):
        """Test a successful SubagentResult."""
        result = SubagentResult(
            subagent_type=SubagentType.DOCUMENT_ANALYZER,
            task="Analyze document",
            result="Analysis complete",
            steps_taken=5,
            input_tokens=100,
            output_tokens=50,
            tool_calls=["get_annotation", "list_annotations"],
        )

        assert result.success is True
        assert result.error is None
        assert result.result == "Analysis complete"
        assert result.steps_taken == 5

    def test_failed_result(self):
        """Test a failed SubagentResult."""
        result = SubagentResult(
            subagent_type=SubagentType.HOOK_DEBUGGER,
            task="Debug hook",
            error="Connection failed",
        )

        assert result.success is False
        assert result.result is None
        assert result.error == "Connection failed"

    def test_default_values(self):
        """Test SubagentResult default values."""
        result = SubagentResult(
            subagent_type=SubagentType.SCHEMA_EXPERT,
            task="Analyze schema",
        )

        assert result.result is None
        assert result.steps_taken == 0
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.error is None
        assert result.tool_calls == []
        assert result.success is False  # No result, so not successful


class TestSubagentRegistry:
    """Test SubagentRegistry class."""

    def test_get_subagent_registry_singleton(self):
        """Test that get_subagent_registry returns a singleton."""
        registry1 = get_subagent_registry()
        registry2 = get_subagent_registry()
        assert registry1 is registry2

    def test_registry_has_all_types(self):
        """Test that the registry contains all subagent types."""
        registry = SubagentRegistry()
        types = registry.list_types()

        assert SubagentType.DOCUMENT_ANALYZER in types
        assert SubagentType.HOOK_DEBUGGER in types
        assert SubagentType.SCHEMA_EXPERT in types
        assert SubagentType.RULE_OPTIMIZER in types

    def test_get_by_type(self):
        """Test getting a subagent definition by type."""
        registry = SubagentRegistry()
        definition = registry.get(SubagentType.DOCUMENT_ANALYZER)

        assert definition.type == SubagentType.DOCUMENT_ANALYZER
        assert len(definition.tools) > 0
        assert len(definition.system_prompt) > 0

    def test_get_by_name(self):
        """Test getting a subagent definition by name string."""
        registry = SubagentRegistry()
        definition = registry.get_by_name("hook_debugger")

        assert definition.type == SubagentType.HOOK_DEBUGGER

    def test_get_by_name_invalid(self):
        """Test that get_by_name raises ValueError for invalid name."""
        registry = SubagentRegistry()

        with pytest.raises(ValueError) as exc_info:
            registry.get_by_name("invalid_type")

        assert "Unknown subagent type" in str(exc_info.value)
        assert "invalid_type" in str(exc_info.value)

    def test_get_unknown_type_raises(self):
        """Test that get raises KeyError for unknown type."""
        registry = SubagentRegistry()

        with pytest.raises(KeyError):
            registry.get(MagicMock())  # type: ignore[arg-type]

    def test_list_all(self):
        """Test listing all subagent definitions."""
        registry = SubagentRegistry()
        definitions = registry.list_all()

        assert len(definitions) == 4
        assert all(isinstance(d, SubagentDefinition) for d in definitions)

    def test_document_analyzer_tools(self):
        """Test that document analyzer has correct tools."""
        registry = SubagentRegistry()
        definition = registry.get(SubagentType.DOCUMENT_ANALYZER)

        assert "get_annotation" in definition.tools
        assert "get_annotation_content" in definition.tools

    def test_hook_debugger_tools(self):
        """Test that hook debugger has correct tools."""
        registry = SubagentRegistry()
        definition = registry.get(SubagentType.HOOK_DEBUGGER)

        assert "get_hook" in definition.tools
        assert "list_hooks" in definition.tools

    def test_schema_expert_tools(self):
        """Test that schema expert has correct tools."""
        registry = SubagentRegistry()
        definition = registry.get(SubagentType.SCHEMA_EXPERT)

        assert "get_schema" in definition.tools
        assert "list_schemas" in definition.tools

    def test_rule_optimizer_tools(self):
        """Test that rule optimizer has correct tools."""
        registry = SubagentRegistry()
        definition = registry.get(SubagentType.RULE_OPTIMIZER)

        assert "list_rules" in definition.tools
        assert "get_schema" in definition.tools


class TestFilteredMCPConnection:
    """Test FilteredMCPConnection wrapper."""

    @pytest.fixture
    def mock_mcp_connection(self):
        """Create a mock MCP connection."""
        connection = AsyncMock()
        tool1 = MagicMock()
        tool1.name = "get_annotation"
        tool2 = MagicMock()
        tool2.name = "list_hooks"
        tool3 = MagicMock()
        tool3.name = "get_queue"
        connection.get_tools.return_value = [tool1, tool2, tool3]
        return connection

    @pytest.mark.asyncio
    async def test_get_tools_filters_by_allowed(self, mock_mcp_connection):
        """Test that get_tools only returns allowed tools."""
        filtered = FilteredMCPConnection(mock_mcp_connection, ["get_annotation", "get_queue"])

        tools = await filtered.get_tools()

        assert len(tools) == 2
        tool_names = [t.name for t in tools]
        assert "get_annotation" in tool_names
        assert "get_queue" in tool_names
        assert "list_hooks" not in tool_names

    @pytest.mark.asyncio
    async def test_get_tools_caches_result(self, mock_mcp_connection):
        """Test that get_tools caches the filtered tools."""
        filtered = FilteredMCPConnection(mock_mcp_connection, ["get_annotation"])

        await filtered.get_tools()
        await filtered.get_tools()

        mock_mcp_connection.get_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_tool_allowed(self, mock_mcp_connection):
        """Test that call_tool works for allowed tools."""
        mock_mcp_connection.call_tool.return_value = {"result": "success"}
        filtered = FilteredMCPConnection(mock_mcp_connection, ["get_annotation"])

        result = await filtered.call_tool("get_annotation", {"id": 123})

        mock_mcp_connection.call_tool.assert_called_once_with("get_annotation", {"id": 123})
        assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_call_tool_not_allowed_raises(self, mock_mcp_connection):
        """Test that call_tool raises ValueError for non-allowed tools."""
        filtered = FilteredMCPConnection(mock_mcp_connection, ["get_annotation"])

        with pytest.raises(ValueError) as exc_info:
            await filtered.call_tool("list_hooks", {})

        assert "list_hooks" in str(exc_info.value)
        assert "not allowed" in str(exc_info.value)


class TestSubagentRunner:
    """Test SubagentRunner class."""

    @pytest.fixture
    def mock_mcp_connection(self):
        """Create a mock MCP connection."""
        connection = AsyncMock()
        tool = MagicMock()
        tool.name = "get_annotation"
        tool.description = "Get annotation"
        tool.inputSchema = {"type": "object", "properties": {}}
        connection.get_tools.return_value = [tool]
        return connection

    @pytest.mark.asyncio
    async def test_run_with_string_type(self, mock_mcp_connection):
        """Test running a subagent with string type."""
        runner = SubagentRunner(mock_mcp_connection)

        with patch("rossum_agent.agent.subagents.runner.create_bedrock_client"):
            with patch("rossum_agent.agent.core.RossumAgent") as mock_agent_class:
                mock_agent = AsyncMock()

                async def mock_run(task):
                    from rossum_agent.agent.models import AgentStep

                    yield AgentStep(
                        step_number=1,
                        final_answer="Analysis complete",
                        is_final=True,
                        is_streaming=False,
                    )

                mock_agent.run = mock_run
                mock_agent._total_input_tokens = 100
                mock_agent._total_output_tokens = 50
                mock_agent_class.return_value = mock_agent

                result = await runner.run("document_analyzer", "Analyze this")

        assert result.subagent_type == SubagentType.DOCUMENT_ANALYZER
        assert result.success is True
        assert result.result == "Analysis complete"

    @pytest.mark.asyncio
    async def test_run_with_enum_type(self, mock_mcp_connection):
        """Test running a subagent with enum type."""
        runner = SubagentRunner(mock_mcp_connection)

        with patch("rossum_agent.agent.subagents.runner.create_bedrock_client"):
            with patch("rossum_agent.agent.core.RossumAgent") as mock_agent_class:
                mock_agent = AsyncMock()

                async def mock_run(task):
                    from rossum_agent.agent.models import AgentStep

                    yield AgentStep(
                        step_number=1,
                        final_answer="Done",
                        is_final=True,
                        is_streaming=False,
                    )

                mock_agent.run = mock_run
                mock_agent._total_input_tokens = 0
                mock_agent._total_output_tokens = 0
                mock_agent_class.return_value = mock_agent

                result = await runner.run(SubagentType.HOOK_DEBUGGER, "Debug this")

        assert result.subagent_type == SubagentType.HOOK_DEBUGGER

    @pytest.mark.asyncio
    async def test_run_tracks_tool_calls(self, mock_mcp_connection):
        """Test that run tracks tool calls made by the subagent."""
        runner = SubagentRunner(mock_mcp_connection)

        with patch("rossum_agent.agent.subagents.runner.create_bedrock_client"):
            with patch("rossum_agent.agent.core.RossumAgent") as mock_agent_class:
                mock_agent = AsyncMock()

                async def mock_run(task):
                    from rossum_agent.agent.models import AgentStep, ToolCall

                    yield AgentStep(
                        step_number=1,
                        tool_calls=[ToolCall(id="tc1", name="get_annotation", arguments={})],
                        is_streaming=False,
                    )
                    yield AgentStep(
                        step_number=2,
                        final_answer="Done",
                        is_final=True,
                        is_streaming=False,
                    )

                mock_agent.run = mock_run
                mock_agent._total_input_tokens = 100
                mock_agent._total_output_tokens = 50
                mock_agent_class.return_value = mock_agent

                result = await runner.run(SubagentType.DOCUMENT_ANALYZER, "Test")

        assert "get_annotation" in result.tool_calls

    @pytest.mark.asyncio
    async def test_run_handles_error(self, mock_mcp_connection):
        """Test that run handles errors gracefully."""
        runner = SubagentRunner(mock_mcp_connection)

        with patch("rossum_agent.agent.subagents.runner.create_bedrock_client"):
            with patch("rossum_agent.agent.core.RossumAgent") as mock_agent_class:
                mock_agent = AsyncMock()

                async def mock_run(task):
                    raise Exception("Test error")
                    yield  # Make it a generator

                mock_agent.run = mock_run
                mock_agent_class.return_value = mock_agent

                result = await runner.run(SubagentType.DOCUMENT_ANALYZER, "Test")

        assert result.success is False
        assert "Test error" in result.error

    @pytest.mark.asyncio
    async def test_run_handles_agent_error_step(self, mock_mcp_connection):
        """Test that run handles error steps from the agent."""
        runner = SubagentRunner(mock_mcp_connection)

        with patch("rossum_agent.agent.subagents.runner.create_bedrock_client"):
            with patch("rossum_agent.agent.core.RossumAgent") as mock_agent_class:
                mock_agent = AsyncMock()

                async def mock_run(task):
                    from rossum_agent.agent.models import AgentStep

                    yield AgentStep(
                        step_number=1,
                        error="Rate limit exceeded",
                        is_final=True,
                        is_streaming=False,
                    )

                mock_agent.run = mock_run
                mock_agent._total_input_tokens = 0
                mock_agent._total_output_tokens = 0
                mock_agent_class.return_value = mock_agent

                result = await runner.run(SubagentType.DOCUMENT_ANALYZER, "Test")

        assert result.success is False
        assert result.error == "Rate limit exceeded"


class TestRunSubagentFunction:
    """Test the run_subagent convenience function."""

    @pytest.mark.asyncio
    async def test_run_subagent_creates_runner(self):
        """Test that run_subagent creates a runner and executes."""
        mock_connection = AsyncMock()
        mock_connection.get_tools.return_value = []

        with patch("rossum_agent.agent.subagents.runner.SubagentRunner") as mock_runner_class:
            mock_runner = AsyncMock()
            mock_runner.run.return_value = SubagentResult(
                subagent_type=SubagentType.DOCUMENT_ANALYZER,
                task="Test",
                result="Done",
            )
            mock_runner_class.return_value = mock_runner

            result = await run_subagent(mock_connection, SubagentType.DOCUMENT_ANALYZER, "Test task")

        mock_runner_class.assert_called_once_with(mock_connection)
        mock_runner.run.assert_called_once_with(SubagentType.DOCUMENT_ANALYZER, "Test task")
        assert result.result == "Done"
