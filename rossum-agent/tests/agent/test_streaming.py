"""Tests for rossum_agent.agent.streaming module."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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
from rossum_agent.agent import AgentConfig, RossumAgent, ToolCall
from rossum_agent.agent.models import (
    FinalAnswerStep,
    StepType,
    TextDeltaStep,
    ThinkingStep,
    ToolResultStep,
)
from rossum_agent.agent.streaming import StreamState, process_stream_event


class TestProcessStreamEvent:
    """Test RossumAgent._process_stream_event method directly."""

    def test_content_block_start_event_for_tool_use(self):
        """Test processing ContentBlockStartEvent for tool use."""
        pending_tools: dict[int, dict[str, str]] = {}
        tool_calls: list[ToolCall] = []

        tool_block = ToolUseBlock(type="tool_use", id="tool_123", name="test_tool", input={})
        event = RawContentBlockStartEvent(type="content_block_start", index=0, content_block=tool_block)

        delta = process_stream_event(event, pending_tools, tool_calls)

        assert delta is None
        assert 0 in pending_tools
        assert pending_tools[0]["name"] == "test_tool"
        assert pending_tools[0]["id"] == "tool_123"

    def test_content_block_delta_event_for_text(self):
        """Test processing ContentBlockDeltaEvent for text."""
        pending_tools: dict[int, dict[str, str]] = {}
        tool_calls: list[ToolCall] = []

        event = RawContentBlockDeltaEvent(
            type="content_block_delta", index=0, delta=TextDelta(type="text_delta", text="Hello world")
        )

        delta = process_stream_event(event, pending_tools, tool_calls)

        assert delta is not None
        assert delta.kind == "text"
        assert delta.content == "Hello world"

    def test_content_block_delta_event_for_json(self):
        """Test processing ContentBlockDeltaEvent for JSON input."""
        pending_tools: dict[int, dict[str, str]] = {0: {"name": "tool", "id": "t1", "json": ""}}
        tool_calls: list[ToolCall] = []

        event = RawContentBlockDeltaEvent(
            type="content_block_delta", index=0, delta=InputJSONDelta(type="input_json_delta", partial_json='{"key":')
        )

        delta = process_stream_event(event, pending_tools, tool_calls)

        assert delta is None
        assert pending_tools[0]["json"] == '{"key":'

    def test_content_block_stop_event_with_empty_json(self):
        """Test processing ContentBlockStopEvent with empty JSON."""
        pending_tools: dict[int, dict[str, str]] = {0: {"name": "tool", "id": "t1", "json": ""}}
        tool_calls: list[ToolCall] = []

        event = ContentBlockStopEvent(type="content_block_stop", index=0)

        delta = process_stream_event(event, pending_tools, tool_calls)

        assert delta is None
        assert len(tool_calls) == 1
        assert tool_calls[0].arguments == {}

    def test_unhandled_event_returns_none(self):
        """Test that unhandled events return None."""
        pending_tools: dict[int, dict[str, str]] = {}
        tool_calls: list[ToolCall] = []

        event = MagicMock()

        delta = process_stream_event(event, pending_tools, tool_calls)

        assert delta is None

    def test_content_block_start_event_for_thinking(self):
        """Test processing ContentBlockStartEvent for thinking block returns None."""
        from anthropic.types import ThinkingBlock

        pending_tools: dict[int, dict[str, str]] = {}
        tool_calls: list[ToolCall] = []

        thinking_block = ThinkingBlock(type="thinking", thinking="", signature="sig")
        event = RawContentBlockStartEvent(type="content_block_start", index=0, content_block=thinking_block)

        delta = process_stream_event(event, pending_tools, tool_calls)

        assert delta is None

    def test_content_block_delta_event_for_thinking(self):
        """Test processing ContentBlockDeltaEvent for thinking delta."""
        from anthropic.types import ThinkingDelta

        pending_tools: dict[int, dict[str, str]] = {}
        tool_calls: list[ToolCall] = []

        event = RawContentBlockDeltaEvent(
            type="content_block_delta", index=0, delta=ThinkingDelta(type="thinking_delta", thinking="Let me think...")
        )

        delta = process_stream_event(event, pending_tools, tool_calls)

        assert delta is not None
        assert delta.kind == "thinking"
        assert delta.content == "Let me think..."


class TestStreamState:
    """Test StreamState class."""

    def test_flush_buffer_returns_none_when_empty(self):
        """Test that flush_buffer returns None when buffer is empty."""
        state = StreamState()
        result = state.flush_buffer(step_num=1, step_type=StepType.FINAL_ANSWER)
        assert result is None

    def test_flush_buffer_returns_step_with_content(self):
        """Test that flush_buffer returns TextDeltaStep with accumulated content."""
        state = StreamState()
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
        state = StreamState()
        state.text_buffer = ["some", "text"]

        state.flush_buffer(step_num=1, step_type=StepType.FINAL_ANSWER)

        assert state.text_buffer == []

    def test_flush_buffer_accumulates_response_text(self):
        """Test that flush_buffer accumulates into response_text."""
        state = StreamState()
        state.response_text = "Previous "
        state.text_buffer = ["new text"]

        result = state.flush_buffer(step_num=1, step_type=StepType.FINAL_ANSWER)

        assert state.response_text == "Previous new text"
        assert result.accumulated_text == "Previous new text"

    def test_flush_buffer_with_empty_thinking(self):
        """Test that thinking is None when thinking_text is empty."""
        state = StreamState()
        state.text_buffer = ["text"]
        state.thinking_text = ""

        result = state.flush_buffer(step_num=1, step_type=StepType.FINAL_ANSWER)

        assert result.thinking is None

    def test_stream_state_initial_values(self):
        """Test StreamState has correct initial values."""
        state = StreamState()
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
        state = StreamState()
        state.initial_buffer_flushed = True

        assert state._should_flush_initial_buffer() is True

    def test_should_flush_initial_buffer_when_no_first_token(self):
        """Test _should_flush_initial_buffer returns False when no first token time."""
        state = StreamState()
        state.first_text_token_time = None

        assert state._should_flush_initial_buffer() is False

    def test_should_flush_initial_buffer_after_delay(self):
        """Test _should_flush_initial_buffer returns True after delay elapsed."""
        state = StreamState()
        state.first_text_token_time = time.monotonic() - 2.0

        assert state._should_flush_initial_buffer() is True

    def test_should_flush_initial_buffer_before_delay(self):
        """Test _should_flush_initial_buffer returns False before delay elapsed."""
        state = StreamState()
        state.first_text_token_time = time.monotonic()

        assert state._should_flush_initial_buffer() is False

    def test_get_step_type_with_pending_tools(self):
        """Test get_step_type returns INTERMEDIATE when tools pending."""
        state = StreamState()
        state.pending_tools = {0: {"name": "test_tool"}}

        assert state.get_step_type(step_num=2) == StepType.INTERMEDIATE

    def test_get_step_type_with_tool_calls(self):
        """Test get_step_type returns INTERMEDIATE when tool_calls exist."""
        state = StreamState()
        state.tool_calls = [MagicMock()]

        assert state.get_step_type(step_num=2) == StepType.INTERMEDIATE

    def test_get_step_type_final_answer(self):
        """Test get_step_type returns FINAL_ANSWER when no tools on non-first step."""
        state = StreamState()

        assert state.get_step_type(step_num=2) == StepType.FINAL_ANSWER

    def test_get_step_type_first_step_defaults_to_intermediate(self):
        """Test get_step_type returns INTERMEDIATE on step 1 even without tools."""
        state = StreamState()

        assert state.get_step_type(step_num=1) == StepType.INTERMEDIATE

    def test_thinking_block_followed_by_intermediate_step(self):
        """Test that a step with thinking always has content (tool calls or text).

        This verifies the architectural invariant: in a single step, a thinking block
        is always followed by an intermediate block (tool calls or text response).
        """
        state = StreamState()
        state.thinking_text = "Analyzing the request..."
        state.text_buffer = ["Here is my response"]

        result = state.flush_buffer(step_num=1, step_type=StepType.INTERMEDIATE)

        assert result is not None
        assert result.thinking == "Analyzing the request..."
        assert result.text_delta == "Here is my response"
        assert result.step_type == StepType.INTERMEDIATE

    def test_thinking_block_followed_by_tool_calls(self):
        """Test that thinking can be followed by tool calls in intermediate step."""
        state = StreamState()
        state.thinking_text = "I need to use a tool..."
        state.tool_calls = [MagicMock()]
        state.pending_tools = {}

        assert state.get_step_type(step_num=2) == StepType.INTERMEDIATE

    def test_get_step_type_with_text_and_tool_calls_returns_intermediate(self):
        """Test get_step_type returns INTERMEDIATE when both text and tool calls exist.

        Regression test: When the model produces both text AND tool calls in the same
        response, the step type should be INTERMEDIATE (not FINAL_ANSWER). This ensures
        the stream-end flush correctly classifies the step based on actual state.
        """
        state = StreamState()
        state.text_buffer = ["Some response text"]
        state.response_text = "Previous text"
        state.tool_calls = [MagicMock()]

        assert state.get_step_type(step_num=2) == StepType.INTERMEDIATE

        result = state.flush_buffer(step_num=2, step_type=state.get_step_type(step_num=2))

        assert result is not None
        assert result.step_type == StepType.INTERMEDIATE
        assert result.text_delta == "Some response text"

    def test_finalize_thinking_returns_step_on_first_call(self):
        """Test that finalize_thinking returns a ThinkingStep on first call."""
        state = StreamState()
        state.thinking_text = "Let me think about this..."

        result = state.finalize_thinking(step_num=1)

        assert result is not None
        assert result.step_number == 1
        assert result.thinking == "Let me think about this..."
        assert result.is_streaming is False
        assert state.thinking_finalized is True

    def test_finalize_thinking_returns_none_on_second_call(self):
        """Test that finalize_thinking returns None when already finalized."""
        state = StreamState()
        state.thinking_text = "Let me think about this..."

        state.finalize_thinking(step_num=1)
        result = state.finalize_thinking(step_num=1)

        assert result is None

    def test_finalize_thinking_returns_none_when_no_thinking(self):
        """Test that finalize_thinking returns None when no thinking text."""
        state = StreamState()

        result = state.finalize_thinking(step_num=1)

        assert result is None
        assert state.thinking_finalized is False


class TestExtractThinkingBlocks:
    """Test extract_thinking_blocks function."""

    def test_extracts_thinking_blocks_from_message(self):
        """Thinking blocks are extracted with their signatures."""
        from anthropic.types import TextBlock, ThinkingBlock
        from rossum_agent.agent.streaming import extract_thinking_blocks

        message = MagicMock()
        message.content = [
            ThinkingBlock(type="thinking", thinking="Step 1 reasoning", signature="sig_1"),
            TextBlock(type="text", text="Answer text"),
            ThinkingBlock(type="thinking", thinking="Step 2 reasoning", signature="sig_2"),
        ]

        result = extract_thinking_blocks(message)

        assert len(result) == 2
        assert result[0].thinking == "Step 1 reasoning"
        assert result[0].signature == "sig_1"
        assert result[1].thinking == "Step 2 reasoning"
        assert result[1].signature == "sig_2"

    def test_returns_empty_list_when_no_thinking_blocks(self):
        """Returns empty list when message has no thinking blocks."""
        from anthropic.types import TextBlock
        from rossum_agent.agent.streaming import extract_thinking_blocks

        message = MagicMock()
        message.content = [TextBlock(type="text", text="Just text")]

        result = extract_thinking_blocks(message)

        assert result == []

    def test_returns_empty_list_for_empty_content(self):
        """Returns empty list when message content is empty."""
        from rossum_agent.agent.streaming import extract_thinking_blocks

        message = MagicMock()
        message.content = []

        result = extract_thinking_blocks(message)

        assert result == []


class TestHandleTextDelta:
    """Test handle_text_delta function."""

    def test_sets_first_text_token_time(self):
        """First call sets first_text_token_time."""
        from rossum_agent.agent.streaming import handle_text_delta

        state = StreamState()
        assert state.first_text_token_time is None

        handle_text_delta(step_num=1, content="Hello", state=state)

        assert state.first_text_token_time is not None

    def test_buffers_text_before_initial_flush(self):
        """Text is buffered and not flushed before initial buffer delay."""
        from rossum_agent.agent.streaming import handle_text_delta

        state = StreamState()

        result = handle_text_delta(step_num=1, content="Hello", state=state)

        assert result is None
        assert state.text_buffer == ["Hello"]

    def test_flushes_immediately_after_buffer_period(self):
        """Text is flushed immediately once initial buffer period elapsed."""
        from rossum_agent.agent.streaming import handle_text_delta

        state = StreamState()
        state.first_text_token_time = time.monotonic() - 2.0  # Well past delay
        state.initial_buffer_flushed = False

        result = handle_text_delta(step_num=2, content="World", state=state)

        assert state.initial_buffer_flushed is True
        assert result is not None
        assert result.text_delta == "World"

    def test_flushes_immediately_when_tool_calls_present(self):
        """Text flushes immediately when tool_calls are detected."""
        from rossum_agent.agent.streaming import handle_text_delta

        state = StreamState()
        state.tool_calls = [MagicMock()]

        result = handle_text_delta(step_num=1, content="Before tool", state=state)

        assert state.initial_buffer_flushed is True
        assert result is not None
        assert result.step_type == StepType.INTERMEDIATE

    def test_flushes_immediately_when_pending_tools_present(self):
        """Text flushes immediately when pending_tools are detected."""
        from rossum_agent.agent.streaming import handle_text_delta

        state = StreamState()
        state.pending_tools = {0: {"name": "test_tool"}}

        result = handle_text_delta(step_num=1, content="Before tool", state=state)

        assert state.initial_buffer_flushed is True
        assert result is not None
        assert result.step_type == StepType.INTERMEDIATE


class TestHandleTextDeltaWithFinalization:
    """Test handle_text_delta_with_finalization function."""

    def test_returns_both_thinking_and_text_steps(self):
        """Finalizes thinking and handles text delta, returning both steps."""
        from rossum_agent.agent.streaming import handle_text_delta_with_finalization

        state = StreamState()
        state.thinking_text = "I should respond"
        state.initial_buffer_flushed = True

        steps = handle_text_delta_with_finalization(step_num=2, content="Answer", state=state)

        assert len(steps) == 2
        assert isinstance(steps[0], ThinkingStep)
        assert steps[0].is_streaming is False
        assert isinstance(steps[1], TextDeltaStep)
        assert steps[1].text_delta == "Answer"

    def test_returns_only_text_when_no_thinking(self):
        """Returns only text step when there's no thinking to finalize."""
        from rossum_agent.agent.streaming import handle_text_delta_with_finalization

        state = StreamState()
        state.initial_buffer_flushed = True

        steps = handle_text_delta_with_finalization(step_num=2, content="Answer", state=state)

        assert len(steps) == 1
        assert isinstance(steps[0], TextDeltaStep)

    def test_returns_empty_when_buffering(self):
        """Returns empty list when text is still buffering and no thinking."""
        from rossum_agent.agent.streaming import handle_text_delta_with_finalization

        state = StreamState()

        steps = handle_text_delta_with_finalization(step_num=1, content="Hello", state=state)

        assert len(steps) == 0
        assert state.text_buffer == ["Hello"]

    def test_does_not_finalize_thinking_twice(self):
        """Second call doesn't produce another ThinkingStep."""
        from rossum_agent.agent.streaming import handle_text_delta_with_finalization

        state = StreamState()
        state.thinking_text = "Reasoning"
        state.initial_buffer_flushed = True

        steps1 = handle_text_delta_with_finalization(step_num=2, content="First", state=state)
        steps2 = handle_text_delta_with_finalization(step_num=2, content="Second", state=state)

        thinking_steps = [s for s in steps1 + steps2 if isinstance(s, ThinkingStep)]
        assert len(thinking_steps) == 1


class TestMaybeLogProgress:
    """Test StreamState.maybe_log_progress."""

    def test_logs_after_interval(self):
        """Logs progress when enough time has elapsed."""
        state = StreamState()
        state.last_progress_log_time = time.monotonic() - 15.0
        state.thinking_text = "thinking..."
        state.text_deltas = 0

        with patch("rossum_agent.agent.streaming.logger") as mock_logger:
            state.maybe_log_progress(step_num=1)
            mock_logger.info.assert_called_once()
            log_msg = mock_logger.info.call_args[0][0]
            assert "Step 1" in log_msg
            assert "thinking" in log_msg

    def test_does_not_log_before_interval(self):
        """Does not log when interval hasn't elapsed."""
        state = StreamState()
        state.last_progress_log_time = time.monotonic()

        with patch("rossum_agent.agent.streaming.logger") as mock_logger:
            state.maybe_log_progress(step_num=1)
            mock_logger.info.assert_not_called()

    def test_logs_text_phase_when_text_deltas_exist(self):
        """Reports 'text' phase when text_deltas > 0."""
        state = StreamState()
        state.last_progress_log_time = time.monotonic() - 15.0
        state.text_deltas = 5
        state.response_text = "some text"

        with patch("rossum_agent.agent.streaming.logger") as mock_logger:
            state.maybe_log_progress(step_num=2)
            log_msg = mock_logger.info.call_args[0][0]
            assert "text" in log_msg

    def test_updates_last_progress_log_time(self):
        """Updates last_progress_log_time after logging."""
        state = StreamState()
        old_time = time.monotonic() - 15.0
        state.last_progress_log_time = old_time

        with patch("rossum_agent.agent.streaming.logger"):
            state.maybe_log_progress(step_num=1)

        assert state.last_progress_log_time > old_time


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
        """Create a mock async stream context manager that yields events."""

        class _AsyncStream:
            def __init__(self):
                self._iter = iter(events)
                self._final_message = final_message

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return next(self._iter)
                except StopIteration:
                    raise StopAsyncIteration from None

            async def get_final_message(self):
                return self._final_message

        return _AsyncStream()

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
        assert isinstance(final_step, FinalAnswerStep)
        assert final_step.final_answer == "Hello, how can I help you?"
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
        assert isinstance(final_step, ToolResultStep)
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
        assert isinstance(final_step, ToolResultStep)
        assert len(final_step.tool_calls) == 1
        # Thinking is yielded as a separate ThinkingStep earlier in the stream
        thinking_steps = [s for s in steps if isinstance(s, ThinkingStep)]
        assert len(thinking_steps) >= 1
        assert "Let me analyze this..." in thinking_steps[-1].thinking

    @pytest.mark.asyncio
    async def test_stream_exception_propagates(self):
        """Exceptions raised during async streaming propagate to the caller."""
        agent = self._create_agent()
        agent.memory.add_task("Test")

        error = ValueError("Stream failed mid-response")
        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)
        mock_stream.__aiter__ = MagicMock(return_value=mock_stream)
        mock_stream.__anext__ = AsyncMock(side_effect=error)

        with (
            patch.object(agent.client.messages, "stream", return_value=mock_stream),
            pytest.raises(ValueError, match="Stream failed mid-response"),
        ):
            async for _ in agent._stream_model_response(1):
                pass

    @pytest.mark.asyncio
    async def test_thinking_delta_does_not_start_buffer_timer(self):
        """Thinking deltas must NOT start the initial text buffer timer.

        first_text_token_time is only set by actual text deltas.  If thinking
        tokens started the timer, text arriving after a long thinking phase
        would bypass the initial buffer and be prematurely classified as
        final_answer before tool_use blocks have a chance to arrive.
        """
        from anthropic.types import ThinkingBlock, ThinkingDelta

        agent = self._create_agent()
        agent.memory.add_task("Test")

        thinking_block = ThinkingBlock(type="thinking", thinking="", signature="sig")
        thinking_start = RawContentBlockStartEvent(type="content_block_start", index=0, content_block=thinking_block)
        thinking_delta = RawContentBlockDeltaEvent(
            type="content_block_delta",
            index=0,
            delta=ThinkingDelta(type="thinking_delta", thinking="Analyzing..."),
        )
        thinking_stop = ContentBlockStopEvent(type="content_block_stop", index=0)
        text_delta = RawContentBlockDeltaEvent(
            type="content_block_delta",
            index=1,
            delta=TextDelta(type="text_delta", text="Here is the answer."),
        )

        final_message = self._create_final_message()
        mock_stream = self._create_mock_stream(
            [thinking_start, thinking_delta, thinking_stop, text_delta], final_message
        )

        # Simulate: thinking token at T=0, text token at T=2.0 (well past
        # INITIAL_TEXT_BUFFER_DELAY=1.5s).  Because thinking does NOT set the
        # timer, the buffer delay starts at T=2.0 (when text arrives) and
        # the text stays buffered until the stream ends.
        # Calls: StreamState init (stream_start_time, last_progress_log_time),
        # thinking delta (maybe_log_progress),
        # text delta (first_text_token_time, maybe_log_progress),
        # stream_elapsed after streaming completes.
        t0 = 1000.0
        time_calls = iter([t0, t0, t0, t0 + 2.0, t0 + 2.0, t0 + 2.0])

        with (
            patch.object(agent.client.messages, "stream", return_value=mock_stream),
            patch("rossum_agent.agent.streaming.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = time_calls
            steps = []
            async for step in agent._stream_model_response(1):
                steps.append(step)

        # Text should be buffered until stream ends (not flushed prematurely).
        # The finalized thinking step should also appear.
        thinking_steps = [s for s in steps if isinstance(s, ThinkingStep)]
        finalized_thinking = [s for s in thinking_steps if not s.is_streaming]
        assert len(finalized_thinking) == 1

        text_steps = [s for s in steps if isinstance(s, TextDeltaStep)]
        assert len(text_steps) >= 1
        assert any("Here is the answer." in s.text_delta for s in text_steps)
