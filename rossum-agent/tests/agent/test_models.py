"""Tests for rossum_agent.agent.models module."""

from __future__ import annotations

import pytest
from rossum_agent.agent.models import (
    AgentConfig,
    AgentStep,
    StepType,
    StreamDelta,
    ThinkingBlockData,
    ToolCall,
    ToolResult,
    truncate_content,
)


class TestTruncateContent:
    """Test truncate_content function."""

    def test_returns_content_unchanged_when_under_limit(self):
        content = "Short content"
        result = truncate_content(content, max_length=100)
        assert result == content

    def test_returns_content_unchanged_when_equal_to_limit(self):
        content = "A" * 100
        result = truncate_content(content, max_length=100)
        assert result == content

    def test_truncates_content_when_over_limit(self):
        content = "A" * 1000
        result = truncate_content(content, max_length=100)
        assert "truncated" in result.lower()
        assert result.startswith("A" * 50)
        assert result.endswith("A" * 50)

    def test_uses_default_max_length(self):
        content = "A" * 10
        result = truncate_content(content)
        assert result == content

    def test_truncation_message_includes_max_length(self):
        content = "B" * 500
        result = truncate_content(content, max_length=200)
        assert "200" in result


class TestToolCallSerialization:
    """Test ToolCall serialization methods."""

    def test_to_dict(self):
        tool_call = ToolCall(id="tc1", name="get_data", arguments={"key": "value", "count": 5})
        result = tool_call.to_dict()
        assert result == {"id": "tc1", "name": "get_data", "arguments": {"key": "value", "count": 5}}

    def test_from_dict(self):
        data = {"id": "tc2", "name": "list_items", "arguments": {"filter": "active"}}
        tool_call = ToolCall.from_dict(data)
        assert tool_call.id == "tc2"
        assert tool_call.name == "list_items"
        assert tool_call.arguments == {"filter": "active"}

    def test_from_dict_with_missing_arguments(self):
        data = {"id": "tc3", "name": "simple_tool"}
        tool_call = ToolCall.from_dict(data)
        assert tool_call.arguments == {}

    def test_roundtrip(self):
        original = ToolCall(id="tc1", name="complex_tool", arguments={"nested": {"a": 1}, "list": [1, 2, 3]})
        restored = ToolCall.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.arguments == original.arguments

    def test_empty_arguments(self):
        tool_call = ToolCall(id="tc1", name="no_args", arguments={})
        result = tool_call.to_dict()
        assert result["arguments"] == {}


class TestToolResultSerialization:
    """Test ToolResult serialization methods."""

    def test_to_dict(self):
        tool_result = ToolResult(tool_call_id="tc1", name="get_data", content='{"data": [1, 2, 3]}', is_error=False)
        result = tool_result.to_dict()
        assert result == {
            "tool_call_id": "tc1",
            "name": "get_data",
            "content": '{"data": [1, 2, 3]}',
            "is_error": False,
        }

    def test_to_dict_with_error(self):
        tool_result = ToolResult(tool_call_id="tc2", name="failing_tool", content="Error: not found", is_error=True)
        result = tool_result.to_dict()
        assert result["is_error"] is True
        assert result["content"] == "Error: not found"

    def test_from_dict(self):
        data = {"tool_call_id": "tc1", "name": "test_tool", "content": "success", "is_error": False}
        tool_result = ToolResult.from_dict(data)
        assert tool_result.tool_call_id == "tc1"
        assert tool_result.name == "test_tool"
        assert tool_result.content == "success"
        assert tool_result.is_error is False

    def test_from_dict_with_defaults(self):
        data = {"tool_call_id": "tc1", "name": "test_tool"}
        tool_result = ToolResult.from_dict(data)
        assert tool_result.content == ""
        assert tool_result.is_error is False

    def test_roundtrip(self):
        original = ToolResult(tool_call_id="tc1", name="tool", content="result", is_error=True)
        restored = ToolResult.from_dict(original.to_dict())
        assert restored.tool_call_id == original.tool_call_id
        assert restored.name == original.name
        assert restored.content == original.content
        assert restored.is_error == original.is_error

    def test_default_is_error_is_false(self):
        tool_result = ToolResult(tool_call_id="tc1", name="tool", content="ok")
        assert tool_result.is_error is False


class TestAgentConfig:
    """Test AgentConfig dataclass."""

    def test_default_values(self):
        config = AgentConfig()
        assert config.max_output_tokens == 64000
        assert config.max_steps == 50
        assert config.temperature == 1.0  # Required for extended thinking

    def test_request_delay_default(self):
        config = AgentConfig()
        assert config.request_delay == 3.0

    def test_custom_values(self):
        config = AgentConfig(max_output_tokens=4096, max_steps=10, request_delay=1.0)
        assert config.max_output_tokens == 4096
        assert config.max_steps == 10
        assert config.temperature == 1.0  # Must be 1.0 for extended thinking
        assert config.request_delay == 1.0


class TestAgentStep:
    """Test AgentStep dataclass."""

    def test_has_tool_calls_returns_true_when_present(self):
        step = AgentStep(step_number=1, tool_calls=[ToolCall(id="1", name="test_tool", arguments={})])
        assert step.has_tool_calls() is True

    def test_has_tool_calls_returns_false_when_empty(self):
        step = AgentStep(step_number=1)
        assert step.has_tool_calls() is False

    def test_default_values(self):
        step = AgentStep(step_number=1)
        assert step.thinking is None
        assert step.tool_calls == []
        assert step.tool_results == []
        assert step.final_answer is None
        assert step.is_final is False
        assert step.error is None
        assert step.is_streaming is False
        assert step.input_tokens == 0
        assert step.output_tokens == 0
        assert step.current_tool is None
        assert step.tool_progress is None
        assert step.sub_agent_progress is None

    def test_with_final_answer(self):
        step = AgentStep(step_number=5, final_answer="The answer is 42", is_final=True)
        assert step.final_answer == "The answer is 42"
        assert step.is_final is True

    def test_with_error(self):
        step = AgentStep(step_number=3, error="Something went wrong", is_final=True)
        assert step.error == "Something went wrong"
        assert step.is_final is True

    def test_with_token_counts(self):
        step = AgentStep(step_number=1, input_tokens=100, output_tokens=50)
        assert step.input_tokens == 100
        assert step.output_tokens == 50

    def test_with_tool_progress(self):
        step = AgentStep(step_number=1, current_tool="search", tool_progress=(2, 5))
        assert step.current_tool == "search"
        assert step.tool_progress == (2, 5)

    def test_with_step_type(self):
        step = AgentStep(step_number=1, step_type=StepType.THINKING)
        assert step.step_type == StepType.THINKING

    def test_with_text_delta_and_accumulated(self):
        step = AgentStep(step_number=1, text_delta="new text", accumulated_text="all text so far")
        assert step.text_delta == "new text"
        assert step.accumulated_text == "all text so far"


class TestStepType:
    """Test StepType enum."""

    def test_thinking_value(self):
        assert StepType.THINKING.value == "thinking"

    def test_intermediate_value(self):
        assert StepType.INTERMEDIATE.value == "intermediate"

    def test_final_answer_value(self):
        assert StepType.FINAL_ANSWER.value == "final_answer"


class TestStreamDelta:
    """Test StreamDelta dataclass."""

    def test_thinking_delta(self):
        delta = StreamDelta(kind="thinking", content="Let me analyze...")
        assert delta.kind == "thinking"
        assert delta.content == "Let me analyze..."

    def test_text_delta(self):
        delta = StreamDelta(kind="text", content="Here is my answer")
        assert delta.kind == "text"
        assert delta.content == "Here is my answer"


class TestThinkingBlockData:
    """Test ThinkingBlockData dataclass."""

    def test_creation(self):
        block = ThinkingBlockData(thinking="I need to analyze this", signature="sig123")
        assert block.thinking == "I need to analyze this"
        assert block.signature == "sig123"

    def test_to_dict(self):
        block = ThinkingBlockData(thinking="analysis", signature="abc")
        result = block.to_dict()
        assert result == {"type": "thinking", "thinking": "analysis", "signature": "abc"}

    def test_from_dict(self):
        data = {"thinking": "my thoughts", "signature": "xyz"}
        block = ThinkingBlockData.from_dict(data)
        assert block.thinking == "my thoughts"
        assert block.signature == "xyz"

    def test_roundtrip(self):
        original = ThinkingBlockData(thinking="deep thoughts", signature="sig456")
        serialized = original.to_dict()
        restored = ThinkingBlockData.from_dict(serialized)
        assert restored.thinking == original.thinking
        assert restored.signature == original.signature


class TestAgentConfigValidation:
    """Test AgentConfig validation."""

    def test_temperature_must_be_one(self):
        with pytest.raises(ValueError, match=r"temperature must be 1\.0"):
            AgentConfig(temperature=0.5)

    def test_default_thinking_budget(self):
        config = AgentConfig()
        assert config.thinking_budget_tokens == 10000

    def test_thinking_budget_must_be_at_least_1024(self):
        with pytest.raises(ValueError, match=r"thinking_budget_tokens must be at least 1024"):
            AgentConfig(thinking_budget_tokens=1000)
