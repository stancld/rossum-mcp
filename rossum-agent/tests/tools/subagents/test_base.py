"""Tests for rossum_agent.tools.subagents.base module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from rossum_agent.tools.subagents.base import (
    SubAgent,
    SubAgentConfig,
    SubAgentResult,
    save_iteration_context,
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


class TestSaveIterationContext:
    """Test save_iteration_context function."""

    def test_saves_context_file(self, tmp_path):
        """Test that context file is saved with expected structure."""
        messages = [{"role": "user", "content": "test"}]
        tools = [{"name": "tool1"}]

        with patch("rossum_agent.tools.subagents.base.get_output_dir", return_value=tmp_path):
            save_iteration_context(
                tool_name="test_tool",
                iteration=1,
                max_iterations=5,
                messages=messages,
                system_prompt="Test prompt",
                tools=tools,
                max_tokens=4096,
            )

        context_file = tmp_path / "test_tool_context_iter_1.json"
        assert context_file.exists()

        context_data = json.loads(context_file.read_text())
        assert context_data["iteration"] == 1
        assert context_data["max_iterations"] == 5
        assert context_data["messages"] == messages
        assert context_data["system_prompt"] == "Test prompt"
        assert context_data["tools"] == tools
        assert context_data["max_tokens"] == 4096

    def test_logs_warning_on_failure(self):
        """Test that warning is logged when save fails."""
        with (
            patch(
                "rossum_agent.tools.subagents.base.get_output_dir",
                side_effect=Exception("Test error"),
            ),
            patch("rossum_agent.tools.subagents.base.logger") as mock_logger,
        ):
            save_iteration_context(
                tool_name="test",
                iteration=1,
                max_iterations=5,
                messages=[],
                system_prompt="",
                tools=[],
                max_tokens=4096,
            )

            mock_logger.warning.assert_called_once()
            assert "Failed to save test context" in mock_logger.warning.call_args[0][0]


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

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with (
            patch(
                "rossum_agent.tools.subagents.base.create_bedrock_client",
                return_value=mock_client,
            ),
            patch("rossum_agent.tools.subagents.base.report_progress"),
            patch("rossum_agent.tools.subagents.base.report_token_usage"),
            patch("rossum_agent.tools.subagents.base.save_iteration_context"),
        ):
            result = agent.run("Test message")

            assert result.analysis == "Analysis result"
            assert result.input_tokens == 100
            assert result.output_tokens == 50
            assert result.iterations_used == 1

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

        with (
            patch(
                "rossum_agent.tools.subagents.base.create_bedrock_client",
                return_value=mock_client,
            ),
            patch("rossum_agent.tools.subagents.base.report_progress"),
            patch("rossum_agent.tools.subagents.base.report_token_usage"),
            patch("rossum_agent.tools.subagents.base.save_iteration_context"),
        ):
            result = agent.run("Test message")

            assert result.analysis == "Final result"
            assert result.input_tokens == 250
            assert result.output_tokens == 125
            assert result.iterations_used == 2
            assert mock_client.messages.create.call_count == 2

    def test_run_reports_token_usage(self):
        """Test that token usage is reported via callback."""
        config = SubAgentConfig(
            tool_name="test",
            system_prompt="prompt",
            tools=[],
        )
        agent = ConcreteSubAgent(config)

        token_reports = []

        def capture_tokens(usage):
            token_reports.append(usage)

        mock_response = MagicMock()
        mock_response.content = []
        mock_response.stop_reason = "end_of_turn"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with (
            patch(
                "rossum_agent.tools.subagents.base.create_bedrock_client",
                return_value=mock_client,
            ),
            patch("rossum_agent.tools.subagents.base.report_progress"),
            patch(
                "rossum_agent.tools.subagents.base.report_token_usage",
                side_effect=capture_tokens,
            ),
            patch("rossum_agent.tools.subagents.base.save_iteration_context"),
        ):
            agent.run("Test")

            assert len(token_reports) == 1
            assert token_reports[0].tool_name == "test"
            assert token_reports[0].input_tokens == 100
            assert token_reports[0].output_tokens == 50
            assert token_reports[0].iteration == 1

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

        with (
            patch(
                "rossum_agent.tools.subagents.base.create_bedrock_client",
                return_value=mock_client,
            ),
            patch("rossum_agent.tools.subagents.base.report_progress"),
            patch("rossum_agent.tools.subagents.base.report_token_usage"),
            patch("rossum_agent.tools.subagents.base.save_iteration_context"),
        ):
            result = agent.run("Test")

            assert result.analysis == "Handled error"

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

    def test_run_max_iterations_reached(self):
        """Test behavior when max iterations is reached."""
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

        mock_response = MagicMock()
        mock_response.content = [mock_tool_block]
        mock_response.stop_reason = "tool_use"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with (
            patch(
                "rossum_agent.tools.subagents.base.create_bedrock_client",
                return_value=mock_client,
            ),
            patch("rossum_agent.tools.subagents.base.report_progress"),
            patch("rossum_agent.tools.subagents.base.report_token_usage"),
            patch("rossum_agent.tools.subagents.base.save_iteration_context"),
            patch("rossum_agent.tools.subagents.base.logger") as mock_logger,
        ):
            result = agent.run("Test")

            assert result.iterations_used == 2
            assert result.input_tokens == 200
            assert result.output_tokens == 100
            mock_logger.warning.assert_called()
            assert "max iterations" in mock_logger.warning.call_args[0][0]

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
