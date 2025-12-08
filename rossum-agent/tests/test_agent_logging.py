"""Tests for rossum_agent.agent_logging module."""

from __future__ import annotations

from unittest.mock import patch

from rossum_agent.agent import AgentStep, ToolCall, ToolResult
from rossum_agent.agent_logging import log_agent_result


class TestLogAgentResult:
    """Test log_agent_result function."""

    @patch("rossum_agent.agent_logging.logger")
    def test_logs_final_answer_step(self, mock_logger):
        """Test logging of final answer step."""
        step = AgentStep(
            step_number=1,
            thinking="Processing the request",
            final_answer="Final answer content",
            is_final=True,
        )

        log_agent_result(step, prompt="Test prompt", duration=1.5)

        assert mock_logger.info.called
        call_args = mock_logger.info.call_args

        assert call_args[0][0] == "Agent step completed"

        extra = call_args.kwargs["extra"]
        assert extra["event_type"] == "agent_call_complete"
        assert extra["prompt"] == "Test prompt"
        assert extra["duration_seconds"] == 1.5
        assert extra["is_final"] is True
        assert extra["final_answer"] == "Final answer content"

    @patch("rossum_agent.agent_logging.logger")
    def test_logs_step_with_tool_calls(self, mock_logger):
        """Test logging of step with tool calls."""
        tool_call = ToolCall(id="tc_1", name="list_queues", arguments={"workspace_url": "https://example.com"})
        step = AgentStep(
            step_number=1,
            thinking="Let me check the queues",
            tool_calls=[tool_call],
            is_final=False,
        )

        log_agent_result(step, prompt="Test prompt", duration=2.0)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert extra["step_number"] == 1
        assert extra["is_final"] is False
        assert "tool_calls" in extra
        assert "list_queues" in extra["tool_calls"]

    @patch("rossum_agent.agent_logging.logger")
    def test_logs_step_with_tool_results(self, mock_logger):
        """Test logging of step with tool results."""
        tool_result = ToolResult(tool_call_id="tc_1", name="list_queues", content='{"queues": []}', is_error=False)
        step = AgentStep(
            step_number=1,
            tool_results=[tool_result],
            is_final=False,
        )

        log_agent_result(step, prompt="Test prompt", duration=1.0)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert "tool_results" in extra
        assert "list_queues" in extra["tool_results"]

    @patch("rossum_agent.agent_logging.logger")
    def test_logs_step_with_error(self, mock_logger):
        """Test logging of step with error."""
        step = AgentStep(
            step_number=3,
            error="Something went wrong",
            is_final=True,
        )

        log_agent_result(step, prompt="Error prompt", duration=0.5)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert extra["error"] == "Something went wrong"
        assert extra["is_final"] is True

    @patch("rossum_agent.agent_logging.logger")
    def test_logs_step_with_minimal_data(self, mock_logger):
        """Test that steps with minimal data are handled correctly."""
        step = AgentStep(step_number=4, is_final=False)

        log_agent_result(step, prompt="Sparse prompt", duration=1.0)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert extra["step_number"] == 4
        assert extra["is_final"] is False
        assert "thinking" not in extra
        assert "tool_calls" not in extra
        assert "tool_results" not in extra
        assert "final_answer" not in extra
        assert "error" not in extra

    @patch("rossum_agent.agent_logging.logger")
    def test_default_parameters(self, mock_logger):
        """Test that default parameters work correctly."""
        step = AgentStep(step_number=1, final_answer="Output", is_final=True)

        log_agent_result(step)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert extra["prompt"] == ""
        assert extra["duration_seconds"] == 0

    @patch("rossum_agent.agent_logging.logger")
    def test_multiple_consecutive_logs(self, mock_logger):
        """Test that multiple consecutive logs work correctly."""
        steps = [
            AgentStep(step_number=1, thinking="Step 1", is_final=False),
            AgentStep(step_number=2, thinking="Step 2", is_final=False),
            AgentStep(step_number=3, final_answer="Final", is_final=True),
        ]

        for i, step in enumerate(steps):
            log_agent_result(step, prompt=f"Prompt {i}", duration=float(i))

        assert mock_logger.info.call_count == 3

    @patch("rossum_agent.agent_logging.logger")
    def test_large_prompt_logged_completely(self, mock_logger):
        """Test that large prompts are logged completely (not truncated)."""
        large_prompt = "x" * 10000
        step = AgentStep(step_number=1, final_answer="Output", is_final=True)

        log_agent_result(step, prompt=large_prompt, duration=1.0)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert len(extra["prompt"]) == 10000
        assert extra["prompt"] == large_prompt

    @patch("rossum_agent.agent_logging.logger")
    def test_unicode_content_logged_correctly(self, mock_logger):
        """Test that unicode content is logged correctly."""
        unicode_answer = "Testing unicode: 你好世界 🌍 🚀"
        step = AgentStep(step_number=1, final_answer=unicode_answer, is_final=True)

        log_agent_result(step, prompt="Unicode test", duration=1.0)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert extra["final_answer"] == unicode_answer

    @patch("rossum_agent.agent_logging.logger")
    def test_empty_answer_logged(self, mock_logger):
        """Test that empty answer is logged correctly."""
        step = AgentStep(step_number=1, final_answer="", is_final=True)

        log_agent_result(step, prompt="", duration=0.0)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert "final_answer" not in extra  # Empty strings are falsy, so not logged
        assert extra["prompt"] == ""
        assert extra["duration_seconds"] == 0.0

    @patch("rossum_agent.agent_logging.logger")
    def test_thinking_truncated_if_too_long(self, mock_logger):
        """Test that very long thinking is truncated to 500 chars."""
        long_thinking = "x" * 1000
        step = AgentStep(step_number=1, thinking=long_thinking, is_final=False)

        log_agent_result(step, prompt="Test", duration=1.0)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert len(extra["thinking"]) == 500

    @patch("rossum_agent.agent_logging.logger")
    def test_final_answer_truncated_if_too_long(self, mock_logger):
        """Test that very long final answer is truncated to 500 chars."""
        long_answer = "x" * 1000
        step = AgentStep(step_number=1, final_answer=long_answer, is_final=True)

        log_agent_result(step, prompt="Test", duration=1.0)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert len(extra["final_answer"]) == 500
