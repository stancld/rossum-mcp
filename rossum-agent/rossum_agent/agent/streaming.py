"""Stream event processing for the Rossum agent.

Converts Anthropic streaming events into AgentStep objects for client
consumption. Manages text buffering, thinking block extraction, and
timeout-based flush logic.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import time
from typing import TYPE_CHECKING

from anthropic.types import (
    ContentBlockStopEvent,
    InputJSONDelta,
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    TextDelta,
    ThinkingBlock,
    ThinkingDelta,
    ToolUseBlock,
)

from rossum_agent.agent.models import (
    AgentStep,
    StepType,
    StreamDelta,
    TextDeltaStep,
    ThinkingBlockData,
    ThinkingStep,
    ToolCall,
)
from rossum_agent.agent.tool_execution import _parse_json_encoded_strings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from anthropic.types import Message, MessageStreamEvent

logger = logging.getLogger(__name__)

# Buffer text tokens for this duration before first flush to allow time to determine
# whether this is an intermediate step (with tool calls) or final answer text.
# This delay helps correctly classify the step type before streaming to the client.
INITIAL_TEXT_BUFFER_DELAY = 1.5

# Sentinel for detecting async generator exhaustion in anext()
_STREAM_END = object()

# How often to log streaming progress (seconds)
_STREAM_PROGRESS_LOG_INTERVAL = 10.0


@dataclasses.dataclass
class StreamState:
    """Mutable state for streaming model response.

    Attributes:
        first_text_token_time: Timestamp of when the first text token was received.
            Used to implement initial buffering delay (see INITIAL_TEXT_BUFFER_DELAY).
        initial_buffer_flushed: Whether the initial buffer has been flushed after
            the delay period. Once True, text tokens are streamed immediately.
    """

    thinking_text: str = ""
    response_text: str = ""
    final_message: Message | None = None
    text_buffer: list[str] = dataclasses.field(default_factory=list)
    tool_calls: list[ToolCall] = dataclasses.field(default_factory=list)
    pending_tools: dict[int, dict[str, str]] = dataclasses.field(default_factory=dict)
    first_text_token_time: float | None = None
    initial_buffer_flushed: bool = False
    thinking_finalized: bool = False
    # Streaming progress tracking
    stream_start_time: float = dataclasses.field(default_factory=time.monotonic)
    last_progress_log_time: float = dataclasses.field(default_factory=time.monotonic)
    thinking_deltas: int = 0
    text_deltas: int = 0

    def _should_flush_initial_buffer(self) -> bool:
        """Check if the initial buffer delay has elapsed and buffer should be flushed."""
        if self.initial_buffer_flushed:
            return True
        if self.first_text_token_time is None:
            return False
        return (time.monotonic() - self.first_text_token_time) >= INITIAL_TEXT_BUFFER_DELAY

    def get_step_type(self, step_num: int) -> StepType:
        """Get the step type based on whether tool calls are pending.

        In the first step, default to INTERMEDIATE since the agent nearly always
        uses tools before producing a final answer.
        """
        if self.pending_tools or self.tool_calls or step_num == 1:
            return StepType.INTERMEDIATE
        return StepType.FINAL_ANSWER

    def flush_buffer(self, step_num: int, step_type: StepType) -> TextDeltaStep | None:
        """Flush text buffer and return TextDeltaStep if buffer had content."""
        if not self.text_buffer:
            return None
        buffered_text = "".join(self.text_buffer)
        self.text_buffer.clear()
        self.response_text += buffered_text
        return TextDeltaStep(
            step_number=step_num,
            step_type=step_type,
            text_delta=buffered_text,
            accumulated_text=self.response_text,
            thinking=self.thinking_text or None,
        )

    def finalize_thinking(self, step_num: int) -> ThinkingStep | None:
        """Return a finalized ThinkingStep if thinking exists and hasn't been finalized yet."""
        if not self.thinking_text or self.thinking_finalized:
            return None
        self.thinking_finalized = True
        return ThinkingStep(step_number=step_num, thinking=self.thinking_text, is_streaming=False)

    def maybe_log_progress(self, step_num: int) -> None:
        """Log streaming progress periodically (every _STREAM_PROGRESS_LOG_INTERVAL seconds)."""
        now = time.monotonic()
        if now - self.last_progress_log_time < _STREAM_PROGRESS_LOG_INTERVAL:
            return
        self.last_progress_log_time = now
        elapsed = now - self.stream_start_time
        phase = "thinking" if not self.text_deltas else "text"
        thinking_chars = len(self.thinking_text)
        text_chars = len(self.response_text) + sum(len(t) for t in self.text_buffer)
        total_chars = thinking_chars + text_chars
        chars_per_sec = total_chars / elapsed if elapsed > 0 else 0
        logger.info(
            f"Step {step_num} streaming [{phase}]: {elapsed:.0f}s elapsed, "
            f"chars={total_chars} ({chars_per_sec:.0f}/s), "
            f"thinking={thinking_chars} chars, text={text_chars} chars"
        )


def process_stream_event(
    event: MessageStreamEvent, pending_tools: dict[int, dict[str, str]], tool_calls: list[ToolCall]
) -> StreamDelta | None:
    """Process a single stream event.

    Returns:
        StreamDelta with kind="thinking" or "text", or None if no delta.
    """
    if isinstance(event, RawContentBlockStartEvent):
        if isinstance(event.content_block, ToolUseBlock):
            pending_tools[event.index] = {
                "name": event.content_block.name,
                "id": event.content_block.id,
                "json": "",
            }

    elif isinstance(event, RawContentBlockDeltaEvent):
        if isinstance(event.delta, ThinkingDelta):
            return StreamDelta(kind="thinking", content=event.delta.thinking)
        if isinstance(event.delta, TextDelta):
            return StreamDelta(kind="text", content=event.delta.text)
        if isinstance(event.delta, InputJSONDelta) and event.index in pending_tools:
            pending_tools[event.index]["json"] += event.delta.partial_json

    elif isinstance(event, ContentBlockStopEvent) and event.index in pending_tools:
        tool_info = pending_tools.pop(event.index)
        try:
            arguments = json.loads(tool_info["json"]) if tool_info["json"] else {}
            arguments = _parse_json_encoded_strings(arguments)
        except json.JSONDecodeError as e:
            logger.warning("Failed to decode tool arguments for %s: %s", tool_info["name"], e)
            arguments = {}
        tool_calls.append(ToolCall(id=tool_info["id"], name=tool_info["name"], arguments=arguments))

    return None


def extract_thinking_blocks(message: Message) -> list[ThinkingBlockData]:
    """Extract thinking blocks from a message for preserving in conversation history."""
    return [
        ThinkingBlockData(thinking=block.thinking, signature=block.signature)
        for block in message.content
        if isinstance(block, ThinkingBlock)
    ]


def handle_text_delta(step_num: int, content: str, state: StreamState) -> TextDeltaStep | None:
    """Handle a text delta, buffering or flushing as appropriate."""
    if state.first_text_token_time is None:
        state.first_text_token_time = time.monotonic()
    else:
        if time.monotonic() - state.first_text_token_time > INITIAL_TEXT_BUFFER_DELAY:
            state.initial_buffer_flushed = True

    state.text_buffer.append(content)

    if state.initial_buffer_flushed:
        return state.flush_buffer(step_num, state.get_step_type(step_num))
    if state.pending_tools or state.tool_calls:
        state.initial_buffer_flushed = True
        return state.flush_buffer(step_num, StepType.INTERMEDIATE)
    return None


def handle_text_delta_with_finalization(step_num: int, content: str, state: StreamState) -> list[AgentStep]:
    """Finalize thinking (if needed) then handle text delta. Returns 0-2 steps."""
    steps: list[AgentStep] = []
    if finalized := state.finalize_thinking(step_num):
        steps.append(finalized)
    if text_step := handle_text_delta(step_num, content, state):
        steps.append(text_step)
    return steps


async def process_stream_events(
    step_num: int,
    stream: AsyncIterator[MessageStreamEvent],
    state: StreamState,
) -> AsyncIterator[AgentStep]:
    """Process stream events and yield AgentSteps.

    Text tokens are buffered for INITIAL_TEXT_BUFFER_DELAY seconds after the first
    text token is received. This allows time to determine whether the response will
    include tool calls (intermediate step) or is a final answer, enabling correct
    step type classification before streaming to the client.

    After the initial buffer is flushed, subsequent text tokens are streamed immediately.

    Uses asyncio.wait with timeout on anext() to implement buffer flush during model
    pauses without cancelling the underlying stream read.
    """
    pending_next: asyncio.Task | None = None
    try:
        while True:
            if pending_next is None:
                pending_next = asyncio.ensure_future(anext(stream, _STREAM_END))

            done, _ = await asyncio.wait({pending_next}, timeout=INITIAL_TEXT_BUFFER_DELAY)

            if not done:
                # Yield #1: Timeout-based flush of initial text buffer (ensures responsiveness during model pauses)
                if (
                    state.text_buffer
                    and state._should_flush_initial_buffer()
                    and (step := state.flush_buffer(step_num, state.get_step_type(step_num)))
                ):
                    state.initial_buffer_flushed = True
                    yield step
                continue

            item = pending_next.result()
            pending_next = None

            if item is _STREAM_END:
                # Yield #2: Stream ended - flush any remaining buffered text
                if step := state.flush_buffer(step_num, state.get_step_type(step_num)):
                    yield step
                break

            event: MessageStreamEvent = item  # type: ignore[assignment]  # narrowed after _STREAM_END sentinel check
            delta = process_stream_event(event, state.pending_tools, state.tool_calls)
            if not delta:
                continue

            if delta.kind == "thinking":
                state.thinking_text += delta.content
                state.thinking_deltas += 1
                state.maybe_log_progress(step_num)
                # Yield #3: Streaming thinking tokens (extended thinking / chain-of-thought)
                yield ThinkingStep(
                    step_number=step_num,
                    thinking=state.thinking_text,
                )
                continue

            state.text_deltas += 1
            state.maybe_log_progress(step_num)
            # Yield #4a: Finalize thinking before first text delta.
            # Yield #4b: Text delta - immediate flush after initial buffer period or when tool calls detected.
            for yielded_step in handle_text_delta_with_finalization(step_num, delta.content, state):
                yield yielded_step
    finally:
        if pending_next is not None and not pending_next.done():
            pending_next.cancel()
