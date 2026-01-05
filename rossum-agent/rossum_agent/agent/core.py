"""Core agent module implementing the RossumAgent class with Anthropic tool use API.

This module provides the main agent loop for interacting with the Rossum platform
using Claude models via AWS Bedrock and MCP tools.

Streaming Architecture & AgentStep Yield Points
================================================

The agent streams responses via `_stream_model_response` which yields `AgentStep` objects
at multiple points to provide real-time updates to the client. The yield flow is:

    _stream_model_response
        │
        ├── #5 forwards from _process_stream_events ──┬── #1 Timeout flush (buffer stale after 1.5s)
        │                                             ├── #2 Stream end flush (final text)
        │                                             ├── #3 Thinking tokens (chain-of-thought)
        │                                             └── #4 Text deltas (after initial buffer)
        │
        ├── #6 Final answer (no tools, response complete)
        │
        └── #7 forwards from _execute_tools_with_progress
                ├── Tool starting (which tool is about to run)
                └── Sub-agent progress (from nested agent tools like debug_hook)

Key concepts:
- Initial text buffering (INITIAL_TEXT_BUFFER_DELAY=1.5s) allows determining step type
  (INTERMEDIATE vs FINAL_ANSWER) before streaming to client
- After initial flush, text tokens stream immediately
- Tool execution yields progress updates for UI responsiveness
- In a single step, a thinking block is always followed by an intermediate block
  (tool calls or text response)
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import queue
import random
import time
from contextvars import copy_context
from functools import partial
from typing import TYPE_CHECKING

from anthropic import APIError, APITimeoutError, RateLimitError
from anthropic._types import Omit
from anthropic.types import (
    ContentBlockStopEvent,
    InputJSONDelta,
    Message,
    MessageParam,
    MessageStreamEvent,
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    TextDelta,
    ThinkingBlock,
    ThinkingConfigEnabledParam,
    ThinkingDelta,
    ToolParam,
    ToolUseBlock,
)

from rossum_agent.agent.memory import AgentMemory, MemoryStep
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
from rossum_agent.agent.request_classifier import RequestScope, classify_request, generate_rejection_response
from rossum_agent.bedrock_client import create_bedrock_client, get_model_id
from rossum_agent.rossum_mcp_integration import MCPConnection, mcp_tools_to_anthropic_format
from rossum_agent.tools import (
    DEPLOY_TOOLS,
    INTERNAL_TOOLS,
    SubAgentProgress,
    execute_tool,
    get_deploy_tool_names,
    get_deploy_tools,
    get_internal_tool_names,
    get_internal_tools,
    set_mcp_connection,
    set_progress_callback,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator
    from typing import Literal

    from anthropic import AnthropicBedrock

    from rossum_agent.agent.types import UserContent

logger = logging.getLogger(__name__)


RATE_LIMIT_MAX_RETRIES = 5
RATE_LIMIT_BASE_DELAY = 2.0
RATE_LIMIT_MAX_DELAY = 60.0

# Buffer text tokens for this duration before first flush to allow time to determine
# whether this is an intermediate step (with tool calls) or final answer text.
# This delay helps correctly classify the step type before streaming to the client.
INITIAL_TEXT_BUFFER_DELAY = 1.5


@dataclasses.dataclass
class _StreamState:
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

    def _should_flush_initial_buffer(self) -> bool:
        """Check if the initial buffer delay has elapsed and buffer should be flushed."""
        if self.initial_buffer_flushed:
            return True
        if self.first_text_token_time is None:
            return False
        return (time.monotonic() - self.first_text_token_time) >= INITIAL_TEXT_BUFFER_DELAY

    def get_step_type(self) -> StepType:
        """Get the step type based on whether tool calls are pending."""
        return StepType.INTERMEDIATE if self.pending_tools or self.tool_calls else StepType.FINAL_ANSWER

    def flush_buffer(self, step_num: int, step_type: StepType) -> AgentStep | None:
        """Flush text buffer and return AgentStep if buffer had content."""
        if not self.text_buffer:
            return None
        buffered_text = "".join(self.text_buffer)
        self.text_buffer.clear()
        self.response_text += buffered_text
        return AgentStep(
            step_number=step_num,
            thinking=self.thinking_text or None,
            is_streaming=True,
            text_delta=buffered_text,
            accumulated_text=self.response_text,
            step_type=step_type,
        )

    @property
    def contains_thinking(self) -> bool:
        return self.thinking_text != ""


class RossumAgent:
    """Claude-powered agent for Rossum document processing.

    This agent uses Anthropic's tool use API to interact with the Rossum platform
    via MCP tools. It maintains conversation state across multiple turns and
    supports streaming responses.

    Memory is stored as structured MemoryStep objects and rebuilt into messages
    each call.
    """

    def __init__(
        self,
        client: AnthropicBedrock,
        mcp_connection: MCPConnection,
        system_prompt: str,
        config: AgentConfig | None = None,
        additional_tools: list[ToolParam] | None = None,
    ) -> None:
        self.client = client
        self.mcp_connection = mcp_connection
        self.system_prompt = system_prompt
        self.config = config or AgentConfig()
        self.additional_tools = additional_tools or []

        self.memory = AgentMemory()
        self._tools_cache: list[ToolParam] | None = None
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0

    @property
    def messages(self) -> list[MessageParam]:
        """Get the current conversation messages (rebuilt from memory)."""
        return self.memory.write_to_messages()

    def reset(self) -> None:
        """Reset the agent's conversation state."""
        self.memory.reset()
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    def add_user_message(self, content: UserContent) -> None:
        """Add a user message to the conversation history."""
        self.memory.add_task(content)

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the conversation history.

        This creates a MemoryStep with text set, which ensures the
        message is properly serialized when rebuilding conversation history.
        For proper conversation flow with tool use, use the run() method instead.
        """
        step = MemoryStep(step_number=0, text=content)
        self.memory.add_step(step)

    async def _get_tools(self) -> list[ToolParam]:
        """Get all available tools in Anthropic format (cached)."""
        if self._tools_cache is None:
            mcp_tools = await self.mcp_connection.get_tools()
            self._tools_cache = (
                mcp_tools_to_anthropic_format(mcp_tools)
                + get_internal_tools()
                + get_deploy_tools()
                + self.additional_tools
            )
        return self._tools_cache

    def _serialize_tool_result(self, result: object) -> str:
        """Serialize a tool result to a string for storage in context.

        Handles pydantic models, dataclasses, dicts, lists, and other objects properly.
        """
        if result is None:
            return "Tool executed successfully (no output)"

        # Handle dataclasses (check before pydantic since pydantic models aren't dataclasses)
        if dataclasses.is_dataclass(result) and not isinstance(result, type):
            return json.dumps(dataclasses.asdict(result), indent=2, default=str)

        # Handle lists of dataclasses
        if isinstance(result, list) and result and dataclasses.is_dataclass(result[0]):
            return json.dumps([dataclasses.asdict(item) for item in result], indent=2, default=str)

        # Handle pydantic models (BaseModel has model_dump method)
        # Use mode='json' to ensure nested models are properly serialized to JSON-compatible dicts
        if hasattr(result, "model_dump"):
            return json.dumps(result.model_dump(mode="json"), indent=2, default=str)

        # Handle lists of pydantic models
        if isinstance(result, list) and result and hasattr(result[0], "model_dump"):
            return json.dumps([item.model_dump(mode="json") for item in result], indent=2, default=str)

        # Handle dicts and regular lists
        if isinstance(result, dict | list):
            return json.dumps(result, indent=2, default=str)

        # Fallback to string representation
        return str(result)

    def _sync_stream_events(
        self, model_id: str, messages: list[MessageParam], tools: list[ToolParam]
    ) -> Iterator[tuple[MessageStreamEvent | None, Message | None]]:
        """Synchronous generator that yields stream events and final message.

        This runs in a thread pool to avoid blocking the event loop.

        Yields:
            Tuples of (event, None) for each stream event, then (None, final_message) at the end.
        """
        thinking_config: ThinkingConfigEnabledParam = {
            "type": "enabled",
            "budget_tokens": self.config.thinking_budget_tokens,
        }
        with self.client.messages.stream(
            model=model_id,
            max_tokens=self.config.max_tokens,
            system=self.system_prompt,
            messages=messages,
            tools=tools if tools else Omit(),
            thinking=thinking_config,
            temperature=self.config.temperature,
        ) as stream:
            for event in stream:
                yield (event, None)
            yield (None, stream.get_final_message())

    def _process_stream_event(
        self,
        event: MessageStreamEvent,
        pending_tools: dict[int, dict[str, str]],
        tool_calls: list[ToolCall],
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
            except json.JSONDecodeError as e:
                logger.warning("Failed to decode tool arguments for %s: %s", tool_info["name"], e)
                arguments = {}
            tool_calls.append(ToolCall(id=tool_info["id"], name=tool_info["name"], arguments=arguments))

        return None

    def _extract_thinking_blocks(self, message: Message) -> list[ThinkingBlockData]:
        """Extract thinking blocks from a message for preserving in conversation history."""
        return [
            ThinkingBlockData(thinking=block.thinking, signature=block.signature)
            for block in message.content
            if isinstance(block, ThinkingBlock)
        ]

    def _handle_text_delta(
        self, step_num: int, content: str, delta_kind: Literal["thinking", "text"], state: _StreamState
    ) -> AgentStep | None:
        """Handle a text delta, buffering or flushing as appropriate."""
        if state.first_text_token_time is None:
            state.first_text_token_time = time.monotonic()
        else:
            if time.monotonic() - state.first_text_token_time > INITIAL_TEXT_BUFFER_DELAY:
                state.initial_buffer_flushed = True

        state.text_buffer.append(content)

        if state.initial_buffer_flushed:
            step_type = (
                StepType.INTERMEDIATE if state.contains_thinking and delta_kind == "text" else state.get_step_type()
            )
            return state.flush_buffer(step_num, step_type)
        if state.pending_tools or state.tool_calls:
            state.initial_buffer_flushed = True
            return state.flush_buffer(step_num, StepType.INTERMEDIATE)
        return None

    async def _process_stream_events(
        self,
        step_num: int,
        event_queue: queue.Queue[tuple[MessageStreamEvent | None, Message | None] | None],
        state: _StreamState,
    ) -> AsyncIterator[AgentStep]:
        """Process stream events and yield AgentSteps.

        Text tokens are buffered for INITIAL_TEXT_BUFFER_DELAY seconds after the first
        text token is received. This allows time to determine whether the response will
        include tool calls (intermediate step) or is a final answer, enabling correct
        step type classification before streaming to the client.

        After the initial buffer is flushed, subsequent text tokens are streamed immediately.
        """
        while True:
            try:
                item = await asyncio.to_thread(event_queue.get, timeout=INITIAL_TEXT_BUFFER_DELAY)
            except queue.Empty:
                # Yield #1: Timeout-based flush of initial text buffer (ensures responsiveness during model pauses)
                if (
                    state.text_buffer
                    and state._should_flush_initial_buffer()
                    and (step := state.flush_buffer(step_num, state.get_step_type()))
                ):
                    state.initial_buffer_flushed = True
                    yield step
                continue

            if item is None:
                # Yield #2: Stream ended - flush any remaining buffered text
                if step := state.flush_buffer(step_num, state.get_step_type()):
                    yield step
                break

            event, final_msg = item
            if final_msg is not None:
                state.final_message = final_msg
                continue

            delta = self._process_stream_event(event, state.pending_tools, state.tool_calls)
            if not delta:
                continue

            if delta.kind == "thinking":
                state.thinking_text += delta.content
                # Yield #3: Streaming thinking tokens (extended thinking / chain-of-thought)
                yield AgentStep(
                    step_number=step_num,
                    thinking=state.thinking_text,
                    is_streaming=True,
                    step_type=StepType.THINKING,
                )
                if state.first_text_token_time is None:
                    state.first_text_token_time = time.monotonic()
                continue

            # Yield #4: Text delta - immediate flush after initial buffer period or when tool calls detected
            if step := self._handle_text_delta(step_num, delta.content, delta.kind, state):
                yield step

    async def _stream_model_response(self, step_num: int) -> AsyncIterator[AgentStep]:
        """Stream model response, yielding partial steps as thinking streams in.

        Extended thinking separates the model's internal reasoning (thinking blocks)
        from its final response (text blocks). This allows distinguishing between
        the chain-of-thought process and the actual answer.

        Yields:
            AgentStep objects - partial steps while streaming, then final step with tool results.
        """
        messages = self.memory.write_to_messages()
        tools = await self._get_tools()
        model_id = get_model_id()
        state = _StreamState()

        event_queue: queue.Queue[tuple[MessageStreamEvent | None, Message | None] | None] = queue.Queue()

        def producer() -> None:
            for item in self._sync_stream_events(model_id, messages, tools):
                event_queue.put(item)
            event_queue.put(None)

        ctx = copy_context()
        producer_task = asyncio.get_event_loop().run_in_executor(None, partial(ctx.run, producer))

        # Yield #5: Forward all streaming steps from _process_stream_events (yields #1-4)
        async for step in self._process_stream_events(step_num, event_queue, state):
            yield step

        await producer_task

        if state.final_message is None:
            raise RuntimeError("Stream ended without final message")

        thinking_blocks = self._extract_thinking_blocks(state.final_message)
        input_tokens = state.final_message.usage.input_tokens
        output_tokens = state.final_message.usage.output_tokens
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        logger.info(
            f"Step {step_num}: input_tokens={input_tokens}, output_tokens={output_tokens}, "
            f"total_input={self._total_input_tokens}, total_output={self._total_output_tokens}"
        )

        step = AgentStep(
            step_number=step_num,
            thinking=state.thinking_text if state.thinking_text else None,
            tool_calls=state.tool_calls,
            is_streaming=False,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            step_type=StepType.FINAL_ANSWER if not state.tool_calls else StepType.INTERMEDIATE,
        )

        if not state.tool_calls:
            step.final_answer = state.response_text if state.response_text else None
            step.is_final = True
            memory_step = MemoryStep(
                step_number=step_num,
                text=state.response_text if state.response_text else None,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            self.memory.add_step(memory_step)
            # Yield #6: Final answer step (no tool calls, response complete)
            yield step
            return

        # Yield #7: Forward tool execution progress steps from _execute_tools_with_progress
        async for step_or_result in self._execute_tools_with_progress(
            step_num, state.response_text, state.tool_calls, step, input_tokens, output_tokens, thinking_blocks
        ):
            yield step_or_result

    async def _execute_tools_with_progress(
        self,
        step_num: int,
        thinking_text: str,
        tool_calls: list[ToolCall],
        step: AgentStep,
        input_tokens: int,
        output_tokens: int,
        thinking_blocks: list[ThinkingBlockData] | None = None,
    ) -> AsyncIterator[AgentStep]:
        """Execute tools and yield progress updates."""
        memory_step = MemoryStep(
            step_number=step_num,
            text=thinking_text if thinking_text else None,
            tool_calls=tool_calls,
            thinking_blocks=thinking_blocks or [],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        tool_results: list[ToolResult] = []
        total_tools = len(tool_calls)

        for idx, tool_call in enumerate(tool_calls, 1):
            tool_progress = (idx, total_tools)
            # Yield: Tool execution starting - shows which tool is about to run
            yield AgentStep(
                step_number=step_num,
                thinking=thinking_text if thinking_text else None,
                tool_calls=tool_calls,
                is_streaming=True,
                current_tool=tool_call.name,
                tool_progress=tool_progress,
                step_type=StepType.INTERMEDIATE,
            )

            async for progress_or_result in self._execute_tool_with_progress(
                tool_call, step_num, tool_calls, tool_progress
            ):
                # Yield: Sub-agent progress updates from tool execution
                if isinstance(progress_or_result, AgentStep):
                    yield progress_or_result
                elif isinstance(progress_or_result, ToolResult):
                    tool_results.append(progress_or_result)

        step.tool_results = tool_results
        memory_step.tool_results = tool_results

        self.memory.add_step(memory_step)

        yield step

    async def _execute_tool_with_progress(
        self, tool_call: ToolCall, step_num: int, tool_calls: list[ToolCall], tool_progress: tuple[int, int]
    ) -> AsyncIterator[AgentStep | ToolResult]:
        """Execute a tool and yield progress updates for sub-agents.

        For tools with sub-agents (like debug_hook), this yields AgentStep updates
        with sub_agent_progress. Always yields the final ToolResult.
        """
        progress_queue: queue.Queue[SubAgentProgress] = queue.Queue()

        def progress_callback(progress: SubAgentProgress) -> None:
            progress_queue.put(progress)

        try:
            if tool_call.name in get_internal_tool_names():
                set_progress_callback(progress_callback)

                loop = asyncio.get_event_loop()
                ctx = copy_context()
                future = loop.run_in_executor(
                    None, partial(ctx.run, execute_tool, tool_call.name, tool_call.arguments, INTERNAL_TOOLS)
                )

                while not future.done():
                    try:
                        progress = progress_queue.get_nowait()
                        yield AgentStep(
                            step_number=step_num,
                            tool_calls=tool_calls,
                            is_streaming=True,
                            current_tool=tool_call.name,
                            tool_progress=tool_progress,
                            sub_agent_progress=progress,
                            step_type=StepType.INTERMEDIATE,
                        )
                    except queue.Empty:
                        pass
                    await asyncio.sleep(0.1)

                result = future.result()
                content = str(result)
                set_progress_callback(None)
            elif tool_call.name in get_deploy_tool_names():
                loop = asyncio.get_event_loop()
                ctx = copy_context()
                future = loop.run_in_executor(
                    None, partial(ctx.run, execute_tool, tool_call.name, tool_call.arguments, DEPLOY_TOOLS)
                )
                result = await future
                content = str(result)
            else:
                result = await self.mcp_connection.call_tool(tool_call.name, tool_call.arguments)
                content = self._serialize_tool_result(result)

            content = truncate_content(content)
            yield ToolResult(tool_call_id=tool_call.id, name=tool_call.name, content=content)

        except Exception as e:
            set_progress_callback(None)
            error_msg = f"Tool {tool_call.name} failed: {e}"
            logger.warning(f"Tool {tool_call.name} failed: {e}", exc_info=True)
            yield ToolResult(tool_call_id=tool_call.id, name=tool_call.name, content=error_msg, is_error=True)

    def _extract_text_from_prompt(self, prompt: UserContent) -> str:
        """Extract text content from a user prompt for classification."""
        if isinstance(prompt, str):
            return prompt
        text_parts: list[str] = []
        for block in prompt:
            if block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
        return " ".join(text_parts)

    def _check_request_scope(self, prompt: UserContent) -> AgentStep | None:
        """Check if request is in scope, return rejection step if out of scope."""
        text = self._extract_text_from_prompt(prompt)
        result = classify_request(self.client, text)
        self._total_input_tokens += result.input_tokens
        self._total_output_tokens += result.output_tokens
        if result.scope == RequestScope.OUT_OF_SCOPE:
            rejection = generate_rejection_response(self.client, text)
            total_input = result.input_tokens + rejection.input_tokens
            total_output = result.output_tokens + rejection.output_tokens
            self._total_input_tokens += rejection.input_tokens
            self._total_output_tokens += rejection.output_tokens
            return AgentStep(
                step_number=1,
                final_answer=rejection.response,
                is_final=True,
                input_tokens=total_input,
                output_tokens=total_output,
                step_type=StepType.FINAL_ANSWER,
            )
        return None

    async def run(self, prompt: UserContent) -> AsyncIterator[AgentStep]:
        """Run the agent with the given prompt, yielding steps.

        This method implements the main agent loop, calling the model,
        executing tools, and continuing until the model produces a final
        answer or the maximum number of steps is reached.

        Rate limiting is handled with exponential backoff and jitter.
        """
        if rejection := self._check_request_scope(prompt):
            yield rejection
            return

        set_mcp_connection(self.mcp_connection, asyncio.get_event_loop())
        self.memory.add_task(prompt)

        for step_num in range(1, self.config.max_steps + 1):
            rate_limit_retries = 0

            # Throttle requests to avoid rate limiting (skip delay on first step)
            if step_num > 1 and self.config.request_delay > 0:
                await asyncio.sleep(self.config.request_delay)

            while True:
                try:
                    final_step: AgentStep | None = None
                    async for step in self._stream_model_response(step_num):
                        yield step
                        if not step.is_streaming:
                            final_step = step

                    if final_step and final_step.is_final:
                        return

                    break

                except RateLimitError as e:
                    rate_limit_retries += 1
                    if rate_limit_retries > RATE_LIMIT_MAX_RETRIES:
                        logger.error(f"Rate limit retries exhausted at step {step_num}: {e}")
                        yield AgentStep(
                            step_number=step_num,
                            error=f"Rate limit exceeded after {RATE_LIMIT_MAX_RETRIES} retries. Please try again later.",
                            is_final=True,
                            step_type=StepType.FINAL_ANSWER,
                        )
                        return

                    delay = min(RATE_LIMIT_BASE_DELAY * (2 ** (rate_limit_retries - 1)), RATE_LIMIT_MAX_DELAY)
                    jitter = random.uniform(0, delay * 0.1)
                    wait_time = delay + jitter
                    logger.warning(
                        f"Rate limit hit at step {step_num} (attempt {rate_limit_retries}/{RATE_LIMIT_MAX_RETRIES}), "
                        f"retrying in {wait_time:.1f}s: {e}"
                    )
                    yield AgentStep(
                        step_number=step_num,
                        thinking=f"⏳ Rate limited, waiting {wait_time:.1f}s before retry ({rate_limit_retries}/{RATE_LIMIT_MAX_RETRIES})...",
                        is_streaming=True,
                        step_type=StepType.INTERMEDIATE,
                    )
                    await asyncio.sleep(wait_time)

                except APITimeoutError as e:
                    logger.warning(f"API timeout at step {step_num}: {e}")
                    yield AgentStep(
                        step_number=step_num,
                        error=f"Request timed out. Please try again. Details: {e}",
                        is_final=True,
                        step_type=StepType.FINAL_ANSWER,
                    )
                    return

                except APIError as e:
                    logger.error(f"API error at step {step_num}: {e}")
                    yield AgentStep(
                        step_number=step_num,
                        error=f"API error occurred: {e}",
                        is_final=True,
                        step_type=StepType.FINAL_ANSWER,
                    )
                    return

        else:
            yield AgentStep(
                step_number=self.config.max_steps,
                error=f"Maximum steps ({self.config.max_steps}) reached without final answer.",
                is_final=True,
                step_type=StepType.FINAL_ANSWER,
            )


async def create_agent(
    mcp_connection: MCPConnection,
    system_prompt: str,
    config: AgentConfig | None = None,
    additional_tools: list[ToolParam] | None = None,
) -> RossumAgent:
    """Create and configure a RossumAgent instance.

    This is a convenience factory function that creates the Bedrock client
    and initializes the agent with the provided configuration.
    """
    client = create_bedrock_client()
    return RossumAgent(
        client=client,
        mcp_connection=mcp_connection,
        system_prompt=system_prompt,
        config=config,
        additional_tools=additional_tools,
    )
