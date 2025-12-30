"""Core agent module implementing the RossumAgent class with Anthropic tool use API.

This module provides the main agent loop for interacting with the Rossum platform
using Claude models via AWS Bedrock and MCP tools.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import queue
import random
from contextvars import copy_context
from functools import partial
from typing import TYPE_CHECKING

from anthropic import APIError, APITimeoutError, RateLimitError
from anthropic.types import (
    ContentBlockStopEvent,
    InputJSONDelta,
    Message,
    MessageParam,
    MessageStreamEvent,
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    TextDelta,
    ToolParam,
    ToolUseBlock,
)

from rossum_agent.agent.memory import AgentMemory, MemoryStep
from rossum_agent.agent.models import AgentConfig, AgentStep, ToolCall, ToolResult, truncate_content
from rossum_agent.agent.request_classifier import (
    RequestScope,
    classify_request,
    generate_rejection_response,
)
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

    from anthropic import AnthropicBedrock

    from rossum_agent.agent.types import UserContent

logger = logging.getLogger(__name__)


RATE_LIMIT_MAX_RETRIES = 5
RATE_LIMIT_BASE_DELAY = 2.0
RATE_LIMIT_MAX_DELAY = 60.0


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
        with self.client.messages.stream(
            model=model_id,
            max_tokens=self.config.max_tokens,
            system=self.system_prompt,
            messages=messages,
            tools=tools,
            temperature=self.config.temperature,
        ) as stream:
            for event in stream:
                yield (event, None)
            yield (None, stream.get_final_message())

    def _process_stream_event(
        self, event: MessageStreamEvent, pending_tools: dict[int, dict[str, str]], tool_calls: list[ToolCall]
    ) -> str | None:
        """Process a single stream event.

        Args:
            event: The stream event to process.
            pending_tools: Dict tracking in-progress tool use blocks.
            tool_calls: List to append completed tool calls to.

        Returns:
            Text delta if this event contained text, None otherwise.
        """
        if isinstance(event, RawContentBlockStartEvent):
            if isinstance(event.content_block, ToolUseBlock):
                pending_tools[event.index] = {
                    "name": event.content_block.name,
                    "id": event.content_block.id,
                    "json": "",
                }

        elif isinstance(event, RawContentBlockDeltaEvent):
            if isinstance(event.delta, TextDelta):
                text: str = event.delta.text
                return text
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

    async def _stream_model_response(self, step_num: int) -> AsyncIterator[AgentStep]:
        """Stream model response, yielding partial steps as thinking streams in.

        Yields:
            AgentStep objects - partial steps while streaming, then final step with tool results.
        """
        messages = self.memory.write_to_messages()

        tools = await self._get_tools()
        model_id = get_model_id()

        thinking_text = ""
        tool_calls: list[ToolCall] = []
        pending_tools: dict[int, dict[str, str]] = {}
        final_message: Message | None = None

        event_queue: queue.Queue[tuple[MessageStreamEvent | None, Message | None] | None] = queue.Queue()

        def producer() -> None:
            for item in self._sync_stream_events(model_id, messages, tools):
                event_queue.put(item)
            event_queue.put(None)

        ctx = copy_context()
        producer_task = asyncio.get_event_loop().run_in_executor(None, partial(ctx.run, producer))

        while True:
            item = await asyncio.to_thread(event_queue.get)
            if item is None:
                break
            event, final_msg = item
            if final_msg is not None:
                final_message = final_msg
                continue

            text_delta = self._process_stream_event(event, pending_tools, tool_calls)
            if text_delta:
                thinking_text += text_delta
                yield AgentStep(step_number=step_num, thinking=thinking_text, is_streaming=True)

        await producer_task

        if final_message is None:
            raise RuntimeError("Stream ended without final message")

        input_tokens = final_message.usage.input_tokens
        output_tokens = final_message.usage.output_tokens
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        logger.info(
            f"Step {step_num}: input_tokens={input_tokens}, output_tokens={output_tokens}, "
            f"total_input={self._total_input_tokens}, total_output={self._total_output_tokens}"
        )

        step = AgentStep(
            step_number=step_num,
            thinking=thinking_text if thinking_text else None,
            tool_calls=tool_calls,
            is_streaming=False,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        if not tool_calls:
            step.final_answer = thinking_text if thinking_text else None
            step.is_final = True
            memory_step = MemoryStep(
                step_number=step_num,
                text=thinking_text if thinking_text else None,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            self.memory.add_step(memory_step)
            yield step
            return

        async for step_or_result in self._execute_tools_with_progress(
            step_num, thinking_text, tool_calls, step, input_tokens, output_tokens
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
    ) -> AsyncIterator[AgentStep]:
        """Execute tools and yield progress updates."""
        memory_step = MemoryStep(
            step_number=step_num,
            text=thinking_text if thinking_text else None,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        tool_results: list[ToolResult] = []
        total_tools = len(tool_calls)

        for idx, tool_call in enumerate(tool_calls, 1):
            tool_progress = (idx, total_tools)
            yield AgentStep(
                step_number=step_num,
                thinking=thinking_text if thinking_text else None,
                tool_calls=tool_calls,
                is_streaming=True,
                current_tool=tool_call.name,
                tool_progress=tool_progress,
            )

            async for progress_or_result in self._execute_tool_with_progress(
                tool_call, step_num, tool_calls, tool_progress
            ):
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
                    )
                    await asyncio.sleep(wait_time)

                except APITimeoutError as e:
                    logger.warning(f"API timeout at step {step_num}: {e}")
                    yield AgentStep(
                        step_number=step_num, error=f"Request timed out. Please try again. Details: {e}", is_final=True
                    )
                    return

                except APIError as e:
                    logger.error(f"API error at step {step_num}: {e}")
                    yield AgentStep(step_number=step_num, error=f"API error occurred: {e}", is_final=True)
                    return

        else:
            yield AgentStep(
                step_number=self.config.max_steps,
                error=f"Maximum steps ({self.config.max_steps}) reached without final answer.",
                is_final=True,
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
