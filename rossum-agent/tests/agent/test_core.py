"""Tests for rossum_agent.agent module."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anthropic import APIError, APITimeoutError, RateLimitError
from rossum_agent.agent import (
    AgentConfig,
    AgentMemory,
    MemoryStep,
    RossumAgent,
    TaskStep,
    ToolCall,
    ToolResult,
    truncate_content,
)
from rossum_agent.agent.core import create_agent
from rossum_agent.agent.models import (
    ErrorStep,
    FinalAnswerStep,
    ThinkingStep,
    ToolResultStep,
    ToolStartStep,
)
from rossum_agent.tools.core import AgentContext, SubAgentTokenUsage, reset_context, set_context
from rossum_agent.utils import add_message_cache_breakpoint


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
        assert config.max_output_tokens == 128000
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


class TestAgentStepTypes:
    """Test AgentStep discriminated union types."""

    def test_tool_result_step_has_tool_calls(self):
        """Test ToolResultStep always has tool_calls."""
        step = ToolResultStep(
            step_number=1,
            tool_calls=[ToolCall(id="1", name="test_tool", arguments={})],
            tool_results=[],
        )
        assert len(step.tool_calls) == 1

    def test_thinking_step_has_no_tool_calls(self):
        """Test ThinkingStep has no tool_calls attribute."""
        step = ThinkingStep(step_number=1, thinking="thought")
        assert not hasattr(step, "tool_calls")


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
        for orig, rest in zip(original_messages, restored_messages, strict=True):
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
        agent.tokens.main_input = 1000
        agent.tokens.main_output = 500

        agent.reset()

        assert agent.memory.steps == []
        assert agent.tokens.total_input == 0
        assert agent.tokens.total_output == 0

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
    async def test_stops_when_final_answer_step(self):
        """Test that run() stops when FinalAnswerStep is yielded."""
        agent = self._create_agent()

        final_step = FinalAnswerStep(step_number=1, final_answer="Done!")

        async def mock_stream_response(step_num):
            yield final_step

        with patch.object(agent, "_stream_model_response", side_effect=mock_stream_response):
            steps = []
            async for step in agent.run("Test prompt"):
                steps.append(step)

        assert len(steps) == 1
        assert isinstance(steps[0], FinalAnswerStep)
        assert steps[0].final_answer == "Done!"

    @pytest.mark.asyncio
    async def test_continues_when_not_final(self):
        """Test that run() continues processing when step is not final."""
        agent = self._create_agent()

        call_count = [0]

        async def mock_stream_response(step_num):
            call_count[0] += 1
            if call_count[0] < 2:
                yield ToolStartStep(
                    step_number=step_num,
                    tool_calls=[ToolCall(id="tc1", name="tool", arguments={})],
                    tool_progress=(0, 1),
                )
                yield ToolResultStep(
                    step_number=step_num,
                    tool_calls=[ToolCall(id="tc1", name="tool", arguments={})],
                    tool_results=[ToolResult(tool_call_id="tc1", name="tool", content="result")],
                )
            else:
                yield FinalAnswerStep(
                    step_number=step_num,
                    final_answer="All done!",
                )

        with (
            patch.object(agent, "_stream_model_response", side_effect=mock_stream_response),
            patch("rossum_agent.agent.core.asyncio.sleep", new_callable=AsyncMock),
        ):
            steps = []
            async for step in agent.run("Test prompt"):
                steps.append(step)

        finalized_steps = [s for s in steps if isinstance(s, (ToolResultStep, FinalAnswerStep, ErrorStep))]
        assert len(finalized_steps) == 2
        assert isinstance(finalized_steps[-1], FinalAnswerStep)

    @pytest.mark.asyncio
    async def test_max_steps_reached(self):
        """Test that run() stops and yields error when max_steps is reached."""
        agent = self._create_agent()

        async def mock_stream_response(step_num):
            yield ToolResultStep(
                step_number=step_num,
                tool_calls=[ToolCall(id="tc1", name="tool", arguments={})],
                tool_results=[ToolResult(tool_call_id="tc1", name="tool", content="result")],
            )

        with (
            patch.object(agent, "_stream_model_response", side_effect=mock_stream_response),
            patch("rossum_agent.agent.core.asyncio.sleep", new_callable=AsyncMock),
        ):
            steps = []
            async for step in agent.run("Test prompt"):
                steps.append(step)

        assert isinstance(steps[-1], ErrorStep)
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

        final_steps = [s for s in steps if isinstance(s, ErrorStep)]
        assert len(final_steps) == 1
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
            yield FinalAnswerStep(step_number=step_num, final_answer="Success!")

        with (
            patch.object(agent, "_stream_model_response", side_effect=mock_stream_response),
            patch("rossum_agent.agent.core.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            steps = []
            async for step in agent.run("Test prompt"):
                steps.append(step)

        assert call_count[0] == 3  # 2 failures + 1 success
        assert mock_sleep.await_count == 2  # Called for each retry wait
        final_steps = [s for s in steps if isinstance(s, FinalAnswerStep)]
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
            yield FinalAnswerStep(step_number=step_num, final_answer="Done")

        with (
            patch.object(agent, "_stream_model_response", side_effect=mock_stream_response),
            patch("rossum_agent.agent.core.asyncio.sleep", new_callable=AsyncMock),
        ):
            steps = []
            async for step in agent.run("Test prompt"):
                steps.append(step)

        thinking_steps = [s for s in steps if isinstance(s, ThinkingStep)]
        assert len(thinking_steps) >= 1
        assert "Rate limited" in thinking_steps[0].thinking
        assert "waiting" in thinking_steps[0].thinking.lower()

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
            yield FinalAnswerStep(step_number=step_num, final_answer="Done")

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
        assert isinstance(steps[0], ErrorStep)
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
        assert isinstance(steps[0], ErrorStep)
        assert "API error" in steps[0].error

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates_instead_of_being_caught(self):
        """Test that CancelledError in run() propagates rather than being caught as a generic Exception."""
        agent = self._create_agent()

        async def mock_stream_response(step_num):
            raise asyncio.CancelledError
            yield  # Make it a generator

        with (
            patch.object(agent, "_stream_model_response", side_effect=mock_stream_response),
            pytest.raises(asyncio.CancelledError),
        ):
            async for _ in agent.run("Test prompt"):
                pass


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
                yield ToolResultStep(
                    step_number=step_num,
                    tool_calls=[ToolCall(id="tc1", name="tool", arguments={})],
                    tool_results=[ToolResult(tool_call_id="tc1", name="tool", content="result")],
                )
            else:
                yield FinalAnswerStep(step_number=step_num, final_answer="Done")

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

    @pytest.mark.asyncio
    async def test_includes_delete_tool_in_read_write_mode(self):
        """Test that the unified delete tool is loaded when not in read-only mode."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        delete_tool = MagicMock()
        delete_tool.name = "delete"
        delete_tool.description = "Delete an entity"
        delete_tool.inputSchema = {"type": "object", "properties": {}}
        mock_mcp_connection.get_tools.return_value = [delete_tool]

        agent = RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test",
        )

        token = set_context(AgentContext(mcp_mode="read-write"))
        try:
            tools = await agent._get_tools()
        finally:
            reset_context(token)

        tool_names = [t.get("name") for t in tools if isinstance(t, dict)]
        assert "delete" in tool_names

    @pytest.mark.asyncio
    async def test_excludes_delete_tool_in_read_only_mode(self):
        """Test that the unified delete tool is NOT loaded in read-only mode."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        delete_tool = MagicMock()
        delete_tool.name = "delete"
        delete_tool.description = "Delete an entity"
        delete_tool.inputSchema = {"type": "object", "properties": {}}
        mock_mcp_connection.get_tools.return_value = [delete_tool]

        agent = RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test",
        )

        token = set_context(AgentContext(mcp_mode="read-only"))
        try:
            tools = await agent._get_tools()
        finally:
            reset_context(token)

        tool_names = [t.get("name") for t in tools if isinstance(t, dict)]
        assert "delete" not in tool_names


class TestCreateAgentFactory:
    """Test create_agent factory function."""

    @pytest.mark.asyncio
    async def test_creates_agent_with_default_config(self):
        """Test that create_agent creates an agent with proper setup."""

        mock_mcp = AsyncMock()

        with patch("rossum_agent.agent.core.create_async_bedrock_client") as mock_create_client:
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

        mock_mcp = AsyncMock()
        config = AgentConfig(max_steps=10)

        with patch("rossum_agent.agent.core.create_async_bedrock_client") as mock_create_client:
            mock_create_client.return_value = MagicMock()

            agent = await create_agent(
                mcp_connection=mock_mcp,
                system_prompt="Test",
                config=config,
            )

        assert agent.config.max_steps == 10
        assert agent.config.temperature == 1.0  # Must be 1.0 for extended thinking


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
            yield FinalAnswerStep(step_number=step_num, final_answer="Done")

        with (
            patch.object(agent, "_stream_model_response", side_effect=mock_stream_response),
            patch("rossum_agent.agent.core.preload_categories_for_request") as mock_preload,
        ):
            mock_preload.return_value = (
                "Loaded 5 tools from ['queues']: list_queues, get_queue, create_queue, update_queue, delete_queue"
            )

            async for _ in agent.run("List all queues"):
                pass

        # Task text stays clean; preload info stored separately
        task_step = agent.memory.steps[0]
        assert task_step.task == "List all queues"
        assert task_step.preload_info == (
            "Loaded 5 tools from ['queues']: list_queues, get_queue, create_queue, update_queue, delete_queue"
        )

        # But messages sent to API still include the system info
        messages = task_step.to_messages()
        assert "[System: Loaded 5 tools" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_preload_result_injected_into_list_prompt(self):
        """Test that preload result is stored separately for list content prompt."""
        agent = self._create_agent()

        async def mock_stream_response(step_num):
            yield FinalAnswerStep(step_number=step_num, final_answer="Done")

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
        # Task stays clean — only the original 2 blocks
        assert isinstance(task_step.task, list)
        assert len(task_step.task) == 2
        assert task_step.preload_info == "Loaded 3 tools from ['schemas']"

        # Messages for API include the injected text block
        messages = task_step.to_messages()
        msg_content = messages[0]["content"]
        assert len(msg_content) == 3
        assert "[System: Loaded 3 tools" in msg_content[2]["text"]

    @pytest.mark.asyncio
    async def test_no_injection_when_no_preload(self):
        """Test that prompt is unchanged when preload returns None."""
        agent = self._create_agent()

        async def mock_stream_response(step_num):
            yield FinalAnswerStep(step_number=step_num, final_answer="Done")

        with (
            patch.object(agent, "_stream_model_response", side_effect=mock_stream_response),
            patch("rossum_agent.agent.core.preload_categories_for_request") as mock_preload,
        ):
            mock_preload.return_value = None

            async for _ in agent.run("Hello world"):
                pass

        task_step = agent.memory.steps[0]
        assert task_step.task == "Hello world"
        assert task_step.preload_info is None


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
        mock_agent.tokens.main_input = 100
        mock_agent.tokens.main_output = 50

        mock_agent.reset()

        assert mock_agent.tokens.total_input == 0
        assert mock_agent.tokens.total_output == 0

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
        ):
            mock_client = MagicMock()
            mock_mcp = MagicMock()
            mock_mcp.list_tools.return_value = MagicMock(tools=[])

            agent = RossumAgent(client=mock_client, mcp_connection=mock_mcp, system_prompt="Test prompt", config=None)
            yield agent

    def test_initial_token_counters_are_zero(self, mock_agent):
        """Test that all token counters start at zero."""
        assert mock_agent.tokens.total_input == 0
        assert mock_agent.tokens.total_output == 0
        assert mock_agent.tokens.main_input == 0
        assert mock_agent.tokens.main_output == 0
        assert mock_agent.tokens.sub_input == 0
        assert mock_agent.tokens.sub_output == 0
        assert mock_agent.tokens.sub_by_tool == {}
        assert mock_agent.tokens.last_main_input == 0

    def test_reset_clears_all_token_counters(self, mock_agent):
        """Test reset clears all token tracking state."""
        mock_agent.tokens.main_input = 600
        mock_agent.tokens.main_output = 300
        mock_agent.tokens.sub_input = 400
        mock_agent.tokens.sub_output = 200
        mock_agent.tokens.sub_by_tool = {"search_knowledge_base": (400, 200)}
        mock_agent.tokens.last_main_input = 600

        mock_agent.reset()

        assert mock_agent.tokens.total_input == 0
        assert mock_agent.tokens.total_output == 0
        assert mock_agent.tokens.main_input == 0
        assert mock_agent.tokens.main_output == 0
        assert mock_agent.tokens.sub_input == 0
        assert mock_agent.tokens.sub_output == 0
        assert mock_agent.tokens.sub_by_tool == {}
        assert mock_agent.tokens.last_main_input == 0

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
        mock_agent.tokens.main_input = 1000
        mock_agent.tokens.main_output = 500

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
        mock_agent.tokens.main_input = 1000
        mock_agent.tokens.main_output = 500
        mock_agent.tokens.sub_input = 2000
        mock_agent.tokens.sub_output = 1000
        mock_agent.tokens.sub_by_tool = {
            "search_knowledge_base": (1500, 700),
            "patch_schema_with_subagent": (500, 300),
        }

        breakdown = mock_agent.get_token_usage_breakdown()

        assert breakdown.total.total_tokens == 4500
        assert breakdown.main_agent.total_tokens == 1500
        assert breakdown.sub_agents.total_tokens == 3000
        assert breakdown.sub_agents.by_tool["search_knowledge_base"].input_tokens == 1500
        assert breakdown.sub_agents.by_tool["search_knowledge_base"].total_tokens == 2200
        assert breakdown.sub_agents.by_tool["patch_schema_with_subagent"].total_tokens == 800

    def test_accumulate_main_tracks_last_input(self, mock_agent):
        """Test accumulate_main accumulates totals and tracks last_main_input."""
        mock_agent.tokens.accumulate_main(input_tokens=500, output_tokens=200, cache_creation=10, cache_read=50)

        assert mock_agent.tokens.main_input == 500
        assert mock_agent.tokens.main_output == 200
        assert mock_agent.tokens.last_main_input == 500

        mock_agent.tokens.accumulate_main(input_tokens=800, output_tokens=300, cache_creation=20, cache_read=100)

        assert mock_agent.tokens.main_input == 1300
        assert mock_agent.tokens.main_output == 500
        assert mock_agent.tokens.last_main_input == 800

    def test_accumulate_sub_agent_tokens(self, mock_agent):
        """Test tokens.accumulate_sub accumulates properly."""

        usage1 = SubAgentTokenUsage(tool_name="search_knowledge_base", input_tokens=100, output_tokens=50, iteration=1)
        mock_agent.tokens.accumulate_sub(usage1)

        assert mock_agent.tokens.total_input == 100
        assert mock_agent.tokens.total_output == 50
        assert mock_agent.tokens.sub_input == 100
        assert mock_agent.tokens.sub_output == 50
        assert mock_agent.tokens.sub_by_tool["search_knowledge_base"] == (100, 50)

        usage2 = SubAgentTokenUsage(
            tool_name="search_knowledge_base", input_tokens=200, output_tokens=100, iteration=2
        )
        mock_agent.tokens.accumulate_sub(usage2)

        assert mock_agent.tokens.total_input == 300
        assert mock_agent.tokens.total_output == 150
        assert mock_agent.tokens.sub_input == 300
        assert mock_agent.tokens.sub_output == 150
        assert mock_agent.tokens.sub_by_tool["search_knowledge_base"] == (300, 150)

    def test_accumulate_sub_agent_tokens_multiple_tools(self, mock_agent):
        """Test accumulating tokens from multiple sub-agent tools."""

        usage1 = SubAgentTokenUsage(tool_name="search_knowledge_base", input_tokens=100, output_tokens=50, iteration=1)
        usage2 = SubAgentTokenUsage(
            tool_name="patch_schema_with_subagent", input_tokens=200, output_tokens=100, iteration=1
        )
        mock_agent.tokens.accumulate_sub(usage1)
        mock_agent.tokens.accumulate_sub(usage2)

        assert mock_agent.tokens.sub_by_tool["search_knowledge_base"] == (100, 50)
        assert mock_agent.tokens.sub_by_tool["patch_schema_with_subagent"] == (200, 100)
        assert mock_agent.tokens.sub_input == 300
        assert mock_agent.tokens.sub_output == 150

    def test_log_token_usage_summary(self, mock_agent, caplog):
        """Test log_token_usage_summary logs formatted summary."""
        mock_agent.tokens.main_input = 1000
        mock_agent.tokens.main_output = 500
        mock_agent.tokens.sub_input = 2000
        mock_agent.tokens.sub_output = 1000
        mock_agent.tokens.sub_by_tool = {"search_knowledge_base": (2000, 1000)}

        with caplog.at_level(logging.INFO):
            mock_agent.log_token_usage_summary()

        log_output = caplog.text
        assert "TOKEN USAGE SUMMARY" in log_output
        assert "Main Agent" in log_output
        assert "Sub-agents (total)" in log_output
        assert "search_knowledge_base" in log_output
        assert "TOTAL" in log_output
        assert "1,000" in log_output
        assert "3,000" in log_output

    def test_initial_cache_counters_are_zero(self, mock_agent):
        """Test that all cache token counters start at zero."""
        assert mock_agent.tokens.total_cache_creation == 0
        assert mock_agent.tokens.total_cache_read == 0
        assert mock_agent.tokens.main_cache_creation == 0
        assert mock_agent.tokens.main_cache_read == 0
        assert mock_agent.tokens.sub_cache_creation == 0
        assert mock_agent.tokens.sub_cache_read == 0
        assert mock_agent.tokens.sub_cache_by_tool == {}

    def test_reset_clears_cache_counters(self, mock_agent):
        """Test reset clears all cache token tracking state."""
        mock_agent.tokens.main_cache_creation = 300
        mock_agent.tokens.main_cache_read = 600
        mock_agent.tokens.sub_cache_creation = 200
        mock_agent.tokens.sub_cache_read = 400
        mock_agent.tokens.sub_cache_by_tool = {"search_knowledge_base": (200, 400)}

        mock_agent.reset()

        assert mock_agent.tokens.total_cache_creation == 0
        assert mock_agent.tokens.total_cache_read == 0
        assert mock_agent.tokens.main_cache_creation == 0
        assert mock_agent.tokens.main_cache_read == 0
        assert mock_agent.tokens.sub_cache_creation == 0
        assert mock_agent.tokens.sub_cache_read == 0
        assert mock_agent.tokens.sub_cache_by_tool == {}

    def test_accumulate_sub_agent_cache_tokens(self, mock_agent):
        """Test tokens.accumulate_sub accumulates cache metrics."""

        usage = SubAgentTokenUsage(
            tool_name="search_knowledge_base",
            input_tokens=100,
            output_tokens=50,
            iteration=1,
            cache_creation_input_tokens=30,
            cache_read_input_tokens=60,
        )
        mock_agent.tokens.accumulate_sub(usage)

        assert mock_agent.tokens.total_cache_creation == 30
        assert mock_agent.tokens.total_cache_read == 60
        assert mock_agent.tokens.sub_cache_creation == 30
        assert mock_agent.tokens.sub_cache_read == 60
        assert mock_agent.tokens.sub_cache_by_tool["search_knowledge_base"] == (30, 60)

    def test_get_token_usage_breakdown_includes_cache(self, mock_agent):
        """Test that breakdown includes cache metrics."""
        mock_agent.tokens.main_input = 1000
        mock_agent.tokens.main_output = 500
        mock_agent.tokens.main_cache_creation = 100
        mock_agent.tokens.main_cache_read = 800

        breakdown = mock_agent.get_token_usage_breakdown()

        assert breakdown.total.cache_creation_input_tokens == 100
        assert breakdown.total.cache_read_input_tokens == 800
        assert breakdown.main_agent.cache_creation_input_tokens == 100
        assert breakdown.main_agent.cache_read_input_tokens == 800


class TestCacheBreakpoints:
    """Test cache breakpoint injection in _sync_stream_events and _add_message_cache_breakpoint."""

    def test_add_message_cache_breakpoint_to_string_content(self):
        """Test cache breakpoint converts string content to list with cache_control."""
        messages = [{"role": "user", "content": "Hello"}]
        add_message_cache_breakpoint(messages)

        assert isinstance(messages[0]["content"], list)
        assert messages[0]["content"][0]["type"] == "text"
        assert messages[0]["content"][0]["text"] == "Hello"
        assert messages[0]["content"][0]["cache_control"] == {"type": "ephemeral"}

    def test_add_message_cache_breakpoint_to_list_content(self):
        """Test cache breakpoint adds cache_control to last block in list."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "First"},
                    {"type": "text", "text": "Second"},
                ],
            }
        ]
        add_message_cache_breakpoint(messages)

        assert "cache_control" not in messages[0]["content"][0]
        assert messages[0]["content"][1]["cache_control"] == {"type": "ephemeral"}

    def test_add_message_cache_breakpoint_empty_messages(self):
        """Test cache breakpoint handles empty message list."""
        messages = []
        add_message_cache_breakpoint(messages)
        assert messages == []

    def test_add_message_cache_breakpoint_tool_result_content(self):
        """Test cache breakpoint on message with tool_result content."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tc1", "content": "result"},
                ],
            }
        ]
        add_message_cache_breakpoint(messages)

        assert messages[0]["content"][0]["cache_control"] == {"type": "ephemeral"}

    def test_add_message_cache_breakpoint_removes_previous(self):
        """Test that previous cache_control breakpoints are removed before adding new one.

        This prevents exceeding Anthropic's 4-breakpoint limit during iterative tool use.
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "First", "cache_control": {"type": "ephemeral"}},
                ],
            },
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "tc1", "name": "tool", "input": {}}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tc1",
                        "content": "result1",
                        "cache_control": {"type": "ephemeral"},
                    },
                ],
            },
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "tc2", "name": "tool", "input": {}}],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tc2", "content": "result2"},
                ],
            },
        ]
        add_message_cache_breakpoint(messages)

        # Previous breakpoints should be removed
        assert "cache_control" not in messages[0]["content"][0]
        assert "cache_control" not in messages[2]["content"][0]
        # Only last message should have cache_control
        assert messages[4]["content"][0]["cache_control"] == {"type": "ephemeral"}
