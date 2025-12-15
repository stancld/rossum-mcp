"""Tests for rossum_agent.agent module."""

from __future__ import annotations

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
        assert config.max_tokens == 128000
        assert config.max_steps == 50
        assert config.temperature == 0.0

    def test_custom_values(self):
        """Test custom configuration values."""
        config = AgentConfig(
            max_tokens=4096,
            max_steps=10,
            temperature=0.5,
        )
        assert config.max_tokens == 4096
        assert config.max_steps == 10
        assert config.temperature == 0.5


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
        """Test that tool calls are converted to messages (thinking IS included before tool_use)."""
        step = MemoryStep(
            step_number=1,
            thinking="Let me analyze this...",
            tool_calls=[ToolCall(id="tc1", name="get_data", arguments={"key": "value"})],
            tool_results=[ToolResult(tool_call_id="tc1", name="get_data", content="result data")],
        )

        messages = step.to_messages()

        assert len(messages) == 2
        assert messages[0]["role"] == "assistant"
        # Thinking text is included as first block, then tool_use
        assert len(messages[0]["content"]) == 2
        assert messages[0]["content"][0]["type"] == "text"
        assert messages[0]["content"][0]["text"] == "Let me analyze this..."
        assert messages[0]["content"][1]["type"] == "tool_use"

        assert messages[1]["role"] == "user"
        assert messages[1]["content"][0]["type"] == "tool_result"

    def test_to_messages_with_tool_calls_no_thinking(self):
        """Test that tool calls without thinking only include tool_use blocks."""
        step = MemoryStep(
            step_number=1,
            tool_calls=[ToolCall(id="tc1", name="get_data", arguments={"key": "value"})],
            tool_results=[ToolResult(tool_call_id="tc1", name="get_data", content="result data")],
        )

        messages = step.to_messages()

        assert len(messages) == 2
        assert messages[0]["role"] == "assistant"
        # No thinking, so only tool_use block
        assert len(messages[0]["content"]) == 1
        assert messages[0]["content"][0]["type"] == "tool_use"

        assert messages[1]["role"] == "user"
        assert messages[1]["content"][0]["type"] == "tool_result"

    def test_to_messages_no_tool_calls_returns_empty(self):
        """Test that step without tool calls and no model_output returns empty messages."""
        step = MemoryStep(step_number=1, thinking="Just thinking...")

        messages = step.to_messages()

        assert messages == []

    def test_to_messages_with_model_output(self):
        """Test that final answer steps include model_output as assistant content."""
        step = MemoryStep(step_number=1, model_output="Here is the final answer.")

        messages = step.to_messages()

        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert messages[0]["content"] == "Here is the final answer."


class TestTaskStep:
    """Test TaskStep to_messages conversion."""

    def test_to_messages(self):
        """Test that TaskStep converts to user message."""
        step = TaskStep(task="Help me with this task")

        messages = step.to_messages()

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Help me with this task"


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
        memory.add_step(MemoryStep(step_number=1, thinking="Thinking..."))

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
                thinking="Thinking",
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
                thinking="Thinking",
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
        """Test streaming with both text and tool call."""
        agent = self._create_agent()
        agent.memory.add_task("Help me")
        agent.mcp_connection.call_tool.return_value = "result"

        text_delta = RawContentBlockDeltaEvent(
            type="content_block_delta",
            index=0,
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
            index=1,
            content_block=tool_block,
        )

        tool_delta = RawContentBlockDeltaEvent(
            type="content_block_delta",
            index=1,
            delta=InputJSONDelta(type="input_json_delta", partial_json="{}"),
        )

        tool_stop = ContentBlockStopEvent(
            type="content_block_stop",
            index=1,
        )

        final_message = self._create_final_message()
        mock_stream = self._create_mock_stream([text_delta, tool_start, tool_delta, tool_stop], final_message)

        with patch.object(agent.client.messages, "stream", return_value=mock_stream):
            steps = []
            async for step in agent._stream_model_response(1):
                steps.append(step)

        final_step = steps[-1]
        assert final_step.thinking == "Let me check that for you."
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
    async def test_rate_limit_error_handling(self):
        """Test that RateLimitError is handled gracefully."""
        agent = self._create_agent()

        async def mock_stream_response(step_num):
            raise RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429),
                body=None,
            )
            yield  # Make it a generator

        with patch.object(agent, "_stream_model_response", side_effect=mock_stream_response):
            steps = []
            async for step in agent.run("Test prompt"):
                steps.append(step)

        assert len(steps) == 1
        assert steps[0].is_final is True
        assert "Rate limit" in steps[0].error

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

        mock_execute.assert_called_once_with("write_file", {"filename": "test.txt", "content": "Hello"})
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
