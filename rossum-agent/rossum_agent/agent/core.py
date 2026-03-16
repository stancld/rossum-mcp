"""Core agent module implementing the RossumAgent class with Anthropic tool use API.

This module provides the main agent loop for interacting with the Rossum platform
using Claude models via AWS Bedrock and MCP tools.

Streaming Architecture & AgentStep Yield Points
================================================

The agent streams responses via `_stream_model_response` which yields `AgentStep` objects
at multiple points to provide real-time updates to the client. The yield flow is:

    _stream_model_response
        │
        ├── #5 forwards from process_stream_events ──┬── #1 Timeout flush (buffer stale after 1.5s)
        │                                            ├── #2 Stream end flush (final text)
        │                                            ├── #3 Thinking tokens (chain-of-thought)
        │                                            └── #4 Text deltas (after initial buffer)
        │
        ├── #6 Final answer (no tools, response complete)
        │
        └── #7 forwards from execute_tools_with_progress
                ├── Tool starting (which tool is about to run)
                └── Sub-agent progress (from nested agent tools like patch_schema_with_subagent)

Key concepts:
- Uses AsyncAnthropicBedrock with async streaming (no thread pool bridge)
- process_stream_events uses asyncio.wait on anext() for timeout-based buffer flushing
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
import logging
import random
import time
from contextvars import copy_context
from functools import partial
from typing import TYPE_CHECKING

from anthropic import APIError, APITimeoutError, RateLimitError
from anthropic._types import Omit

from rossum_agent.agent.memory import AgentMemory, MemoryStep
from rossum_agent.agent.models import (
    AgentConfig,
    AgentStep,
    ErrorStep,
    FinalAnswerStep,
    StepType,
    TextDeltaStep,
    ThinkingStep,
)
from rossum_agent.agent.streaming import (
    StreamState,
    extract_thinking_blocks,
    process_stream_events,
)
from rossum_agent.agent.tool_execution import execute_tools_with_progress
from rossum_agent.api.models.schemas import TokenUsageBreakdown
from rossum_agent.bedrock_client import create_async_bedrock_client, get_model_id
from rossum_agent.rossum_mcp_integration import mcp_tools_to_anthropic_format
from rossum_agent.tools import get_internal_tools
from rossum_agent.tools.core import SubAgentTokenUsage, get_context
from rossum_agent.tools.dynamic_tools import (
    DELETE_TOOL_NAME,
    DISCOVERY_TOOL_NAME,
    get_dynamic_tools,
    get_tools_version,
    preload_categories_for_request,
    reset_dynamic_tools,
)
from rossum_agent.utils import add_message_cache_breakpoint

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from anthropic import AsyncAnthropicBedrock
    from anthropic.types import MessageParam, TextBlockParam, ThinkingConfigAdaptiveParam, ToolParam

    from rossum_agent.agent.types import UserContent
    from rossum_agent.rossum_mcp_integration import MCPConnection

logger = logging.getLogger(__name__)

RATE_LIMIT_MAX_RETRIES = 5
RATE_LIMIT_BASE_DELAY = 2.0
RATE_LIMIT_MAX_DELAY = 60.0


@dataclasses.dataclass
class TokenTracker:
    """Tracks all token usage (main agent + sub-agents) in one place."""

    main_input: int = 0
    main_output: int = 0
    sub_input: int = 0
    sub_output: int = 0
    main_cache_creation: int = 0
    main_cache_read: int = 0
    sub_cache_creation: int = 0
    sub_cache_read: int = 0
    sub_by_tool: dict[str, tuple[int, int]] = dataclasses.field(default_factory=dict)
    sub_cache_by_tool: dict[str, tuple[int, int]] = dataclasses.field(default_factory=dict)
    last_main_input: int = 0

    @property
    def total_input(self) -> int:
        return self.main_input + self.sub_input

    @property
    def total_output(self) -> int:
        return self.main_output + self.sub_output

    @property
    def total_cache_creation(self) -> int:
        return self.main_cache_creation + self.sub_cache_creation

    @property
    def total_cache_read(self) -> int:
        return self.main_cache_read + self.sub_cache_read

    def accumulate_main(self, input_tokens: int, output_tokens: int, cache_creation: int, cache_read: int) -> None:
        self.main_input += input_tokens
        self.main_output += output_tokens
        self.main_cache_creation += cache_creation
        self.main_cache_read += cache_read
        self.last_main_input = input_tokens

    def accumulate_sub(self, usage: SubAgentTokenUsage) -> None:
        self.sub_input += usage.input_tokens
        self.sub_output += usage.output_tokens
        prev_in, prev_out = self.sub_by_tool.get(usage.tool_name, (0, 0))
        self.sub_by_tool[usage.tool_name] = (prev_in + usage.input_tokens, prev_out + usage.output_tokens)
        self.sub_cache_creation += usage.cache_creation_input_tokens
        self.sub_cache_read += usage.cache_read_input_tokens
        prev_cc, prev_cr = self.sub_cache_by_tool.get(usage.tool_name, (0, 0))
        self.sub_cache_by_tool[usage.tool_name] = (
            prev_cc + usage.cache_creation_input_tokens,
            prev_cr + usage.cache_read_input_tokens,
        )

    def to_breakdown(self) -> TokenUsageBreakdown:
        return TokenUsageBreakdown.from_raw_counts(
            total_input=self.total_input,
            total_output=self.total_output,
            main_input=self.main_input,
            main_output=self.main_output,
            sub_input=self.sub_input,
            sub_output=self.sub_output,
            sub_by_tool=self.sub_by_tool,
            main_cache_creation=self.main_cache_creation,
            main_cache_read=self.main_cache_read,
            sub_cache_creation=self.sub_cache_creation,
            sub_cache_read=self.sub_cache_read,
            sub_cache_by_tool=self.sub_cache_by_tool,
        )


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
        client: AsyncAnthropicBedrock,
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
        self._tools_cache_version: int = -1
        self.tokens = TokenTracker()

    @property
    def messages(self) -> list[MessageParam]:
        """Get the current conversation messages (rebuilt from memory)."""
        return self.memory.write_to_messages()

    def reset(self) -> None:
        """Reset the agent's conversation state."""
        self.memory.reset()
        self.tokens = TokenTracker()
        reset_dynamic_tools()

    def get_token_usage_breakdown(self) -> TokenUsageBreakdown:
        """Get token usage breakdown by agent vs sub-agents."""
        return self.tokens.to_breakdown()

    def log_token_usage_summary(self) -> None:
        """Log a human-readable token usage summary."""
        breakdown = self.get_token_usage_breakdown()
        logger.info("\n".join(breakdown.format_summary_lines()))

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
        """Get all available tools in Anthropic format.

        Initially loads only the discovery tool from MCP (list_tool_categories)
        plus internal tools. Additional MCP tools are loaded dynamically via
        load_tool.
        """
        current_version = get_tools_version()
        if self._tools_cache is None or self._tools_cache_version != current_version:
            mcp_tools = await self.mcp_connection.get_tools()
            always_loaded_names = {DISCOVERY_TOOL_NAME}
            if not get_context().is_read_only:
                always_loaded_names.add(DELETE_TOOL_NAME)
            always_loaded = [t for t in mcp_tools if t.name in always_loaded_names]
            self._tools_cache = (
                mcp_tools_to_anthropic_format(always_loaded) + get_internal_tools() + self.additional_tools
            )
            self._tools_cache_version = current_version
        # Include dynamically loaded tools
        return self._tools_cache + get_dynamic_tools()

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
        state = StreamState()
        logger.info(f"Step {step_num}: streaming started (model={model_id}, messages={len(messages)})")

        thinking_config: ThinkingConfigAdaptiveParam = {"type": "adaptive"}

        # Cache breakpoints: system prompt
        system: list[TextBlockParam] = [
            {"type": "text", "text": self.system_prompt, "cache_control": {"type": "ephemeral"}}
        ]

        # Cache breakpoints: last tool definition
        if tools:
            tools = [*tools]  # shallow copy
            tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral"}}  # type: ignore[assignment]  # runtime addition of cache_control

        # Cache breakpoints: last message content block
        add_message_cache_breakpoint(messages)  # type: ignore[arg-type]  # MessageParam is dict at runtime

        async with self.client.messages.stream(
            model=model_id,
            max_tokens=self.config.max_output_tokens,
            system=system,
            messages=messages,
            tools=tools or Omit(),
            thinking=thinking_config,
            temperature=self.config.temperature,
            output_config={"effort": self.config.effort},
        ) as stream:
            # Yield #5: Forward all streaming steps from process_stream_events (yields #1-4)
            async for step in process_stream_events(step_num, stream, state):  # type: ignore[arg-type]  # AsyncMessageStream implements AsyncIterator protocol
                yield step
            state.final_message = await stream.get_final_message()

        if state.final_message is None:
            raise RuntimeError("Stream ended without final message")

        thinking_blocks = extract_thinking_blocks(state.final_message)
        raw_input_tokens = state.final_message.usage.input_tokens
        output_tokens = state.final_message.usage.output_tokens
        cache_creation = getattr(state.final_message.usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(state.final_message.usage, "cache_read_input_tokens", 0) or 0
        input_tokens = raw_input_tokens + cache_creation + cache_read
        self.tokens.accumulate_main(input_tokens, output_tokens, cache_creation, cache_read)
        stream_elapsed = time.monotonic() - state.stream_start_time
        logger.info(
            f"Step {step_num}: completed in {stream_elapsed:.1f}s, "
            f"input_tokens={input_tokens}, output_tokens={output_tokens}, "
            f"cache_creation={cache_creation}, cache_read={cache_read}, "
            f"total_input={self.tokens.total_input}, total_output={self.tokens.total_output}"
        )

        # Yield #6: Finalize thinking if not already done (e.g. thinking → tool_use with no text)
        if finalized := state.finalize_thinking(step_num):
            yield finalized

        # Yield #7: Finalized text event that corrects misclassification.
        # During streaming, text may have been classified as final_answer before tool_use
        # blocks arrived. Now that tool_calls is fully populated, emit the authoritative
        # intermediate classification. Only needed when tool calls exist — otherwise
        # FinalAnswerStep (yield #8) already serves as the finalization event.
        if state.response_text and state.tool_calls:
            yield TextDeltaStep(
                step_number=step_num,
                step_type=StepType.INTERMEDIATE,
                text_delta="",
                accumulated_text=state.response_text,
                is_streaming=False,
            )

        if not state.tool_calls:
            memory_step = MemoryStep(
                step_number=step_num,
                text=state.response_text or None,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            self.memory.add_step(memory_step)
            # Yield #8: Final answer step (no tool calls, response complete)
            yield FinalAnswerStep(
                step_number=step_num,
                final_answer=state.response_text or "",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            return

        # Yield #9: Forward tool execution progress steps from execute_tools_with_progress
        async for step_or_result in execute_tools_with_progress(
            self.mcp_connection,
            self.tokens,
            self.memory,
            step_num,
            response_text=state.response_text,
            tool_calls=state.tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_blocks=thinking_blocks,
        ):
            yield step_or_result

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

    def _calculate_rate_limit_delay(self, retries: int) -> float:
        """Calculate exponential backoff delay with jitter for rate limiting."""
        delay = min(RATE_LIMIT_BASE_DELAY * (2 ** (retries - 1)), RATE_LIMIT_MAX_DELAY)
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter

    async def run(self, prompt: UserContent) -> AsyncIterator[AgentStep]:
        """Run the agent with the given prompt, yielding steps.

        This method implements the main agent loop, calling the model,
        executing tools, and continuing until the model produces a final
        answer or the maximum number of steps is reached.

        Rate limiting is handled with exponential backoff and jitter.
        """
        loop = asyncio.get_running_loop()
        agent_ctx = get_context()
        agent_ctx.mcp_connection = self.mcp_connection
        agent_ctx.mcp_event_loop = loop

        # Pre-load tool categories based on keywords in the user's request
        # Run in thread pool to avoid blocking the event loop (preload uses sync MCP calls)
        request_text = self._extract_text_from_prompt(prompt)
        ctx = copy_context()
        preload_result = await loop.run_in_executor(
            None, partial(ctx.run, preload_categories_for_request, request_text)
        )

        self.memory.add_task(prompt, preload_info=preload_result)

        for step_num in range(1, self.config.max_steps + 1):
            rate_limit_retries = 0

            # Throttle requests to avoid rate limiting (skip delay on first step)
            if step_num > 1:
                await asyncio.sleep(self.config.request_delay)

            while True:
                try:
                    is_done = False
                    async for step in self._stream_model_response(step_num):
                        yield step
                        if isinstance(step, (FinalAnswerStep, ErrorStep)):
                            is_done = True

                    if is_done:
                        return

                    break

                except asyncio.CancelledError:
                    raise

                except RateLimitError as e:
                    rate_limit_retries += 1
                    if rate_limit_retries > RATE_LIMIT_MAX_RETRIES:
                        logger.error(f"Rate limit retries exhausted at step {step_num}: {e}")
                        yield ErrorStep(
                            step_number=step_num,
                            error=f"Rate limit exceeded after {RATE_LIMIT_MAX_RETRIES} retries. Please try again later.",
                        )
                        return

                    wait_time = self._calculate_rate_limit_delay(rate_limit_retries)
                    logger.warning(
                        f"Rate limit hit at step {step_num} (attempt {rate_limit_retries}/{RATE_LIMIT_MAX_RETRIES}), "
                        f"retrying in {wait_time:.1f}s: {e}"
                    )
                    yield ThinkingStep(
                        step_number=step_num,
                        thinking=f"⏳ Rate limited, waiting {wait_time:.1f}s before retry ({rate_limit_retries}/{RATE_LIMIT_MAX_RETRIES})...",
                    )
                    await asyncio.sleep(wait_time)

                except APIError as e:
                    is_timeout = isinstance(e, APITimeoutError)
                    log_fn = logger.warning if is_timeout else logger.error
                    log_fn(f"API {'timeout' if is_timeout else 'error'} at step {step_num}: {e}")
                    error_msg = (
                        f"Request timed out. Please try again. Details: {e}"
                        if is_timeout
                        else f"API error occurred: {e}"
                    )
                    yield ErrorStep(
                        step_number=step_num,
                        error=error_msg,
                    )
                    return

        else:
            yield ErrorStep(
                step_number=self.config.max_steps,
                error=f"Maximum steps ({self.config.max_steps}) reached without final answer.",
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
    client = create_async_bedrock_client()
    return RossumAgent(
        client=client,
        mcp_connection=mcp_connection,
        system_prompt=system_prompt,
        config=config,
        additional_tools=additional_tools,
    )
