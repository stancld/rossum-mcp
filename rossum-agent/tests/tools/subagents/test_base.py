"""Tests for rossum_agent.tools.subagents.base module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from rossum_agent.tools.core import AgentContext, set_context
from rossum_agent.tools.subagents.base import (
    SubAgent,
    SubAgentConfig,
    SubAgentResult,
)


class TestSubAgentConfig:
    """Test SubAgentConfig dataclass."""

    def test_required_fields(self):
        """Test that required fields are properly set."""
        config = SubAgentConfig(
            tool_name="test_tool",
            system_prompt="Test prompt",
            tools=[{"name": "tool1"}],
        )
        assert config.tool_name == "test_tool"
        assert config.system_prompt == "Test prompt"
        assert config.tools == [{"name": "tool1"}]

    def test_default_values(self):
        """Test default values for optional fields."""
        config = SubAgentConfig(
            tool_name="test",
            system_prompt="prompt",
            tools=[],
        )
        assert config.max_iterations == 15
        assert config.max_tokens == 16384

    def test_custom_max_iterations(self):
        """Test custom max_iterations setting."""
        config = SubAgentConfig(
            tool_name="test",
            system_prompt="prompt",
            tools=[],
            max_iterations=5,
            max_tokens=4096,
        )
        assert config.max_iterations == 5
        assert config.max_tokens == 4096


class TestSubAgentResult:
    """Test SubAgentResult dataclass."""

    def test_all_fields(self):
        """Test that all fields are properly set."""
        result = SubAgentResult(
            analysis="Test analysis",
            input_tokens=100,
            output_tokens=50,
            iterations_used=3,
        )
        assert result.analysis == "Test analysis"
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.iterations_used == 3

    def test_tool_calls_defaults_to_none(self):
        """Test that tool_calls defaults to None when not provided."""
        result = SubAgentResult(
            analysis="Test",
            input_tokens=0,
            output_tokens=0,
            iterations_used=1,
        )
        assert result.tool_calls is None

    def test_tool_calls_with_value(self):
        """Test that tool_calls can be set."""
        calls = [{"tool": "test_tool", "input": {"key": "val"}}]
        result = SubAgentResult(
            analysis="Test",
            input_tokens=0,
            output_tokens=0,
            iterations_used=1,
            tool_calls=calls,
        )
        assert result.tool_calls == calls


class ConcreteSubAgent(SubAgent):
    """Concrete implementation for testing."""

    def execute_tool(self, tool_name: str, tool_input: dict) -> str:
        return f"Executed {tool_name}"

    def process_response_block(self, block, iteration: int, max_iterations: int) -> dict | None:
        return None


class TestSubAgent:
    """Test SubAgent base class."""

    def test_init(self):
        """Test initialization."""
        config = SubAgentConfig(
            tool_name="test",
            system_prompt="prompt",
            tools=[],
        )
        agent = ConcreteSubAgent(config)
        assert agent.config == config
        assert agent._client is None

    def test_lazy_client_creation(self):
        """Test that client is created lazily."""
        config = SubAgentConfig(
            tool_name="test",
            system_prompt="prompt",
            tools=[],
        )
        agent = ConcreteSubAgent(config)

        mock_client = MagicMock()
        with patch(
            "rossum_agent.tools.subagents.base.create_bedrock_client",
            return_value=mock_client,
        ):
            client = agent.client

            assert client == mock_client
            assert agent._client == mock_client

            _ = agent.client
            assert agent._client == mock_client

    def test_run_completes_on_end_of_turn(self):
        """Test that run completes when stop_reason is end_of_turn."""
        config = SubAgentConfig(
            tool_name="test",
            system_prompt="prompt",
            tools=[],
            max_iterations=5,
        )
        agent = ConcreteSubAgent(config)

        mock_text_block = MagicMock()
        mock_text_block.text = "Analysis result"
        mock_text_block.type = "text"

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_of_turn"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.usage.cache_creation_input_tokens = 0
        mock_response.usage.cache_read_input_tokens = 0

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        set_context(AgentContext(progress_callback=MagicMock(), token_callback=MagicMock()))
        try:
            with patch(
                "rossum_agent.tools.subagents.base.create_bedrock_client",
                return_value=mock_client,
            ):
                result = agent.run("Test message")

                assert result.analysis == "Analysis result"
                assert result.input_tokens == 100
                assert result.output_tokens == 50
                assert result.iterations_used == 1
        finally:
            set_context(AgentContext())

    def test_run_iterates_with_tool_use(self):
        """Test that run iterates when tools are used."""
        config = SubAgentConfig(
            tool_name="test",
            system_prompt="prompt",
            tools=[{"name": "test_tool"}],
            max_iterations=5,
        )
        agent = ConcreteSubAgent(config)

        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "test_tool"
        mock_tool_block.input = {}
        mock_tool_block.id = "tool_1"

        first_response = MagicMock()
        first_response.content = [mock_tool_block]
        first_response.stop_reason = "tool_use"
        first_response.usage.input_tokens = 100
        first_response.usage.output_tokens = 50

        mock_text_block = MagicMock()
        mock_text_block.text = "Final result"
        mock_text_block.type = "text"

        second_response = MagicMock()
        second_response.content = [mock_text_block]
        second_response.stop_reason = "end_of_turn"
        second_response.usage.input_tokens = 150
        second_response.usage.output_tokens = 75

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [first_response, second_response]

        set_context(AgentContext(progress_callback=MagicMock(), token_callback=MagicMock()))
        try:
            with patch(
                "rossum_agent.tools.subagents.base.create_bedrock_client",
                return_value=mock_client,
            ):
                result = agent.run("Test message")

                assert result.analysis == "Final result"
                assert result.input_tokens == 250
                assert result.output_tokens == 125
                assert result.iterations_used == 2
                assert mock_client.messages.create.call_count == 2
                assert result.tool_calls == [{"tool": "test_tool", "input": {}}]
        finally:
            set_context(AgentContext())

    def test_run_no_tool_calls_returns_none(self):
        """Test that run returns tool_calls=None when no tools are used."""
        config = SubAgentConfig(
            tool_name="test",
            system_prompt="prompt",
            tools=[],
            max_iterations=5,
        )
        agent = ConcreteSubAgent(config)

        mock_text_block = MagicMock()
        mock_text_block.text = "Direct answer"
        mock_text_block.type = "text"

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_of_turn"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.usage.cache_creation_input_tokens = 0
        mock_response.usage.cache_read_input_tokens = 0

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        set_context(AgentContext(progress_callback=MagicMock(), token_callback=MagicMock()))
        try:
            with patch(
                "rossum_agent.tools.subagents.base.create_bedrock_client",
                return_value=mock_client,
            ):
                result = agent.run("Test message")

                assert result.tool_calls is None
        finally:
            set_context(AgentContext())

    def test_run_reports_token_usage(self):
        """Test that token usage is reported via callback."""
        config = SubAgentConfig(
            tool_name="test",
            system_prompt="prompt",
            tools=[],
        )
        agent = ConcreteSubAgent(config)

        token_reports = []

        mock_response = MagicMock()
        mock_response.content = []
        mock_response.stop_reason = "end_of_turn"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.usage.cache_creation_input_tokens = 0
        mock_response.usage.cache_read_input_tokens = 0

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        set_context(
            AgentContext(
                progress_callback=MagicMock(),
                token_callback=lambda usage: token_reports.append(usage),
            )
        )
        try:
            with patch(
                "rossum_agent.tools.subagents.base.create_bedrock_client",
                return_value=mock_client,
            ):
                agent.run("Test")

                assert len(token_reports) == 1
                assert token_reports[0].tool_name == "test"
                assert token_reports[0].input_tokens == 100
                assert token_reports[0].output_tokens == 50
                assert token_reports[0].iteration == 1
        finally:
            set_context(AgentContext())

    def test_run_handles_tool_execution_error(self):
        """Test that tool execution errors are handled gracefully."""
        config = SubAgentConfig(
            tool_name="test",
            system_prompt="prompt",
            tools=[{"name": "failing_tool"}],
        )

        class FailingAgent(SubAgent):
            def execute_tool(self, tool_name: str, tool_input: dict) -> str:
                raise RuntimeError("Tool failed")

            def process_response_block(self, block, iteration: int, max_iterations: int) -> dict | None:
                return None

        agent = FailingAgent(config)

        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "failing_tool"
        mock_tool_block.input = {}
        mock_tool_block.id = "tool_1"

        first_response = MagicMock()
        first_response.content = [mock_tool_block]
        first_response.stop_reason = "tool_use"
        first_response.usage.input_tokens = 100
        first_response.usage.output_tokens = 50

        mock_text_block = MagicMock()
        mock_text_block.text = "Handled error"
        mock_text_block.type = "text"

        second_response = MagicMock()
        second_response.content = [mock_text_block]
        second_response.stop_reason = "end_of_turn"
        second_response.usage.input_tokens = 150
        second_response.usage.output_tokens = 75

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [first_response, second_response]

        set_context(AgentContext(progress_callback=MagicMock(), token_callback=MagicMock()))
        try:
            with patch(
                "rossum_agent.tools.subagents.base.create_bedrock_client",
                return_value=mock_client,
            ):
                result = agent.run("Test")

                assert result.analysis == "Handled error"
        finally:
            set_context(AgentContext())

    def test_run_returns_error_on_exception(self):
        """Test that run returns error message on exception."""
        config = SubAgentConfig(
            tool_name="test",
            system_prompt="prompt",
            tools=[],
        )
        agent = ConcreteSubAgent(config)

        with patch(
            "rossum_agent.tools.subagents.base.create_bedrock_client",
            side_effect=RuntimeError("Connection failed"),
        ):
            result = agent.run("Test")

            assert "Error calling Opus sub-agent" in result.analysis
            assert "Connection failed" in result.analysis
            assert result.input_tokens == 0
            assert result.output_tokens == 0

    def test_run_final_iteration_omits_tools_for_synthesis(self):
        """Test that the final iteration omits tools to force answer synthesis."""
        config = SubAgentConfig(
            tool_name="test",
            system_prompt="prompt",
            tools=[{"name": "tool"}],
            max_iterations=2,
        )
        agent = ConcreteSubAgent(config)

        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "tool"
        mock_tool_block.input = {}
        mock_tool_block.id = "tool_1"

        tool_use_response = MagicMock()
        tool_use_response.content = [mock_tool_block]
        tool_use_response.stop_reason = "tool_use"
        tool_use_response.usage.input_tokens = 100
        tool_use_response.usage.output_tokens = 50
        tool_use_response.usage.cache_creation_input_tokens = 0
        tool_use_response.usage.cache_read_input_tokens = 0

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Synthesized answer from gathered information"

        synthesis_response = MagicMock()
        synthesis_response.content = [mock_text_block]
        synthesis_response.stop_reason = "end_of_turn"
        synthesis_response.usage.input_tokens = 100
        synthesis_response.usage.output_tokens = 50
        synthesis_response.usage.cache_creation_input_tokens = 0
        synthesis_response.usage.cache_read_input_tokens = 0

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [tool_use_response, synthesis_response]

        set_context(AgentContext(progress_callback=MagicMock(), token_callback=MagicMock()))
        try:
            with patch(
                "rossum_agent.tools.subagents.base.create_bedrock_client",
                return_value=mock_client,
            ):
                result = agent.run("Test")

                assert result.iterations_used == 2
                assert result.analysis == "Synthesized answer from gathered information"
                assert result.input_tokens == 200
                assert result.output_tokens == 100

                # Verify final iteration was called without tools and with synthesis prompt
                calls = mock_client.messages.create.call_args_list
                assert len(calls) == 2
                assert len(calls[0].kwargs["tools"]) == 1
                assert calls[0].kwargs["tools"][0]["name"] == "tool"
                assert calls[1].kwargs["tools"] == []
                final_messages = calls[1].kwargs["messages"]
                assert final_messages[-1] == {
                    "role": "user",
                    "content": "Synthesize your final answer from the information gathered so far.",
                }
        finally:
            set_context(AgentContext())

    def test_run_max_iterations_tracks_tool_calls(self):
        """Test that tool_calls from non-final iterations are tracked."""
        config = SubAgentConfig(
            tool_name="test",
            system_prompt="prompt",
            tools=[{"name": "tool"}],
            max_iterations=2,
        )
        agent = ConcreteSubAgent(config)

        mock_tool_block = MagicMock(spec=["type", "name", "input", "id"])
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "tool"
        mock_tool_block.input = {"q": "test"}
        mock_tool_block.id = "tool_1"

        tool_use_response = MagicMock()
        tool_use_response.content = [mock_tool_block]
        tool_use_response.stop_reason = "tool_use"
        tool_use_response.usage.input_tokens = 100
        tool_use_response.usage.output_tokens = 50
        tool_use_response.usage.cache_creation_input_tokens = 0
        tool_use_response.usage.cache_read_input_tokens = 0

        mock_text_block = MagicMock(spec=["type", "text"])
        mock_text_block.type = "text"
        mock_text_block.text = "Final answer"

        synthesis_response = MagicMock()
        synthesis_response.content = [mock_text_block]
        synthesis_response.stop_reason = "end_of_turn"
        synthesis_response.usage.input_tokens = 100
        synthesis_response.usage.output_tokens = 50
        synthesis_response.usage.cache_creation_input_tokens = 0
        synthesis_response.usage.cache_read_input_tokens = 0

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [tool_use_response, synthesis_response]

        set_context(AgentContext(progress_callback=MagicMock(), token_callback=MagicMock()))
        try:
            with (
                patch(
                    "rossum_agent.tools.subagents.base.create_bedrock_client",
                    return_value=mock_client,
                ),
                patch("rossum_agent.tools.subagents.base.logger"),
            ):
                result = agent.run("Test")

                # Only iteration 1 produced tool calls; iteration 2 was synthesis-only
                assert result.tool_calls == [
                    {"tool": "tool", "input": {"q": "test"}},
                ]
        finally:
            set_context(AgentContext())

    def test_process_response_block_concrete_impl(self):
        """Test that ConcreteSubAgent's process_response_block returns None."""
        config = SubAgentConfig(
            tool_name="test",
            system_prompt="prompt",
            tools=[],
        )
        agent = ConcreteSubAgent(config)

        block = MagicMock()
        result = agent.process_response_block(block, 1, 5)

        assert result is None

    def test_run_sends_system_with_cache_control(self):
        """Test that run sends system prompt as list with cache_control."""
        config = SubAgentConfig(
            tool_name="test",
            system_prompt="Test system prompt",
            tools=[{"name": "tool1", "description": "t1", "input_schema": {}}],
        )
        agent = ConcreteSubAgent(config)

        mock_text_block = MagicMock()
        mock_text_block.text = "Done"
        mock_text_block.type = "text"

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_of_turn"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.usage.cache_creation_input_tokens = 80
        mock_response.usage.cache_read_input_tokens = 0

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        set_context(AgentContext(progress_callback=MagicMock(), token_callback=MagicMock()))
        try:
            with patch("rossum_agent.tools.subagents.base.create_bedrock_client", return_value=mock_client):
                agent.run("Test message")

                call_kwargs = mock_client.messages.create.call_args[1]

                # System should be a list with cache_control
                assert isinstance(call_kwargs["system"], list)
                assert call_kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}

                # Last tool should have cache_control
                tools = call_kwargs["tools"]
                assert tools[-1]["cache_control"] == {"type": "ephemeral"}
        finally:
            set_context(AgentContext())

    def test_run_reports_cache_tokens(self):
        """Test that cache token metrics are reported via callback."""
        config = SubAgentConfig(
            tool_name="test",
            system_prompt="prompt",
            tools=[],
        )
        agent = ConcreteSubAgent(config)

        token_reports = []

        mock_response = MagicMock()
        mock_response.content = []
        mock_response.stop_reason = "end_of_turn"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.usage.cache_creation_input_tokens = 30
        mock_response.usage.cache_read_input_tokens = 60

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        set_context(
            AgentContext(
                progress_callback=MagicMock(),
                token_callback=lambda usage: token_reports.append(usage),
            )
        )
        try:
            with patch("rossum_agent.tools.subagents.base.create_bedrock_client", return_value=mock_client):
                agent.run("Test")

                assert len(token_reports) == 1
                assert token_reports[0].cache_creation_input_tokens == 30
                assert token_reports[0].cache_read_input_tokens == 60
        finally:
            set_context(AgentContext())

    # Unit tests for add_message_cache_breakpoint are in tests/agent/test_core.py::TestCacheBreakpoints
