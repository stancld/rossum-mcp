"""Tests for rossum_agent.agent_logging module."""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

from rossum_agent.agent_logging import log_agent_result
from smolagents.memory import ActionStep, FinalAnswerStep


def create_mock_final_answer(output: str) -> Mock:
    """Create a mock FinalAnswerStep."""
    result = Mock(spec=FinalAnswerStep)
    result.output = output
    return result


def create_mock_action_step(**kwargs) -> Mock:
    """Create a mock ActionStep with default values."""
    result = Mock(spec=ActionStep)
    result.step_number = kwargs.get("step_number", 1)
    result.model_output = kwargs.get("model_output")
    result.action_output = kwargs.get("action_output")
    result.observations = kwargs.get("observations")
    result.tool_calls = kwargs.get("tool_calls")
    result.error = kwargs.get("error")
    result.token_usage = kwargs.get("token_usage")
    result.timing = kwargs.get("timing")
    result.is_final_answer = kwargs.get("is_final_answer", False)
    return result


class TestLogAgentResult:
    """Test log_agent_result function."""

    @patch("rossum_agent.agent_logging.logger")
    def test_logs_final_answer_step(self, mock_logger):
        """Test logging of FinalAnswerStep."""
        result = create_mock_final_answer(output="Final answer content")

        log_agent_result(result, prompt="Test prompt", duration=1.5)

        assert mock_logger.info.called
        call_args = mock_logger.info.call_args

        assert call_args[0][0] == "Agent call completed"

        extra = call_args.kwargs["extra"]
        assert extra["event_type"] == "agent_call_complete"
        assert extra["prompt"] == "Test prompt"
        assert extra["duration_seconds"] == 1.5
        assert extra["output"] == "Final answer content"

    @patch("rossum_agent.agent_logging.logger")
    def test_logs_action_step_basic(self, mock_logger):
        """Test logging of basic ActionStep."""
        result = create_mock_action_step(step_number=1, model_output="Model output", is_final_answer=False)

        log_agent_result(result, prompt="Test prompt", duration=2.0)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert extra["step_number"] == 1
        assert extra["model_output"] == "Model output"
        assert extra["is_final_answer"] is False

    @patch("rossum_agent.agent_logging.logger")
    def test_logs_action_step_with_all_fields(self, mock_logger):
        """Test logging of ActionStep with all fields populated."""

        # Use simple objects instead of Mock for __dict__ access
        class TokenUsage:
            def __init__(self):
                self.input_tokens = 100
                self.output_tokens = 50

        class Timing:
            def __init__(self):
                self.start = 1000
                self.end = 2000
                self.duration = 1.0

        token_usage_mock = TokenUsage()
        timing_mock = Timing()
        tool_calls = [{"tool": "search", "args": {"query": "test"}}]

        result = create_mock_action_step(
            step_number=2,
            model_output="Model output",
            action_output="Action output",
            observations="Some observations",
            tool_calls=tool_calls,
            token_usage=token_usage_mock,
            timing=timing_mock,
            is_final_answer=True,
        )

        log_agent_result(result, prompt="Complex prompt", duration=3.5)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert extra["step_number"] == 2
        assert extra["model_output"] == "Model output"
        assert extra["action_output"] == "Action output"
        assert extra["observations"] == "Some observations"
        assert extra["tool_calls"] == json.dumps(tool_calls, default=str)
        assert extra["error"] is None
        assert extra["token_usage"] == {"input_tokens": 100, "output_tokens": 50}
        assert extra["timing"] == {"start": 1000, "end": 2000, "duration": 1.0}
        assert extra["is_final_answer"] is True

    @patch("rossum_agent.agent_logging.logger")
    def test_logs_action_step_with_error(self, mock_logger):
        """Test logging of ActionStep with error."""
        result = create_mock_action_step(step_number=3, error="Something went wrong", is_final_answer=False)

        log_agent_result(result, prompt="Error prompt", duration=0.5)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert extra["error"] == "Something went wrong"

    @patch("rossum_agent.agent_logging.logger")
    def test_logs_action_step_with_none_values(self, mock_logger):
        """Test that None values are handled correctly."""
        result = create_mock_action_step(step_number=4)

        log_agent_result(result, prompt="Sparse prompt", duration=1.0)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert extra["model_output"] is None
        assert extra["action_output"] is None
        assert extra["observations"] is None
        assert extra["tool_calls"] is None
        assert extra["error"] is None
        assert extra["token_usage"] is None
        assert extra["timing"] is None

    @patch("rossum_agent.agent_logging.logger")
    def test_logs_unknown_result_type(self, mock_logger):
        """Test logging of unknown result type."""
        result = "Some string result" * 100  # Long string

        log_agent_result(result, prompt="Unknown type", duration=0.1)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert len(extra["response"]) == 500
        assert extra["response"] == ("Some string result" * 100)[:500]

    @patch("rossum_agent.agent_logging.logger")
    def test_default_parameters(self, mock_logger):
        """Test that default parameters work correctly."""
        result = create_mock_final_answer(output="Output")

        log_agent_result(result)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert extra["prompt"] == ""
        assert extra["duration_seconds"] == 0

    @patch("rossum_agent.agent_logging.logger")
    def test_tool_calls_serialization_with_complex_objects(self, mock_logger):
        """Test that complex objects in tool_calls are serialized correctly."""

        class CustomObject:
            def __str__(self):
                return "custom_object_str"

        tool_calls = [{"tool": "complex", "args": {"obj": CustomObject()}}]

        result = create_mock_action_step(step_number=5, tool_calls=tool_calls, is_final_answer=False)

        log_agent_result(result, prompt="Complex objects", duration=1.0)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        tool_calls_json = extra["tool_calls"]
        assert isinstance(tool_calls_json, str)
        parsed = json.loads(tool_calls_json)
        assert "custom_object_str" in str(parsed)

    @patch("rossum_agent.agent_logging.logger")
    def test_multiple_consecutive_logs(self, mock_logger):
        """Test that multiple consecutive logs work correctly."""
        results = [
            create_mock_action_step(step_number=1, model_output="Step 1"),
            create_mock_action_step(step_number=2, model_output="Step 2"),
            create_mock_final_answer(output="Final"),
        ]

        for i, result in enumerate(results):
            log_agent_result(result, prompt=f"Prompt {i}", duration=float(i))

        assert mock_logger.info.call_count == 3

    @patch("rossum_agent.agent_logging.logger")
    def test_large_prompt_logged_completely(self, mock_logger):
        """Test that large prompts are logged completely (not truncated)."""
        large_prompt = "x" * 10000
        result = create_mock_final_answer(output="Output")

        log_agent_result(result, prompt=large_prompt, duration=1.0)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert len(extra["prompt"]) == 10000
        assert extra["prompt"] == large_prompt

    @patch("rossum_agent.agent_logging.logger")
    def test_unicode_content_logged_correctly(self, mock_logger):
        """Test that unicode content is logged correctly."""
        unicode_output = "Testing unicode: 你好世界 🌍 🚀"
        result = create_mock_final_answer(output=unicode_output)

        log_agent_result(result, prompt="Unicode test", duration=1.0)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert extra["output"] == unicode_output

    @patch("rossum_agent.agent_logging.logger")
    def test_empty_output_logged(self, mock_logger):
        """Test that empty output is logged correctly."""
        result = create_mock_final_answer(output="")

        log_agent_result(result, prompt="", duration=0.0)

        call_args = mock_logger.info.call_args
        extra = call_args.kwargs["extra"]

        assert extra["output"] == ""
        assert extra["prompt"] == ""
        assert extra["duration_seconds"] == 0.0
