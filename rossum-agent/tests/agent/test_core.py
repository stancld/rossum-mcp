"""Tests for rossum_agent.agent module."""

from __future__ import annotations

import asyncio
import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anthropic import APIError, APITimeoutError, RateLimitError
from anthropic.types import (
    ContentBlockStopEvent,
    InputJSONDelta,
    Message,
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    TextDelta,
    ToolUseBlock,
    Usage,
)
from rossum_agent.agent import (
    AgentConfig,
    AgentMemory,
    AgentStep,
    MemoryStep,
    RossumAgent,
    TaskStep,
    ToolCall,
    ToolResult,
    truncate_content,
)
from rossum_agent.agent.core import _parse_json_encoded_strings, _StreamState
from rossum_agent.agent.models import StepType


class TestParseJsonEncodedStrings:
    """Test _parse_json_encoded_strings function for handling LLM double-encoded arguments."""

    def test_parses_json_encoded_list(self):
        """Test that JSON-encoded list strings are parsed to actual lists."""
        arguments = {"fields_to_keep": '["field_a", "field_b", "field_c"]'}
        result = _parse_json_encoded_strings(arguments)
        assert result == {"fields_to_keep": ["field_a", "field_b", "field_c"]}

    def test_parses_json_encoded_dict(self):
        """Test that JSON-encoded dict strings are parsed to actual dicts."""
        arguments = {"config": '{"key": "value", "count": 5}'}
        result = _parse_json_encoded_strings(arguments)
        assert result == {"config": {"key": "value", "count": 5}}

    def test_preserves_non_json_strings(self):
        """Test that regular strings are preserved unchanged."""
        arguments = {"name": "test_value", "path": "/some/path"}
        result = _parse_json_encoded_strings(arguments)
        assert result == {"name": "test_value", "path": "/some/path"}

    def test_preserves_actual_lists_and_dicts(self):
        """Test that actual lists and dicts are preserved unchanged."""
        arguments = {"items": ["a", "b"], "config": {"x": 1}}
        result = _parse_json_encoded_strings(arguments)
        assert result == {"items": ["a", "b"], "config": {"x": 1}}

    def test_handles_mixed_arguments(self):
        """Test handling mix of JSON-encoded and normal arguments."""
        arguments = {"schema_id": 123, "fields_to_keep": '["document_id", "date_issue"]', "name": "test"}
        result = _parse_json_encoded_strings(arguments)
        assert result == {"schema_id": 123, "fields_to_keep": ["document_id", "date_issue"], "name": "test"}

    def test_handles_invalid_json_gracefully(self):
        """Test that invalid JSON strings are preserved unchanged."""
        arguments = {"value": "[invalid json"}
        result = _parse_json_encoded_strings(arguments)
        assert result == {"value": "[invalid json"}

    def test_handles_nested_dicts(self):
        """Test that nested dicts are processed recursively."""
        arguments = {"outer": {"inner_list": '["a", "b"]'}}
        result = _parse_json_encoded_strings(arguments)
        assert result == {"outer": {"inner_list": ["a", "b"]}}

    def test_preserves_json_primitive_strings(self):
        """Test that JSON strings encoding primitives are preserved."""
        arguments = {"value": '"just a string"', "number": "42"}
        result = _parse_json_encoded_strings(arguments)
        # Only list/dict JSON should be parsed, primitives preserved
        assert result["number"] == "42"
        assert result["value"] == '"just a string"'

    def test_preserves_changes_parameter_as_string(self):
        """Test that 'changes' parameter is not parsed even if it's valid JSON.

        The 'changes' parameter should remain as a JSON string because some tools
        expect it in that format (e.g., patch_schema).
        """
        arguments = {"changes": '[{"op": "add", "path": "/fields/-", "value": {"name": "new_field"}}]'}
        result = _parse_json_encoded_strings(arguments)
        # changes should stay as a string, not be parsed to a list
        assert isinstance(result["changes"], str)
        assert result["changes"] == arguments["changes"]

    def test_parses_non_changes_json_lists(self):
        """Test that other JSON lists are parsed but 'changes' is preserved."""
        arguments = {
            "changes": '["item1", "item2"]',
            "fields_to_keep": '["field_a", "field_b"]',
        }
        result = _parse_json_encoded_strings(arguments)
        # changes stays as string
        assert isinstance(result["changes"], str)
        # fields_to_keep is parsed
        assert result["fields_to_keep"] == ["field_a", "field_b"]


class TestTruncateContent:
    """Test truncate_content function."""

    def test_returns_content_unchanged_when_under_limit(self):
        """Test that content under the limit is returned unchanged."""
        content = "Short content"
        result = truncate_content(content, max_length=100)
        assert result == content

    def test_truncates_content_when_over_limit(self):
        """Test that content over the limit is truncated with head and tail."""
        content = "A" * 1000
        result = truncate_content(content, max_length=100)
        assert "truncated" in result.lower()
        assert result.startswith("A" * 50)
        assert result.endswith("A" * 50)

    def test_uses_default_max_length(self):
        """Test that default max_length is used when not specified."""
        content = "A" * 10
        result = truncate_content(content)
        assert result == content


class TestAgentConfig:
    """Test AgentConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = AgentConfig()
        assert config.max_output_tokens == 64000
        assert config.max_steps == 50
        assert config.temperature == 1.0  # Required for extended thinking

    def test_custom_values(self):
        """Test custom configuration values."""
        config = AgentConfig(
            max_output_tokens=4096,
            max_steps=10,
        )
        assert config.max_output_tokens == 4096
        assert config.max_steps == 10
        assert config.temperature == 1.0  # Must be 1.0 for extended thinking


class TestAgentStep:
    """Test AgentStep dataclass."""

    def test_has_tool_calls_returns_true_when_present(self):
        """Test has_tool_calls returns True when tool_calls is non-empty."""
        step = AgentStep(
            step_number=1,
            tool_calls=[ToolCall(id="1", name="test_tool", arguments={})],
        )
        assert step.has_tool_calls() is True

    def test_has_tool_calls_returns_false_when_empty(self):
        """Test has_tool_calls returns False when tool_calls is empty."""
        step = AgentStep(step_number=1)
        assert step.has_tool_calls() is False


class TestMemoryStep:
    """Test MemoryStep to_messages conversion."""

    def test_to_messages_with_tool_calls(self):
        """Test that tool calls are converted to messages (text IS included before tool_use)."""
        step = MemoryStep(
            step_number=1,
            text="Let me analyze this...",
            tool_calls=[ToolCall(id="tc1", name="get_data", arguments={"key": "value"})],
            tool_results=[ToolResult(tool_call_id="tc1", name="get_data", content="result data")],
        )

        messages = step.to_messages()

        assert len(messages) == 2
        assert messages[0]["role"] == "assistant"
        # Text is included as first block, then tool_use
        assert len(messages[0]["content"]) == 2
        assert messages[0]["content"][0]["type"] == "text"
        assert messages[0]["content"][0]["text"] == "Let me analyze this..."
        assert messages[0]["content"][1]["type"] == "tool_use"

        assert messages[1]["role"] == "user"
        assert messages[1]["content"][0]["type"] == "tool_result"

    def test_to_messages_with_tool_calls_no_text(self):
        """Test that tool calls without text only include tool_use blocks."""
        step = MemoryStep(
            step_number=1,
            tool_calls=[ToolCall(id="tc1", name="get_data", arguments={"key": "value"})],
            tool_results=[ToolResult(tool_call_id="tc1", name="get_data", content="result data")],
        )

        messages = step.to_messages()

        assert len(messages) == 2
        assert messages[0]["role"] == "assistant"
        # No text, so only tool_use block
        assert len(messages[0]["content"]) == 1
        assert messages[0]["content"][0]["type"] == "tool_use"

        assert messages[1]["role"] == "user"
        assert messages[1]["content"][0]["type"] == "tool_result"

    def test_to_messages_no_text_returns_empty(self):
        """Test that step without tool calls and no text returns empty messages."""
        step = MemoryStep(step_number=1)

        messages = step.to_messages()

        assert messages == []

    def test_to_messages_with_text(self):
        """Test that final answer steps include text as assistant content."""
        step = MemoryStep(step_number=1, text="Here is the final answer.")

        messages = step.to_messages()

        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert messages[0]["content"] == "Here is the final answer."


class TestMemoryStepSerialization:
    """Test MemoryStep serialization methods."""

    def test_to_dict_simple(self):
        """Test serializing simple MemoryStep."""
        step = MemoryStep(step_number=1, text="Final answer here")
        result = step.to_dict()

        assert result["type"] == "memory_step"
        assert result["step_number"] == 1
        assert result["text"] == "Final answer here"
        assert result["tool_calls"] == []
        assert result["tool_results"] == []

    def test_to_dict_with_tools(self):
        """Test serializing MemoryStep with tool calls and results."""
        step = MemoryStep(
            step_number=2,
            text="Let me check...",
            tool_calls=[ToolCall(id="tc1", name="get_data", arguments={"id": 123})],
            tool_results=[ToolResult(tool_call_id="tc1", name="get_data", content="data found")],
            input_tokens=100,
            output_tokens=50,
        )
        result = step.to_dict()

        assert result["type"] == "memory_step"
        assert result["step_number"] == 2
        assert result["text"] == "Let me check..."
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "get_data"
        assert len(result["tool_results"]) == 1
        assert result["tool_results"][0]["content"] == "data found"
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 50

    def test_from_dict(self):
        """Test deserializing MemoryStep from dict."""
        data = {
            "type": "memory_step",
            "step_number": 3,
            "text": "Analysis complete",
            "tool_calls": [{"id": "tc1", "name": "analyze", "arguments": {"depth": 5}}],
            "tool_results": [{"tool_call_id": "tc1", "name": "analyze", "content": "result", "is_error": False}],
            "input_tokens": 200,
            "output_tokens": 100,
        }
        step = MemoryStep.from_dict(data)

        assert step.step_number == 3
        assert step.text == "Analysis complete"
        assert len(step.tool_calls) == 1
        assert step.tool_calls[0].name == "analyze"
        assert len(step.tool_results) == 1
        assert step.tool_results[0].content == "result"
        assert step.input_tokens == 200
        assert step.output_tokens == 100

    def test_from_dict_with_defaults(self):
        """Test deserializing MemoryStep with missing optional fields."""
        data = {"type": "memory_step"}
        step = MemoryStep.from_dict(data)

        assert step.step_number == 0
        assert step.text is None
        assert step.tool_calls == []
        assert step.tool_results == []
        assert step.input_tokens == 0
        assert step.output_tokens == 0

    def test_roundtrip(self):
        """Test serialization roundtrip preserves data."""
        original = MemoryStep(
            step_number=1,
            text="Thinking...",
            tool_calls=[
                ToolCall(id="tc1", name="tool1", arguments={"a": 1}),
                ToolCall(id="tc2", name="tool2", arguments={"b": 2}),
            ],
            tool_results=[
                ToolResult(tool_call_id="tc1", name="tool1", content="result1"),
                ToolResult(tool_call_id="tc2", name="tool2", content="result2", is_error=True),
            ],
            input_tokens=500,
            output_tokens=250,
        )
        restored = MemoryStep.from_dict(original.to_dict())

        assert restored.step_number == original.step_number
        assert restored.text == original.text
        assert len(restored.tool_calls) == len(original.tool_calls)
        assert len(restored.tool_results) == len(original.tool_results)
        assert restored.tool_calls[0].name == original.tool_calls[0].name
        assert restored.tool_results[1].is_error == original.tool_results[1].is_error
        assert restored.input_tokens == original.input_tokens
        assert restored.output_tokens == original.output_tokens


class TestTaskStep:
    """Test TaskStep to_messages conversion."""

    def test_to_messages(self):
        """Test that TaskStep converts to user message."""
        step = TaskStep(task="Help me with this task")

        messages = step.to_messages()

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Help me with this task"


class TestTaskStepSerialization:
    """Test TaskStep serialization methods."""

    def test_to_dict_text(self):
        """Test serializing TaskStep with text content."""
        step = TaskStep(task="Simple text task")
        result = step.to_dict()

        assert result == {"type": "task_step", "task": "Simple text task"}

    def test_to_dict_multimodal(self):
        """Test serializing TaskStep with multimodal content."""
        task_content = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "abc123"}},
            {"type": "text", "text": "Analyze this image"},
        ]
        step = TaskStep(task=task_content)
        result = step.to_dict()

        assert result["type"] == "task_step"
        assert result["task"] == task_content

    def test_from_dict(self):
        """Test deserializing TaskStep from dict."""
        data = {"type": "task_step", "task": "Restore this task"}
        step = TaskStep.from_dict(data)

        assert step.task == "Restore this task"

    def test_from_dict_multimodal(self):
        """Test deserializing TaskStep with multimodal content."""
        task_content = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "xyz789"}},
            {"type": "text", "text": "What is this?"},
        ]
        data = {"type": "task_step", "task": task_content}
        step = TaskStep.from_dict(data)

        assert step.task == task_content

    def test_roundtrip(self):
        """Test serialization roundtrip preserves data."""
        original = TaskStep(task="Complex task with special chars: äöü 日本語")
        restored = TaskStep.from_dict(original.to_dict())

        assert restored.task == original.task


class TestAgentMemory:
    """Test AgentMemory class."""

    def test_reset_clears_steps(self):
        """Test that reset clears all steps."""
        memory = AgentMemory()
        memory.add_task("Task 1")
        memory.add_step(MemoryStep(step_number=1))

        memory.reset()

        assert memory.steps == []

    def test_add_task_and_step(self):
        """Test adding tasks and steps."""
        memory = AgentMemory()
        memory.add_task("Task 1")
        memory.add_step(MemoryStep(step_number=1, text="Thinking..."))

        assert len(memory.steps) == 2
        assert isinstance(memory.steps[0], TaskStep)
        assert isinstance(memory.steps[1], MemoryStep)

    def test_write_to_messages(self):
        """Test that write_to_messages converts all steps."""
        memory = AgentMemory()
        memory.add_task("Task")
        memory.add_step(
            MemoryStep(
                step_number=1,
                text="Thinking",
                tool_calls=[ToolCall(id="tc1", name="tool", arguments={})],
                tool_results=[ToolResult(tool_call_id="tc1", name="tool", content="result")],
            )
        )

        messages = memory.write_to_messages()

        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Task"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"


class TestAgentMemorySerialization:
    """Test AgentMemory serialization methods."""

    def test_to_dict_empty(self):
        """Test serializing empty memory."""
        memory = AgentMemory()
        result = memory.to_dict()

        assert result == []

    def test_to_dict_with_steps(self):
        """Test serializing memory with multiple steps."""
        memory = AgentMemory()
        memory.add_task("Hello, help me")
        memory.add_step(
            MemoryStep(
                step_number=1,
                text="Sure, let me help",
                tool_calls=[ToolCall(id="tc1", name="get_info", arguments={"query": "test"})],
                tool_results=[ToolResult(tool_call_id="tc1", name="get_info", content="info here")],
            )
        )
        memory.add_task("Follow-up question")
        memory.add_step(MemoryStep(step_number=2, text="Here is the answer"))

        result = memory.to_dict()

        assert len(result) == 4
        assert result[0]["type"] == "task_step"
        assert result[0]["task"] == "Hello, help me"
        assert result[1]["type"] == "memory_step"
        assert result[1]["tool_calls"][0]["name"] == "get_info"
        assert result[2]["type"] == "task_step"
        assert result[2]["task"] == "Follow-up question"
        assert result[3]["type"] == "memory_step"
        assert result[3]["text"] == "Here is the answer"

    def test_from_dict_empty(self):
        """Test deserializing empty list."""
        memory = AgentMemory.from_dict([])

        assert memory.steps == []

    def test_from_dict_with_steps(self):
        """Test deserializing memory with multiple steps."""
        data = [
            {"type": "task_step", "task": "First question"},
            {
                "type": "memory_step",
                "step_number": 1,
                "text": "First answer",
                "tool_calls": [],
                "tool_results": [],
            },
            {"type": "task_step", "task": "Second question"},
            {
                "type": "memory_step",
                "step_number": 2,
                "text": "Second answer",
                "tool_calls": [{"id": "tc1", "name": "tool", "arguments": {}}],
                "tool_results": [{"tool_call_id": "tc1", "name": "tool", "content": "result"}],
            },
        ]

        memory = AgentMemory.from_dict(data)

        assert len(memory.steps) == 4
        assert isinstance(memory.steps[0], TaskStep)
        assert memory.steps[0].task == "First question"
        assert isinstance(memory.steps[1], MemoryStep)
        assert memory.steps[1].text == "First answer"
        assert isinstance(memory.steps[2], TaskStep)
        assert memory.steps[2].task == "Second question"
        assert isinstance(memory.steps[3], MemoryStep)
        assert len(memory.steps[3].tool_calls) == 1

    def test_from_dict_ignores_unknown_types(self):
        """Test that unknown step types are ignored."""
        data = [
            {"type": "task_step", "task": "Valid task"},
            {"type": "unknown_step", "data": "something"},
            {"type": "memory_step", "step_number": 1, "text": "Valid step"},
        ]

        memory = AgentMemory.from_dict(data)

        assert len(memory.steps) == 2
        assert isinstance(memory.steps[0], TaskStep)
        assert isinstance(memory.steps[1], MemoryStep)

    def test_roundtrip(self):
        """Test serialization roundtrip preserves full conversation."""
        original = AgentMemory()
        original.add_task("What is the weather?")
        original.add_step(
            MemoryStep(
                step_number=1,
                text="Let me check the weather.",
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments={"city": "Prague"})],
                tool_results=[ToolResult(tool_call_id="tc1", name="get_weather", content="Sunny, 25C")],
                input_tokens=100,
                output_tokens=50,
            )
        )
        original.add_step(MemoryStep(step_number=2, text="The weather in Prague is sunny and 25°C."))

        restored = AgentMemory.from_dict(original.to_dict())

        assert len(restored.steps) == len(original.steps)
        assert isinstance(restored.steps[0], TaskStep)
        assert restored.steps[0].task == "What is the weather?"
        assert isinstance(restored.steps[1], MemoryStep)
        assert restored.steps[1].tool_calls[0].arguments == {"city": "Prague"}
        assert restored.steps[1].tool_results[0].content == "Sunny, 25C"
        assert isinstance(restored.steps[2], MemoryStep)
        assert restored.steps[2].text == "The weather in Prague is sunny and 25°C."

    def test_roundtrip_produces_same_messages(self):
        """Test that restored memory produces identical messages."""
        original = AgentMemory()
        original.add_task("Test task")
        original.add_step(
            MemoryStep(
                step_number=1,
                text="Thinking...",
                tool_calls=[ToolCall(id="tc1", name="tool", arguments={"x": 1})],
                tool_results=[ToolResult(tool_call_id="tc1", name="tool", content="done")],
            )
        )
        original.add_step(MemoryStep(step_number=2, text="Final answer"))

        original_messages = original.write_to_messages()
        restored = AgentMemory.from_dict(original.to_dict())
        restored_messages = restored.write_to_messages()

        assert len(original_messages) == len(restored_messages)
        for orig, rest in zip(original_messages, restored_messages):
            assert orig["role"] == rest["role"]


class TestRossumAgentMemoryIntegration:
    """Test RossumAgent with memory system."""

    def _create_agent(self) -> RossumAgent:
        """Helper to create an agent with mocked dependencies."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        config = AgentConfig()
        return RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test prompt",
            config=config,
        )

    def test_reset_clears_memory_and_tokens(self):
        """Test that reset clears memory and token counts."""
        agent = self._create_agent()
        agent.memory.add_task("test")
        agent._total_input_tokens = 1000
        agent._total_output_tokens = 500

        agent.reset()

        assert agent.memory.steps == []
        assert agent._total_input_tokens == 0
        assert agent._total_output_tokens == 0

    def test_add_user_message_adds_task(self):
        """Test that add_user_message adds a TaskStep."""
        agent = self._create_agent()
        agent.add_user_message("Hello")

        assert len(agent.memory.steps) == 1
        assert isinstance(agent.memory.steps[0], TaskStep)
        assert agent.memory.steps[0].task == "Hello"

    def test_messages_property_rebuilds_from_memory(self):
        """Test that messages property rebuilds messages each time."""
        agent = self._create_agent()
        agent.memory.add_task("Task")
        agent.memory.add_step(
            MemoryStep(
                step_number=1,
                text="Thinking",
                tool_calls=[ToolCall(id="tc1", name="tool", arguments={})],
                tool_results=[ToolResult(tool_call_id="tc1", name="tool", content="result")],
            )
        )

        messages = agent.messages

        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"


class TestToolCallAndResult:
    """Test ToolCall and ToolResult dataclasses."""

    def test_tool_call_creation(self):
        """Test ToolCall dataclass creation."""
        tool_call = ToolCall(id="tc_1", name="get_data", arguments={"key": "value"})
        assert tool_call.id == "tc_1"
        assert tool_call.name == "get_data"
        assert tool_call.arguments == {"key": "value"}

    def test_tool_result_creation(self):
        """Test ToolResult dataclass creation."""
        result = ToolResult(
            tool_call_id="tc_1",
            name="get_data",
            content='{"data": "test"}',
        )
        assert result.tool_call_id == "tc_1"
        assert result.name == "get_data"
        assert result.content == '{"data": "test"}'
        assert result.is_error is False

    def test_tool_result_with_error(self):
        """Test ToolResult dataclass with error flag."""
        result = ToolResult(
            tool_call_id="tc_1",
            name="get_data",
            content="Error: Connection failed",
            is_error=True,
        )
        assert result.is_error is True


class TestStreamModelResponse:
    """Test _stream_model_response behavior with various event sequences."""

    def _create_agent(self) -> RossumAgent:
        """Helper to create an agent with mocked dependencies."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        mock_mcp_connection.get_tools.return_value = []
        config = AgentConfig()
        return RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test prompt",
            config=config,
        )

    def _create_mock_stream(self, events: list, final_message: Message):
        """Create a mock stream context manager that yields events."""
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.__iter__ = MagicMock(return_value=iter(events))
        mock_stream.get_final_message.return_value = final_message
        return mock_stream

    def _create_final_message(self, input_tokens: int = 100, output_tokens: int = 50) -> Message:
        """Create a mock final message with usage stats."""
        return Message(
            id="msg_test",
            type="message",
            role="assistant",
            content=[],
            model="test-model",
            stop_reason="end_turn",
            stop_sequence=None,
            usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
        )

    @pytest.mark.asyncio
    async def test_pure_text_completion_no_tools(self):
        """Test streaming with pure text completion (no tool calls)."""
        agent = self._create_agent()
        agent.memory.add_task("Hello")

        text_delta_event = RawContentBlockDeltaEvent(
            type="content_block_delta",
            index=0,
            delta=TextDelta(type="text_delta", text="Hello, how can I help you?"),
        )
        final_message = self._create_final_message()
        mock_stream = self._create_mock_stream([text_delta_event], final_message)

        with patch.object(agent.client.messages, "stream", return_value=mock_stream):
            steps = []
            async for step in agent._stream_model_response(1):
                steps.append(step)

        assert len(steps) >= 1
        final_step = steps[-1]
        assert final_step.is_final is True
        assert final_step.final_answer == "Hello, how can I help you?"
        assert final_step.tool_calls == []
        assert final_step.input_tokens == 100
        assert final_step.output_tokens == 50

    @pytest.mark.asyncio
    async def test_single_tool_use_block(self):
        """Test streaming with a single tool_use block."""
        agent = self._create_agent()
        agent.memory.add_task("List queues")
        agent.mcp_connection.call_tool.return_value = {"queues": []}

        tool_block = ToolUseBlock(
            type="tool_use",
            id="tool_123",
            name="list_queues",
            input={},
        )

        start_event = RawContentBlockStartEvent(
            type="content_block_start",
            index=0,
            content_block=tool_block,
        )

        delta_event = RawContentBlockDeltaEvent(
            type="content_block_delta",
            index=0,
            delta=InputJSONDelta(
                type="input_json_delta",
                partial_json='{"workspace_url": "https://example.com"}',
            ),
        )

        stop_event = ContentBlockStopEvent(
            type="content_block_stop",
            index=0,
        )

        final_message = self._create_final_message()
        mock_stream = self._create_mock_stream([start_event, delta_event, stop_event], final_message)

        with patch.object(agent.client.messages, "stream", return_value=mock_stream):
            steps = []
            async for step in agent._stream_model_response(1):
                steps.append(step)

        final_step = steps[-1]
        assert final_step.is_final is False
        assert len(final_step.tool_calls) == 1
        assert final_step.tool_calls[0].name == "list_queues"
        assert final_step.tool_calls[0].arguments == {"workspace_url": "https://example.com"}
        assert len(final_step.tool_results) == 1

    @pytest.mark.asyncio
    async def test_malformed_json_tool_input(self):
        """Test streaming with malformed JSON in tool input."""
        agent = self._create_agent()
        agent.memory.add_task("List queues")
        agent.mcp_connection.call_tool.return_value = {"queues": []}

        tool_block = ToolUseBlock(
            type="tool_use",
            id="tool_123",
            name="list_queues",
            input={},
        )

        start_event = RawContentBlockStartEvent(
            type="content_block_start",
            index=0,
            content_block=tool_block,
        )

        delta_event = RawContentBlockDeltaEvent(
            type="content_block_delta",
            index=0,
            delta=InputJSONDelta(
                type="input_json_delta",
                partial_json='{"invalid json',
            ),
        )

        stop_event = ContentBlockStopEvent(
            type="content_block_stop",
            index=0,
        )

        final_message = self._create_final_message()
        mock_stream = self._create_mock_stream([start_event, delta_event, stop_event], final_message)

        with patch.object(agent.client.messages, "stream", return_value=mock_stream):
            steps = []
            async for step in agent._stream_model_response(1):
                steps.append(step)

        final_step = steps[-1]
        assert len(final_step.tool_calls) == 1
        assert final_step.tool_calls[0].arguments == {}

    @pytest.mark.asyncio
    async def test_text_with_tool_call(self):
        """Test streaming with both thinking and text blocks plus tool call.

        With extended thinking, thinking blocks contain model reasoning,
        text blocks contain the response text, and both are separate.
        """
        from anthropic.types import ThinkingBlock, ThinkingDelta

        agent = self._create_agent()
        agent.memory.add_task("Help me")
        agent.mcp_connection.call_tool.return_value = "result"

        thinking_block = ThinkingBlock(type="thinking", thinking="", signature="sig")
        thinking_start = RawContentBlockStartEvent(
            type="content_block_start",
            index=0,
            content_block=thinking_block,
        )

        thinking_delta_event = RawContentBlockDeltaEvent(
            type="content_block_delta",
            index=0,
            delta=ThinkingDelta(type="thinking_delta", thinking="Let me analyze this..."),
        )

        thinking_stop = ContentBlockStopEvent(
            type="content_block_stop",
            index=0,
        )

        text_delta = RawContentBlockDeltaEvent(
            type="content_block_delta",
            index=1,
            delta=TextDelta(type="text_delta", text="Let me check that for you."),
        )

        tool_block = ToolUseBlock(
            type="tool_use",
            id="tool_456",
            name="get_info",
            input={},
        )

        tool_start = RawContentBlockStartEvent(
            type="content_block_start",
            index=2,
            content_block=tool_block,
        )

        tool_delta = RawContentBlockDeltaEvent(
            type="content_block_delta",
            index=2,
            delta=InputJSONDelta(type="input_json_delta", partial_json="{}"),
        )

        tool_stop = ContentBlockStopEvent(
            type="content_block_stop",
            index=2,
        )

        final_message = self._create_final_message()
        mock_stream = self._create_mock_stream(
            [thinking_start, thinking_delta_event, thinking_stop, text_delta, tool_start, tool_delta, tool_stop],
            final_message,
        )

        with patch.object(agent.client.messages, "stream", return_value=mock_stream):
            steps = []
            async for step in agent._stream_model_response(1):
                steps.append(step)

        final_step = steps[-1]
        assert final_step.thinking == "Let me analyze this..."
        assert len(final_step.tool_calls) == 1


class TestAgentRun:
    """Test RossumAgent.run() method with various scenarios."""

    def _create_agent(self) -> RossumAgent:
        """Helper to create an agent with mocked dependencies."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        mock_mcp_connection.get_tools.return_value = []
        config = AgentConfig(max_steps=3)
        return RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test prompt",
            config=config,
        )

    @pytest.mark.asyncio
    async def test_stops_when_is_final_true(self):
        """Test that run() stops when step.is_final is True."""
        agent = self._create_agent()

        final_step = AgentStep(
            step_number=1,
            final_answer="Done!",
            is_final=True,
        )

        async def mock_stream_response(step_num):
            yield final_step

        with patch.object(agent, "_stream_model_response", side_effect=mock_stream_response):
            steps = []
            async for step in agent.run("Test prompt"):
                steps.append(step)

        assert len(steps) == 1
        assert steps[0].is_final is True
        assert steps[0].final_answer == "Done!"

    @pytest.mark.asyncio
    async def test_continues_when_not_final(self):
        """Test that run() continues processing when step is not final."""
        agent = self._create_agent()

        call_count = [0]

        async def mock_stream_response(step_num):
            call_count[0] += 1
            if call_count[0] < 2:
                yield AgentStep(
                    step_number=step_num,
                    tool_calls=[ToolCall(id="tc1", name="tool", arguments={})],
                    is_streaming=True,
                )
                yield AgentStep(
                    step_number=step_num,
                    tool_calls=[ToolCall(id="tc1", name="tool", arguments={})],
                    tool_results=[ToolResult(tool_call_id="tc1", name="tool", content="result")],
                    is_final=False,
                    is_streaming=False,
                )
            else:
                yield AgentStep(
                    step_number=step_num,
                    final_answer="All done!",
                    is_final=True,
                    is_streaming=False,
                )

        with patch.object(agent, "_stream_model_response", side_effect=mock_stream_response):
            steps = []
            async for step in agent.run("Test prompt"):
                steps.append(step)

        final_steps = [s for s in steps if not s.is_streaming]
        assert len(final_steps) == 2
        assert final_steps[-1].is_final is True

    @pytest.mark.asyncio
    async def test_max_steps_reached(self):
        """Test that run() stops and yields error when max_steps is reached."""
        agent = self._create_agent()

        async def mock_stream_response(step_num):
            yield AgentStep(
                step_number=step_num,
                tool_calls=[ToolCall(id="tc1", name="tool", arguments={})],
                tool_results=[ToolResult(tool_call_id="tc1", name="tool", content="result")],
                is_final=False,
                is_streaming=False,
            )

        with patch.object(agent, "_stream_model_response", side_effect=mock_stream_response):
            steps = []
            async for step in agent.run("Test prompt"):
                steps.append(step)

        assert steps[-1].is_final is True
        assert "Maximum steps" in steps[-1].error
        assert "3" in steps[-1].error

    @pytest.mark.asyncio
    async def test_rate_limit_error_exhausts_retries(self):
        """Test that RateLimitError exhausts retries and returns error."""
        agent = self._create_agent()

        call_count = [0]

        async def mock_stream_response(step_num):
            call_count[0] += 1
            raise RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429),
                body=None,
            )
            yield  # Make it a generator

        with (
            patch.object(agent, "_stream_model_response", side_effect=mock_stream_response),
            patch("rossum_agent.agent.core.asyncio.sleep", new_callable=AsyncMock),
        ):
            steps = []
            async for step in agent.run("Test prompt"):
                steps.append(step)

        final_steps = [s for s in steps if s.is_final]
        assert len(final_steps) == 1
        assert final_steps[0].is_final is True
        assert "Rate limit" in final_steps[0].error
        assert "5 retries" in final_steps[0].error
        assert call_count[0] == 6  # Initial attempt + 5 retries

    @pytest.mark.asyncio
    async def test_rate_limit_retry_succeeds_after_transient_failure(self):
        """Test that rate limit retry succeeds after transient failure."""
        agent = self._create_agent()

        call_count = [0]

        async def mock_stream_response(step_num):
            call_count[0] += 1
            if call_count[0] < 3:
                raise RateLimitError(
                    message="Rate limit exceeded",
                    response=MagicMock(status_code=429),
                    body=None,
                )
            yield AgentStep(step_number=step_num, final_answer="Success!", is_final=True)

        with (
            patch.object(agent, "_stream_model_response", side_effect=mock_stream_response),
            patch("rossum_agent.agent.core.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            steps = []
            async for step in agent.run("Test prompt"):
                steps.append(step)

        assert call_count[0] == 3  # 2 failures + 1 success
        assert mock_sleep.await_count == 2  # Called for each retry wait
        final_steps = [s for s in steps if s.is_final]
        assert len(final_steps) == 1
        assert final_steps[0].final_answer == "Success!"

    @pytest.mark.asyncio
    async def test_rate_limit_yields_progress_step_during_wait(self):
        """Test that rate limit retry yields a progress step during wait."""
        agent = self._create_agent()

        call_count = [0]

        async def mock_stream_response(step_num):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RateLimitError(
                    message="Rate limit exceeded",
                    response=MagicMock(status_code=429),
                    body=None,
                )
            yield AgentStep(step_number=step_num, final_answer="Done", is_final=True)

        with (
            patch.object(agent, "_stream_model_response", side_effect=mock_stream_response),
            patch("rossum_agent.agent.core.asyncio.sleep", new_callable=AsyncMock),
        ):
            steps = []
            async for step in agent.run("Test prompt"):
                steps.append(step)

        streaming_steps = [s for s in steps if s.is_streaming and s.thinking]
        assert len(streaming_steps) >= 1
        assert "Rate limited" in streaming_steps[0].thinking
        assert "waiting" in streaming_steps[0].thinking.lower()

    @pytest.mark.asyncio
    async def test_rate_limit_exponential_backoff_delay(self):
        """Test that rate limit uses exponential backoff with jitter."""
        agent = self._create_agent()

        call_count = [0]

        async def mock_stream_response(step_num):
            call_count[0] += 1
            if call_count[0] <= 3:
                raise RateLimitError(
                    message="Rate limit exceeded",
                    response=MagicMock(status_code=429),
                    body=None,
                )
            yield AgentStep(step_number=step_num, final_answer="Done", is_final=True)

        sleep_durations = []

        async def capture_sleep(duration):
            sleep_durations.append(duration)

        with (
            patch.object(agent, "_stream_model_response", side_effect=mock_stream_response),
            patch("rossum_agent.agent.core.asyncio.sleep", side_effect=capture_sleep),
            patch("rossum_agent.agent.core.random.uniform", return_value=0.0),  # No jitter for deterministic test
        ):
            steps = []
            async for step in agent.run("Test prompt"):
                steps.append(step)

        assert len(sleep_durations) == 3
        # Base delay is 2.0, so: 2.0, 4.0, 8.0
        assert sleep_durations[0] == 2.0
        assert sleep_durations[1] == 4.0
        assert sleep_durations[2] == 8.0

    @pytest.mark.asyncio
    async def test_api_timeout_error_handling(self):
        """Test that APITimeoutError is handled gracefully."""
        agent = self._create_agent()

        async def mock_stream_response(step_num):
            raise APITimeoutError(request=MagicMock())
            yield  # Make it a generator

        with patch.object(agent, "_stream_model_response", side_effect=mock_stream_response):
            steps = []
            async for step in agent.run("Test prompt"):
                steps.append(step)

        assert len(steps) == 1
        assert steps[0].is_final is True
        assert "timed out" in steps[0].error

    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """Test that generic APIError is handled gracefully."""
        agent = self._create_agent()

        async def mock_stream_response(step_num):
            raise APIError(
                message="Internal server error",
                request=MagicMock(),
                body=None,
            )
            yield  # Make it a generator

        with patch.object(agent, "_stream_model_response", side_effect=mock_stream_response):
            steps = []
            async for step in agent.run("Test prompt"):
                steps.append(step)

        assert len(steps) == 1
        assert steps[0].is_final is True
        assert "API error" in steps[0].error


class TestExecuteTool:
    """Test RossumAgent._execute_tool_with_progress method."""

    def _create_agent(self) -> RossumAgent:
        """Helper to create an agent with mocked dependencies."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        mock_mcp_connection.get_tools.return_value = []
        config = AgentConfig()
        return RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test prompt",
            config=config,
        )

    async def _get_final_result(self, agent: RossumAgent, tool_call: ToolCall) -> ToolResult:
        """Helper to get the final ToolResult from _execute_tool_with_progress."""
        result = None
        async for item in agent._execute_tool_with_progress(tool_call, 1, [tool_call], (1, 1)):
            if isinstance(item, ToolResult):
                result = item
        assert result is not None
        return result

    @pytest.mark.asyncio
    async def test_executes_internal_tool(self):
        """Test that internal tools are executed locally."""
        agent = self._create_agent()

        tool_call = ToolCall(
            id="tc_1",
            name="write_file",
            arguments={"filename": "test.txt", "content": "Hello"},
        )

        with patch("rossum_agent.agent.core.execute_internal_tool", return_value="Success") as mock_execute:
            result = await self._get_final_result(agent, tool_call)

        mock_execute.assert_called_once()
        assert result.content == "Success"
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_executes_mcp_tool(self):
        """Test that MCP tools are called via MCP connection."""
        agent = self._create_agent()
        agent.mcp_connection.call_tool.return_value = {"queues": ["q1", "q2"]}

        tool_call = ToolCall(
            id="tc_1",
            name="list_queues",
            arguments={"workspace_url": "https://example.com"},
        )

        result = await self._get_final_result(agent, tool_call)

        agent.mcp_connection.call_tool.assert_called_once_with("list_queues", {"workspace_url": "https://example.com"})
        assert "queues" in result.content
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_handles_tool_execution_error(self):
        """Test that tool execution errors are handled gracefully."""
        agent = self._create_agent()
        agent.mcp_connection.call_tool.side_effect = Exception("Connection failed")

        tool_call = ToolCall(
            id="tc_1",
            name="failing_tool",
            arguments={},
        )

        result = await self._get_final_result(agent, tool_call)

        assert result.is_error is True
        assert "Connection failed" in result.content

    @pytest.mark.asyncio
    async def test_truncates_long_content(self):
        """Test that long tool output is truncated."""
        agent = self._create_agent()
        long_output = "A" * 30000
        agent.mcp_connection.call_tool.return_value = long_output

        tool_call = ToolCall(id="tc_1", name="verbose_tool", arguments={})

        result = await self._get_final_result(agent, tool_call)

        assert len(result.content) < 30000
        assert "truncated" in result.content.lower()

    @pytest.mark.asyncio
    async def test_executes_deploy_tool(self):
        """Test that deploy tools are executed locally."""
        agent = self._create_agent()

        tool_call = ToolCall(
            id="tc_1",
            name="deploy_hook",
            arguments={"hook_id": "123"},
        )

        with patch("rossum_agent.agent.core.execute_tool", return_value="Deploy Success") as mock_execute:
            with patch("rossum_agent.agent.core.get_deploy_tool_names", return_value=["deploy_hook"]):
                result = await self._get_final_result(agent, tool_call)

        mock_execute.assert_called_once()
        assert result.content == "Deploy Success"
        assert result.is_error is False


class TestExecuteToolsInParallel:
    """Test RossumAgent._execute_tools_with_progress parallel execution."""

    def _create_agent(self) -> RossumAgent:
        """Helper to create an agent with mocked dependencies."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        mock_mcp_connection.get_tools.return_value = []
        config = AgentConfig()
        return RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test prompt",
            config=config,
        )

    @pytest.mark.asyncio
    async def test_executes_multiple_tools_in_parallel(self):
        """Test that multiple tools are executed concurrently."""
        agent = self._create_agent()

        execution_times: list[float] = []

        async def slow_tool(*args, **kwargs):
            execution_times.append(time.monotonic())
            await asyncio.sleep(0.1)
            return "result"

        agent.mcp_connection.call_tool = slow_tool

        tool_calls = [
            ToolCall(id="tc_1", name="tool_a", arguments={}),
            ToolCall(id="tc_2", name="tool_b", arguments={}),
            ToolCall(id="tc_3", name="tool_c", arguments={}),
        ]

        step = AgentStep(step_number=1, tool_calls=tool_calls)

        steps = []
        async for s in agent._execute_tools_with_progress(
            step_num=1,
            thinking_text="",
            tool_calls=tool_calls,
            step=step,
            input_tokens=100,
            output_tokens=50,
        ):
            steps.append(s)

        # All tools should have started at nearly the same time (parallel execution)
        assert len(execution_times) == 3
        time_spread = max(execution_times) - min(execution_times)
        # If parallel, all should start within 50ms of each other
        assert time_spread < 0.05

    @pytest.mark.asyncio
    async def test_preserves_tool_result_order(self):
        """Test that tool results are returned in the same order as tool calls."""
        agent = self._create_agent()

        async def varying_delay_tool(name, args):
            # Make each tool take different time to complete
            delays = {"fast_tool": 0.01, "medium_tool": 0.05, "slow_tool": 0.1}
            await asyncio.sleep(delays.get(name, 0.01))
            return f"result_{name}"

        agent.mcp_connection.call_tool = varying_delay_tool

        tool_calls = [
            ToolCall(id="tc_1", name="slow_tool", arguments={}),
            ToolCall(id="tc_2", name="fast_tool", arguments={}),
            ToolCall(id="tc_3", name="medium_tool", arguments={}),
        ]

        step = AgentStep(step_number=1, tool_calls=tool_calls)

        final_step = None
        async for s in agent._execute_tools_with_progress(
            step_num=1,
            thinking_text="",
            tool_calls=tool_calls,
            step=step,
            input_tokens=100,
            output_tokens=50,
        ):
            final_step = s

        # Results should be in same order as tool_calls, regardless of completion order
        assert final_step is not None
        assert len(final_step.tool_results) == 3
        assert final_step.tool_results[0].tool_call_id == "tc_1"
        assert final_step.tool_results[1].tool_call_id == "tc_2"
        assert final_step.tool_results[2].tool_call_id == "tc_3"

    @pytest.mark.asyncio
    async def test_handles_tool_error_in_parallel_execution(self):
        """Test that errors in one tool don't affect other parallel tools."""
        agent = self._create_agent()

        async def mixed_tool(name, args):
            if name == "failing_tool":
                raise Exception("Tool failed")
            return f"success_{name}"

        agent.mcp_connection.call_tool = mixed_tool

        tool_calls = [
            ToolCall(id="tc_1", name="good_tool", arguments={}),
            ToolCall(id="tc_2", name="failing_tool", arguments={}),
            ToolCall(id="tc_3", name="another_good_tool", arguments={}),
        ]

        step = AgentStep(step_number=1, tool_calls=tool_calls)

        final_step = None
        async for s in agent._execute_tools_with_progress(
            step_num=1,
            thinking_text="",
            tool_calls=tool_calls,
            step=step,
            input_tokens=100,
            output_tokens=50,
        ):
            final_step = s

        assert final_step is not None
        assert len(final_step.tool_results) == 3
        # First tool succeeded
        assert final_step.tool_results[0].is_error is False
        # Second tool failed
        assert final_step.tool_results[1].is_error is True
        assert "Tool failed" in final_step.tool_results[1].content
        # Third tool succeeded
        assert final_step.tool_results[2].is_error is False

    @pytest.mark.asyncio
    async def test_yields_progress_steps_during_parallel_execution(self):
        """Test that progress updates are yielded during parallel tool execution."""
        agent = self._create_agent()

        tool_calls = [
            ToolCall(id="tc_1", name="tool_a", arguments={}),
            ToolCall(id="tc_2", name="tool_b", arguments={}),
        ]

        step = AgentStep(step_number=1, tool_calls=tool_calls)

        agent.mcp_connection.call_tool.return_value = "result"

        steps = []
        async for s in agent._execute_tools_with_progress(
            step_num=1,
            thinking_text="Test thinking",
            tool_calls=tool_calls,
            step=step,
            input_tokens=100,
            output_tokens=50,
        ):
            steps.append(s)

        # Should have at least the initial progress step and final step
        assert len(steps) >= 2
        # First step should be progress indicator
        assert steps[0].is_streaming is True
        assert steps[0].tool_progress == (0, 2)


class TestSerializeToolResult:
    """Test RossumAgent._serialize_tool_result method."""

    def _create_agent(self) -> RossumAgent:
        """Helper to create an agent with mocked dependencies."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        config = AgentConfig()
        return RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test prompt",
            config=config,
        )

    def test_serialize_none_result(self):
        """Test that None result returns success message."""
        agent = self._create_agent()
        result = agent._serialize_tool_result(None)
        assert result == "Tool executed successfully (no output)"

    def test_serialize_dataclass(self):
        """Test that dataclass is serialized to JSON."""
        from dataclasses import dataclass

        @dataclass
        class TestData:
            name: str
            value: int

        agent = self._create_agent()
        data = TestData(name="test", value=42)
        result = agent._serialize_tool_result(data)

        assert '"name": "test"' in result
        assert '"value": 42' in result

    def test_serialize_list_of_dataclasses(self):
        """Test that list of dataclasses is serialized to JSON."""
        from dataclasses import dataclass

        @dataclass
        class Item:
            id: int

        agent = self._create_agent()
        items = [Item(id=1), Item(id=2)]
        result = agent._serialize_tool_result(items)

        assert '"id": 1' in result
        assert '"id": 2' in result

    def test_serialize_pydantic_model(self):
        """Test that pydantic model is serialized to JSON."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            field: str

        agent = self._create_agent()
        model = TestModel(field="value")
        result = agent._serialize_tool_result(model)

        assert '"field": "value"' in result

    def test_serialize_list_of_pydantic_models(self):
        """Test that list of pydantic models is serialized to JSON."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            id: int

        agent = self._create_agent()
        models = [TestModel(id=1), TestModel(id=2)]
        result = agent._serialize_tool_result(models)

        assert '"id": 1' in result
        assert '"id": 2' in result

    def test_serialize_dict(self):
        """Test that dict is serialized to JSON."""
        agent = self._create_agent()
        result = agent._serialize_tool_result({"key": "value"})

        assert '"key": "value"' in result

    def test_serialize_list(self):
        """Test that list is serialized to JSON."""
        agent = self._create_agent()
        result = agent._serialize_tool_result([1, 2, 3])

        assert "[" in result
        assert "1" in result

    def test_serialize_string(self):
        """Test that string is returned as-is."""
        agent = self._create_agent()
        result = agent._serialize_tool_result("plain text")

        assert result == "plain text"

    def test_serialize_number(self):
        """Test that number is converted to string."""
        agent = self._create_agent()
        result = agent._serialize_tool_result(42)

        assert result == "42"


class TestExtractTextFromPrompt:
    """Test RossumAgent._extract_text_from_prompt method."""

    def _create_agent(self) -> RossumAgent:
        """Helper to create an agent with mocked dependencies."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        config = AgentConfig()
        return RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test prompt",
            config=config,
        )

    def test_extracts_from_string(self):
        """Test extraction from simple string prompt."""
        agent = self._create_agent()
        result = agent._extract_text_from_prompt("Hello world")
        assert result == "Hello world"

    def test_extracts_from_list_with_text_blocks(self):
        """Test extraction from list of content blocks."""
        agent = self._create_agent()
        prompt = [
            {"type": "text", "text": "First part"},
            {"type": "text", "text": "Second part"},
        ]
        result = agent._extract_text_from_prompt(prompt)
        assert result == "First part Second part"

    def test_ignores_non_text_blocks(self):
        """Test that non-text blocks are ignored."""
        agent = self._create_agent()
        prompt = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "abc"}},
            {"type": "text", "text": "Analyze this"},
        ]
        result = agent._extract_text_from_prompt(prompt)
        assert result == "Analyze this"

    def test_handles_missing_text_field(self):
        """Test handling of blocks with missing text field."""
        agent = self._create_agent()
        prompt = [{"type": "text"}, {"type": "text", "text": "Valid"}]
        result = agent._extract_text_from_prompt(prompt)
        assert result == "Valid"


class TestCheckRequestScope:
    """Test RossumAgent._check_request_scope method."""

    def _create_agent(self) -> RossumAgent:
        """Helper to create an agent with mocked dependencies."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        config = AgentConfig()
        return RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test prompt",
            config=config,
        )

    def test_returns_none_for_in_scope_request(self):
        """Test that in-scope requests return None (proceed)."""
        agent = self._create_agent()

        with patch("rossum_agent.agent.core.classify_request") as mock_classify:
            from rossum_agent.agent.request_classifier import ClassificationResult, RequestScope

            mock_classify.return_value = ClassificationResult(
                scope=RequestScope.IN_SCOPE, raw_response="IN_SCOPE", input_tokens=10, output_tokens=5
            )

            result = agent._check_request_scope("List queues")

        assert result is None
        assert agent._total_input_tokens == 10
        assert agent._total_output_tokens == 5

    def test_returns_rejection_step_for_out_of_scope_request(self):
        """Test that out-of-scope requests return rejection step."""
        agent = self._create_agent()

        with (
            patch("rossum_agent.agent.core.classify_request") as mock_classify,
            patch("rossum_agent.agent.core.generate_rejection_response") as mock_rejection,
        ):
            from rossum_agent.agent.request_classifier import (
                ClassificationResult,
                RejectionResult,
                RequestScope,
            )

            mock_classify.return_value = ClassificationResult(
                scope=RequestScope.OUT_OF_SCOPE, raw_response="OUT_OF_SCOPE", input_tokens=10, output_tokens=5
            )
            mock_rejection.return_value = RejectionResult(
                response="I can help with Rossum tasks.", input_tokens=20, output_tokens=15
            )

            result = agent._check_request_scope("What's the weather?")

        assert result is not None
        assert result.is_final is True
        assert result.final_answer == "I can help with Rossum tasks."
        assert result.input_tokens == 30  # 10 + 20
        assert result.output_tokens == 20  # 5 + 15


class TestAgentRunRequestDelay:
    """Test RossumAgent.run() request delay behavior."""

    def _create_agent(self) -> RossumAgent:
        """Helper to create an agent with request delay."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        mock_mcp_connection.get_tools.return_value = []
        config = AgentConfig(max_steps=3, request_delay=1.0)
        return RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test prompt",
            config=config,
        )

    @pytest.mark.asyncio
    async def test_request_delay_between_steps(self):
        """Test that request delay is applied between steps (not on first step)."""
        agent = self._create_agent()

        call_count = [0]
        sleep_calls = []

        async def mock_stream_response(step_num):
            call_count[0] += 1
            if call_count[0] < 3:
                yield AgentStep(
                    step_number=step_num,
                    tool_calls=[ToolCall(id="tc1", name="tool", arguments={})],
                    tool_results=[ToolResult(tool_call_id="tc1", name="tool", content="result")],
                    is_final=False,
                    is_streaming=False,
                )
            else:
                yield AgentStep(step_number=step_num, final_answer="Done", is_final=True, is_streaming=False)

        async def capture_sleep(duration):
            sleep_calls.append(duration)
            # Don't actually sleep in tests

        with (
            patch.object(agent, "_stream_model_response", side_effect=mock_stream_response),
            patch("rossum_agent.agent.core.asyncio.sleep", side_effect=capture_sleep),
        ):
            steps = []
            async for step in agent.run("Test prompt"):
                steps.append(step)

        # Should have delays for step 2 and 3 (not step 1)
        assert len(sleep_calls) == 2
        assert all(d == 1.0 for d in sleep_calls)


class TestAgentRunOutOfScope:
    """Test RossumAgent.run() out-of-scope handling."""

    def _create_agent(self) -> RossumAgent:
        """Helper to create an agent."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        config = AgentConfig()
        return RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test prompt",
            config=config,
        )

    @pytest.mark.asyncio
    async def test_run_yields_rejection_for_out_of_scope(self):
        """Test that run() yields rejection and returns for out-of-scope requests."""
        agent = self._create_agent()

        rejection_step = AgentStep(
            step_number=1, final_answer="I focus on Rossum tasks.", is_final=True, input_tokens=30, output_tokens=20
        )

        with patch.object(agent, "_check_request_scope", return_value=rejection_step):
            steps = []
            async for step in agent.run("What's the weather?"):
                steps.append(step)

        assert len(steps) == 1
        assert steps[0].is_final is True
        assert steps[0].final_answer == "I focus on Rossum tasks."


class TestAgentAddAssistantMessage:
    """Test RossumAgent.add_assistant_message method."""

    def _create_agent(self) -> RossumAgent:
        """Helper to create an agent."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        config = AgentConfig()
        return RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test prompt",
            config=config,
        )

    def test_adds_memory_step_with_text(self):
        """Test that add_assistant_message adds a MemoryStep with text."""
        agent = self._create_agent()
        agent.add_assistant_message("Hello, I'm here to help!")

        assert len(agent.memory.steps) == 1
        assert isinstance(agent.memory.steps[0], MemoryStep)
        assert agent.memory.steps[0].text == "Hello, I'm here to help!"
        assert agent.memory.steps[0].step_number == 0


class TestAgentGetTools:
    """Test RossumAgent._get_tools caching behavior."""

    def _create_agent(self) -> RossumAgent:
        """Helper to create an agent."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        mock_mcp_connection.get_tools.return_value = []
        config = AgentConfig()
        return RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test prompt",
            config=config,
        )

    @pytest.mark.asyncio
    async def test_caches_tools_after_first_call(self):
        """Test that tools are cached and MCP is only called once."""
        agent = self._create_agent()
        agent.mcp_connection.get_tools.return_value = [MagicMock(name="tool1", description="test", inputSchema={})]

        # Call twice
        await agent._get_tools()
        await agent._get_tools()

        # MCP should only be called once
        agent.mcp_connection.get_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_includes_additional_tools(self):
        """Test that additional tools are included in the tools list."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        mock_mcp_connection.get_tools.return_value = []
        additional = [{"name": "custom_tool", "description": "custom", "input_schema": {}}]

        agent = RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test",
            additional_tools=additional,
        )

        tools = await agent._get_tools()

        # Should include additional tools
        assert any(t.get("name") == "custom_tool" for t in tools if isinstance(t, dict))


class TestCreateAgentFactory:
    """Test create_agent factory function."""

    @pytest.mark.asyncio
    async def test_creates_agent_with_default_config(self):
        """Test that create_agent creates an agent with proper setup."""
        from rossum_agent.agent.core import create_agent

        mock_mcp = AsyncMock()

        with patch("rossum_agent.agent.core.create_bedrock_client") as mock_create_client:
            mock_create_client.return_value = MagicMock()

            agent = await create_agent(
                mcp_connection=mock_mcp,
                system_prompt="Test system prompt",
            )

        assert isinstance(agent, RossumAgent)
        assert agent.system_prompt == "Test system prompt"
        mock_create_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_agent_with_custom_config(self):
        """Test that create_agent respects custom config."""
        from rossum_agent.agent.core import create_agent

        mock_mcp = AsyncMock()
        config = AgentConfig(max_steps=10)

        with patch("rossum_agent.agent.core.create_bedrock_client") as mock_create_client:
            mock_create_client.return_value = MagicMock()

            agent = await create_agent(
                mcp_connection=mock_mcp,
                system_prompt="Test",
                config=config,
            )

        assert agent.config.max_steps == 10
        assert agent.config.temperature == 1.0  # Must be 1.0 for extended thinking


class TestProcessStreamEvent:
    """Test RossumAgent._process_stream_event method directly."""

    def _create_agent(self) -> RossumAgent:
        """Helper to create an agent."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        config = AgentConfig()
        return RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test prompt",
            config=config,
        )

    def test_content_block_start_event_for_tool_use(self):
        """Test processing ContentBlockStartEvent for tool use."""
        agent = self._create_agent()
        pending_tools: dict[int, dict[str, str]] = {}
        tool_calls: list[ToolCall] = []

        tool_block = ToolUseBlock(type="tool_use", id="tool_123", name="test_tool", input={})
        event = RawContentBlockStartEvent(type="content_block_start", index=0, content_block=tool_block)

        delta = agent._process_stream_event(event, pending_tools, tool_calls)

        assert delta is None
        assert 0 in pending_tools
        assert pending_tools[0]["name"] == "test_tool"
        assert pending_tools[0]["id"] == "tool_123"

    def test_content_block_delta_event_for_text(self):
        """Test processing ContentBlockDeltaEvent for text."""
        agent = self._create_agent()
        pending_tools: dict[int, dict[str, str]] = {}
        tool_calls: list[ToolCall] = []

        event = RawContentBlockDeltaEvent(
            type="content_block_delta", index=0, delta=TextDelta(type="text_delta", text="Hello world")
        )

        delta = agent._process_stream_event(event, pending_tools, tool_calls)

        assert delta is not None
        assert delta.kind == "text"
        assert delta.content == "Hello world"

    def test_content_block_delta_event_for_json(self):
        """Test processing ContentBlockDeltaEvent for JSON input."""
        agent = self._create_agent()
        pending_tools: dict[int, dict[str, str]] = {0: {"name": "tool", "id": "t1", "json": ""}}
        tool_calls: list[ToolCall] = []

        event = RawContentBlockDeltaEvent(
            type="content_block_delta", index=0, delta=InputJSONDelta(type="input_json_delta", partial_json='{"key":')
        )

        delta = agent._process_stream_event(event, pending_tools, tool_calls)

        assert delta is None
        assert pending_tools[0]["json"] == '{"key":'

    def test_content_block_stop_event_with_empty_json(self):
        """Test processing ContentBlockStopEvent with empty JSON."""
        agent = self._create_agent()
        pending_tools: dict[int, dict[str, str]] = {0: {"name": "tool", "id": "t1", "json": ""}}
        tool_calls: list[ToolCall] = []

        event = ContentBlockStopEvent(type="content_block_stop", index=0)

        delta = agent._process_stream_event(event, pending_tools, tool_calls)

        assert delta is None
        assert len(tool_calls) == 1
        assert tool_calls[0].arguments == {}

    def test_unhandled_event_returns_none(self):
        """Test that unhandled events return None."""
        agent = self._create_agent()
        pending_tools: dict[int, dict[str, str]] = {}
        tool_calls: list[ToolCall] = []

        event = MagicMock()

        delta = agent._process_stream_event(event, pending_tools, tool_calls)

        assert delta is None

    def test_content_block_start_event_for_thinking(self):
        """Test processing ContentBlockStartEvent for thinking block returns None."""
        from anthropic.types import ThinkingBlock

        agent = self._create_agent()
        pending_tools: dict[int, dict[str, str]] = {}
        tool_calls: list[ToolCall] = []

        thinking_block = ThinkingBlock(type="thinking", thinking="", signature="sig")
        event = RawContentBlockStartEvent(type="content_block_start", index=0, content_block=thinking_block)

        delta = agent._process_stream_event(event, pending_tools, tool_calls)

        assert delta is None

    def test_content_block_delta_event_for_thinking(self):
        """Test processing ContentBlockDeltaEvent for thinking delta."""
        from anthropic.types import ThinkingDelta

        agent = self._create_agent()
        pending_tools: dict[int, dict[str, str]] = {}
        tool_calls: list[ToolCall] = []

        event = RawContentBlockDeltaEvent(
            type="content_block_delta", index=0, delta=ThinkingDelta(type="thinking_delta", thinking="Let me think...")
        )

        delta = agent._process_stream_event(event, pending_tools, tool_calls)

        assert delta is not None
        assert delta.kind == "thinking"
        assert delta.content == "Let me think..."


class TestStreamState:
    """Test _StreamState class."""

    def test_flush_buffer_returns_none_when_empty(self):
        """Test that flush_buffer returns None when buffer is empty."""
        from rossum_agent.agent.core import _StreamState
        from rossum_agent.agent.models import StepType

        state = _StreamState()
        result = state.flush_buffer(step_num=1, step_type=StepType.FINAL_ANSWER)
        assert result is None

    def test_flush_buffer_returns_step_with_content(self):
        """Test that flush_buffer returns AgentStep with accumulated content."""
        from rossum_agent.agent.core import _StreamState
        from rossum_agent.agent.models import StepType

        state = _StreamState()
        state.text_buffer = ["Hello", " ", "world"]
        state.thinking_text = "I'm thinking"

        result = state.flush_buffer(step_num=2, step_type=StepType.INTERMEDIATE)

        assert result is not None
        assert result.step_number == 2
        assert result.text_delta == "Hello world"
        assert result.accumulated_text == "Hello world"
        assert result.thinking == "I'm thinking"
        assert result.step_type == StepType.INTERMEDIATE
        assert result.is_streaming is True

    def test_flush_buffer_clears_buffer(self):
        """Test that flush_buffer clears the text_buffer."""
        from rossum_agent.agent.core import _StreamState
        from rossum_agent.agent.models import StepType

        state = _StreamState()
        state.text_buffer = ["some", "text"]

        state.flush_buffer(step_num=1, step_type=StepType.FINAL_ANSWER)

        assert state.text_buffer == []

    def test_flush_buffer_accumulates_response_text(self):
        """Test that flush_buffer accumulates into response_text."""
        from rossum_agent.agent.core import _StreamState
        from rossum_agent.agent.models import StepType

        state = _StreamState()
        state.response_text = "Previous "
        state.text_buffer = ["new text"]

        result = state.flush_buffer(step_num=1, step_type=StepType.FINAL_ANSWER)

        assert state.response_text == "Previous new text"
        assert result.accumulated_text == "Previous new text"

    def test_flush_buffer_with_empty_thinking(self):
        """Test that thinking is None when thinking_text is empty."""
        from rossum_agent.agent.core import _StreamState
        from rossum_agent.agent.models import StepType

        state = _StreamState()
        state.text_buffer = ["text"]
        state.thinking_text = ""

        result = state.flush_buffer(step_num=1, step_type=StepType.FINAL_ANSWER)

        assert result.thinking is None

    def test_stream_state_initial_values(self):
        """Test _StreamState has correct initial values."""
        from rossum_agent.agent.core import _StreamState

        state = _StreamState()
        assert state.thinking_text == ""
        assert state.response_text == ""
        assert state.final_message is None
        assert state.text_buffer == []
        assert state.tool_calls == []
        assert state.pending_tools == {}
        assert state.first_text_token_time is None
        assert state.initial_buffer_flushed is False

    def test_should_flush_initial_buffer_when_already_flushed(self):
        """Test _should_flush_initial_buffer returns True when already flushed."""
        state = _StreamState()
        state.initial_buffer_flushed = True

        assert state._should_flush_initial_buffer() is True

    def test_should_flush_initial_buffer_when_no_first_token(self):
        """Test _should_flush_initial_buffer returns False when no first token time."""
        state = _StreamState()
        state.first_text_token_time = None

        assert state._should_flush_initial_buffer() is False

    def test_should_flush_initial_buffer_after_delay(self):
        """Test _should_flush_initial_buffer returns True after delay elapsed."""
        state = _StreamState()
        state.first_text_token_time = time.monotonic() - 2.0

        assert state._should_flush_initial_buffer() is True

    def test_should_flush_initial_buffer_before_delay(self):
        """Test _should_flush_initial_buffer returns False before delay elapsed."""
        state = _StreamState()
        state.first_text_token_time = time.monotonic()

        assert state._should_flush_initial_buffer() is False

    def test_get_step_type_with_pending_tools(self):
        """Test get_step_type returns INTERMEDIATE when tools pending."""
        state = _StreamState()
        state.pending_tools = {0: {"name": "test_tool"}}

        assert state.get_step_type() == StepType.INTERMEDIATE

    def test_get_step_type_with_tool_calls(self):
        """Test get_step_type returns INTERMEDIATE when tool_calls exist."""
        state = _StreamState()
        state.tool_calls = [MagicMock()]

        assert state.get_step_type() == StepType.INTERMEDIATE

    def test_get_step_type_final_answer(self):
        """Test get_step_type returns FINAL_ANSWER when no tools."""
        state = _StreamState()

        assert state.get_step_type() == StepType.FINAL_ANSWER

    def test_contains_thinking_returns_true_when_has_thinking(self):
        """Test contains_thinking returns True when thinking_text is non-empty."""
        state = _StreamState()
        state.thinking_text = "Let me analyze this..."

        assert state.contains_thinking is True

    def test_contains_thinking_returns_false_when_empty(self):
        """Test contains_thinking returns False when thinking_text is empty."""
        state = _StreamState()
        state.thinking_text = ""

        assert state.contains_thinking is False

    def test_thinking_block_followed_by_intermediate_step(self):
        """Test that a step with thinking always has content (tool calls or text).

        This verifies the architectural invariant: in a single step, a thinking block
        is always followed by an intermediate block (tool calls or text response).
        """
        state = _StreamState()
        state.thinking_text = "Analyzing the request..."
        state.text_buffer = ["Here is my response"]

        result = state.flush_buffer(step_num=1, step_type=StepType.INTERMEDIATE)

        assert result is not None
        assert result.thinking == "Analyzing the request..."
        assert result.text_delta == "Here is my response"
        assert result.step_type == StepType.INTERMEDIATE

    def test_thinking_block_followed_by_tool_calls(self):
        """Test that thinking can be followed by tool calls in intermediate step."""
        state = _StreamState()
        state.thinking_text = "I need to use a tool..."
        state.tool_calls = [MagicMock()]
        state.pending_tools = {}

        assert state.contains_thinking is True
        assert state.get_step_type() == StepType.INTERMEDIATE

    def test_get_step_type_with_text_and_tool_calls_returns_intermediate(self):
        """Test get_step_type returns INTERMEDIATE when both text and tool calls exist.

        Regression test: When the model produces both text AND tool calls in the same
        response, the step type should be INTERMEDIATE (not FINAL_ANSWER). This ensures
        the stream-end flush correctly classifies the step based on actual state.
        """
        state = _StreamState()
        state.text_buffer = ["Some response text"]
        state.response_text = "Previous text"
        state.tool_calls = [MagicMock()]

        assert state.get_step_type() == StepType.INTERMEDIATE

        result = state.flush_buffer(step_num=2, step_type=state.get_step_type())

        assert result is not None
        assert result.step_type == StepType.INTERMEDIATE
        assert result.text_delta == "Some response text"


class TestPreloadInjection:
    """Test that pre-loaded tool categories are communicated to the agent."""

    def _create_agent(self) -> RossumAgent:
        """Helper to create an agent."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        mock_mcp_connection.get_tools.return_value = []
        config = AgentConfig(max_steps=1)
        return RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test prompt",
            config=config,
        )

    @pytest.mark.asyncio
    async def test_preload_result_injected_into_string_prompt(self):
        """Test that preload result is injected into string prompt."""
        agent = self._create_agent()

        async def mock_stream_response(step_num):
            yield AgentStep(step_number=step_num, final_answer="Done", is_final=True)

        with (
            patch.object(agent, "_stream_model_response", side_effect=mock_stream_response),
            patch("rossum_agent.agent.core.preload_categories_for_request") as mock_preload,
        ):
            mock_preload.return_value = (
                "Loaded 5 tools from ['queues']: list_queues, get_queue, create_queue, update_queue, delete_queue"
            )

            async for _ in agent.run("List all queues"):
                pass

        # Verify the prompt was modified with preload info
        task_step = agent.memory.steps[0]
        assert "[System: Loaded 5 tools" in task_step.task
        assert "Use these tools directly" in task_step.task

    @pytest.mark.asyncio
    async def test_preload_result_injected_into_list_prompt(self):
        """Test that preload result is injected into list content prompt."""
        agent = self._create_agent()

        async def mock_stream_response(step_num):
            yield AgentStep(step_number=step_num, final_answer="Done", is_final=True)

        with (
            patch.object(agent, "_stream_model_response", side_effect=mock_stream_response),
            patch("rossum_agent.agent.core.preload_categories_for_request") as mock_preload,
        ):
            mock_preload.return_value = "Loaded 3 tools from ['schemas']"

            multimodal_prompt = [
                {"type": "text", "text": "Analyze this schema"},
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "abc"}},
            ]
            async for _ in agent.run(multimodal_prompt):
                pass

        task_step = agent.memory.steps[0]
        # For list prompts, should be appended as text block
        assert isinstance(task_step.task, list)
        assert len(task_step.task) == 3  # original 2 + injected text
        assert "[System: Loaded 3 tools" in task_step.task[2]["text"]

    @pytest.mark.asyncio
    async def test_no_injection_when_no_preload(self):
        """Test that prompt is unchanged when preload returns None."""
        agent = self._create_agent()

        async def mock_stream_response(step_num):
            yield AgentStep(step_number=step_num, final_answer="Done", is_final=True)

        with (
            patch.object(agent, "_stream_model_response", side_effect=mock_stream_response),
            patch("rossum_agent.agent.core.preload_categories_for_request") as mock_preload,
        ):
            mock_preload.return_value = None

            async for _ in agent.run("Hello world"):
                pass

        task_step = agent.memory.steps[0]
        assert task_step.task == "Hello world"
        assert "[System:" not in task_step.task


class TestCalculateRateLimitDelay:
    """Tests for RossumAgent._calculate_rate_limit_delay method."""

    def _create_agent(self) -> RossumAgent:
        """Helper to create an agent."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        config = AgentConfig()
        return RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test prompt",
            config=config,
        )

    def test_first_retry_uses_base_delay(self):
        """Test that first retry uses base delay (2.0 seconds)."""
        agent = self._create_agent()

        with patch("rossum_agent.agent.core.random.uniform", return_value=0.0):
            delay = agent._calculate_rate_limit_delay(retries=1)

        # Base delay is 2.0 * (2^0) = 2.0
        assert delay == 2.0

    def test_exponential_backoff(self):
        """Test that delay increases exponentially with retries."""
        agent = self._create_agent()

        with patch("rossum_agent.agent.core.random.uniform", return_value=0.0):
            delay1 = agent._calculate_rate_limit_delay(retries=1)
            delay2 = agent._calculate_rate_limit_delay(retries=2)
            delay3 = agent._calculate_rate_limit_delay(retries=3)

        # 2.0 * 2^0 = 2.0, 2.0 * 2^1 = 4.0, 2.0 * 2^2 = 8.0
        assert delay1 == 2.0
        assert delay2 == 4.0
        assert delay3 == 8.0

    def test_delay_capped_at_max(self):
        """Test that delay is capped at max delay (60 seconds)."""
        agent = self._create_agent()

        with patch("rossum_agent.agent.core.random.uniform", return_value=0.0):
            # Very high retry count should still cap at 60
            delay = agent._calculate_rate_limit_delay(retries=10)

        assert delay == 60.0

    def test_includes_jitter(self):
        """Test that delay includes jitter component."""
        agent = self._create_agent()

        # Mock jitter to be 10% of delay (0.2 for delay of 2.0)
        with patch("rossum_agent.agent.core.random.uniform", return_value=0.2):
            delay = agent._calculate_rate_limit_delay(retries=1)

        # Base delay 2.0 + jitter 0.2 = 2.2
        assert delay == 2.2

    def test_jitter_is_bounded(self):
        """Test that jitter is correctly bounded to 10% of delay."""
        agent = self._create_agent()

        with patch("rossum_agent.agent.core.random.uniform") as mock_uniform:
            mock_uniform.return_value = 0.5
            agent._calculate_rate_limit_delay(retries=2)

            # Should call uniform with (0, delay * 0.1) = (0, 0.4)
            mock_uniform.assert_called_once()
            args = mock_uniform.call_args[0]
            assert args[0] == 0
            assert abs(args[1] - 0.4) < 0.01  # 4.0 * 0.1 = 0.4


class TestRossumAgentProperties:
    """Tests for RossumAgent properties and basic methods."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock RossumAgent."""
        with (
            patch("rossum_agent.agent.core.mcp_tools_to_anthropic_format", return_value=[]),
            patch("rossum_agent.agent.core.get_internal_tools", return_value=[]),
            patch("rossum_agent.agent.core.get_deploy_tools", return_value=[]),
        ):
            mock_client = MagicMock()
            mock_mcp = MagicMock()
            mock_mcp.list_tools.return_value = MagicMock(tools=[])

            agent = RossumAgent(client=mock_client, mcp_connection=mock_mcp, system_prompt="Test prompt", config=None)
            yield agent

    def test_messages_property(self, mock_agent):
        """Test messages property returns conversation messages."""
        result = mock_agent.messages

        assert isinstance(result, list)

    def test_reset_clears_state(self, mock_agent):
        """Test reset clears agent state."""
        mock_agent._total_input_tokens = 100
        mock_agent._total_output_tokens = 50

        mock_agent.reset()

        assert mock_agent._total_input_tokens == 0
        assert mock_agent._total_output_tokens == 0

    def test_add_user_message(self, mock_agent):
        """Test add_user_message adds message to memory."""
        mock_agent.add_user_message("Hello, agent!")

        messages = mock_agent.messages
        assert len(messages) == 1

    def test_add_assistant_message(self, mock_agent):
        """Test add_assistant_message adds message to memory."""
        mock_agent.add_user_message("Hello")
        mock_agent.add_assistant_message("Hi there!")

        messages = mock_agent.messages
        assert len(messages) == 2


class TestRossumAgentTokenTracking:
    """Tests for RossumAgent token usage tracking and breakdown."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock RossumAgent for token tracking tests."""
        with (
            patch("rossum_agent.agent.core.mcp_tools_to_anthropic_format", return_value=[]),
            patch("rossum_agent.agent.core.get_internal_tools", return_value=[]),
            patch("rossum_agent.agent.core.get_deploy_tools", return_value=[]),
        ):
            mock_client = MagicMock()
            mock_mcp = MagicMock()
            mock_mcp.list_tools.return_value = MagicMock(tools=[])

            agent = RossumAgent(client=mock_client, mcp_connection=mock_mcp, system_prompt="Test prompt", config=None)
            yield agent

    def test_initial_token_counters_are_zero(self, mock_agent):
        """Test that all token counters start at zero."""
        assert mock_agent._total_input_tokens == 0
        assert mock_agent._total_output_tokens == 0
        assert mock_agent._main_agent_input_tokens == 0
        assert mock_agent._main_agent_output_tokens == 0
        assert mock_agent._sub_agent_input_tokens == 0
        assert mock_agent._sub_agent_output_tokens == 0
        assert mock_agent._sub_agent_usage == {}

    def test_reset_clears_all_token_counters(self, mock_agent):
        """Test reset clears all token tracking state."""
        mock_agent._total_input_tokens = 1000
        mock_agent._total_output_tokens = 500
        mock_agent._main_agent_input_tokens = 600
        mock_agent._main_agent_output_tokens = 300
        mock_agent._sub_agent_input_tokens = 400
        mock_agent._sub_agent_output_tokens = 200
        mock_agent._sub_agent_usage = {"debug_hook": (400, 200)}

        mock_agent.reset()

        assert mock_agent._total_input_tokens == 0
        assert mock_agent._total_output_tokens == 0
        assert mock_agent._main_agent_input_tokens == 0
        assert mock_agent._main_agent_output_tokens == 0
        assert mock_agent._sub_agent_input_tokens == 0
        assert mock_agent._sub_agent_output_tokens == 0
        assert mock_agent._sub_agent_usage == {}

    def test_get_token_usage_breakdown_with_no_usage(self, mock_agent):
        """Test get_token_usage_breakdown returns zeros when no tokens used."""
        breakdown = mock_agent.get_token_usage_breakdown()

        assert breakdown.total.input_tokens == 0
        assert breakdown.total.output_tokens == 0
        assert breakdown.total.total_tokens == 0
        assert breakdown.main_agent.input_tokens == 0
        assert breakdown.sub_agents.input_tokens == 0
        assert breakdown.sub_agents.by_tool == {}

    def test_get_token_usage_breakdown_with_main_agent_only(self, mock_agent):
        """Test breakdown when only main agent has used tokens."""
        mock_agent._total_input_tokens = 1000
        mock_agent._total_output_tokens = 500
        mock_agent._main_agent_input_tokens = 1000
        mock_agent._main_agent_output_tokens = 500

        breakdown = mock_agent.get_token_usage_breakdown()

        assert breakdown.total.input_tokens == 1000
        assert breakdown.total.output_tokens == 500
        assert breakdown.total.total_tokens == 1500
        assert breakdown.main_agent.input_tokens == 1000
        assert breakdown.main_agent.output_tokens == 500
        assert breakdown.main_agent.total_tokens == 1500
        assert breakdown.sub_agents.total_tokens == 0

    def test_get_token_usage_breakdown_with_sub_agents(self, mock_agent):
        """Test breakdown when sub-agents have been used."""
        mock_agent._total_input_tokens = 3000
        mock_agent._total_output_tokens = 1500
        mock_agent._main_agent_input_tokens = 1000
        mock_agent._main_agent_output_tokens = 500
        mock_agent._sub_agent_input_tokens = 2000
        mock_agent._sub_agent_output_tokens = 1000
        mock_agent._sub_agent_usage = {
            "debug_hook": (1500, 700),
            "patch_schema_with_subagent": (500, 300),
        }

        breakdown = mock_agent.get_token_usage_breakdown()

        assert breakdown.total.total_tokens == 4500
        assert breakdown.main_agent.total_tokens == 1500
        assert breakdown.sub_agents.total_tokens == 3000
        assert breakdown.sub_agents.by_tool["debug_hook"].input_tokens == 1500
        assert breakdown.sub_agents.by_tool["debug_hook"].total_tokens == 2200
        assert breakdown.sub_agents.by_tool["patch_schema_with_subagent"].total_tokens == 800

    def test_accumulate_sub_agent_tokens(self, mock_agent):
        """Test _accumulate_sub_agent_tokens accumulates properly."""
        from rossum_agent.tools import SubAgentTokenUsage

        usage1 = SubAgentTokenUsage(tool_name="debug_hook", input_tokens=100, output_tokens=50, iteration=1)
        mock_agent._accumulate_sub_agent_tokens(usage1)

        assert mock_agent._total_input_tokens == 100
        assert mock_agent._total_output_tokens == 50
        assert mock_agent._sub_agent_input_tokens == 100
        assert mock_agent._sub_agent_output_tokens == 50
        assert mock_agent._sub_agent_usage["debug_hook"] == (100, 50)

        usage2 = SubAgentTokenUsage(tool_name="debug_hook", input_tokens=200, output_tokens=100, iteration=2)
        mock_agent._accumulate_sub_agent_tokens(usage2)

        assert mock_agent._total_input_tokens == 300
        assert mock_agent._total_output_tokens == 150
        assert mock_agent._sub_agent_input_tokens == 300
        assert mock_agent._sub_agent_output_tokens == 150
        assert mock_agent._sub_agent_usage["debug_hook"] == (300, 150)

    def test_accumulate_sub_agent_tokens_multiple_tools(self, mock_agent):
        """Test accumulating tokens from multiple sub-agent tools."""
        from rossum_agent.tools import SubAgentTokenUsage

        usage1 = SubAgentTokenUsage(tool_name="debug_hook", input_tokens=100, output_tokens=50, iteration=1)
        usage2 = SubAgentTokenUsage(
            tool_name="patch_schema_with_subagent", input_tokens=200, output_tokens=100, iteration=1
        )
        mock_agent._accumulate_sub_agent_tokens(usage1)
        mock_agent._accumulate_sub_agent_tokens(usage2)

        assert mock_agent._sub_agent_usage["debug_hook"] == (100, 50)
        assert mock_agent._sub_agent_usage["patch_schema_with_subagent"] == (200, 100)
        assert mock_agent._sub_agent_input_tokens == 300
        assert mock_agent._sub_agent_output_tokens == 150

    def test_log_token_usage_summary(self, mock_agent, caplog):
        """Test log_token_usage_summary logs formatted summary."""
        mock_agent._total_input_tokens = 3000
        mock_agent._total_output_tokens = 1500
        mock_agent._main_agent_input_tokens = 1000
        mock_agent._main_agent_output_tokens = 500
        mock_agent._sub_agent_input_tokens = 2000
        mock_agent._sub_agent_output_tokens = 1000
        mock_agent._sub_agent_usage = {"debug_hook": (2000, 1000)}

        with caplog.at_level(logging.INFO):
            mock_agent.log_token_usage_summary()

        log_output = caplog.text
        assert "TOKEN USAGE SUMMARY" in log_output
        assert "Main Agent" in log_output
        assert "Sub-agents (total)" in log_output
        assert "debug_hook" in log_output
        assert "TOTAL" in log_output
        assert "1,000" in log_output
        assert "3,000" in log_output
