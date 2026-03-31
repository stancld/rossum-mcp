"""Tool dispatch, serialization, deduplication and staggering for the Rossum agent.

This module handles all tool execution concerns: parsing tool arguments,
deduplicating identical calls, serializing results, and orchestrating parallel
execution with progress reporting.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import queue
from contextvars import copy_context
from functools import partial
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel

from rossum_agent.agent.cautious_gate import check_cautious_write_gate
from rossum_agent.agent.memory import MemoryStep
from rossum_agent.agent.models import (
    ThinkingBlockData,
    ToolCall,
    ToolResult,
    ToolResultStep,
    ToolStartStep,
    truncate_content,
)
from rossum_agent.agent.spillover import maybe_spill
from rossum_agent.tools import execute_internal_tool, get_internal_tool_names
from rossum_agent.tools.core import (
    AgentContext,
    SubAgentProgress,
    SubAgentTokenUsage,
    get_context,
    set_context,
)
from rossum_agent.utils import COMPACT_JSON_SEPARATORS

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from rossum_agent.agent.core import TokenTracker
    from rossum_agent.agent.memory import AgentMemory
    from rossum_agent.rossum_mcp_integration import MCPConnection

logger = logging.getLogger(__name__)


def _parse_json_encoded_strings(arguments: dict) -> dict:
    """Recursively parse JSON-encoded strings in tool arguments.

    LLMs sometimes generate JSON-encoded strings for list/dict arguments instead of
    actual lists/dicts. This function detects and parses such strings.

    For example, converts:
        {"fields_to_keep": "[\"a\", \"b\"]"}
    To:
        {"fields_to_keep": ["a", "b"]}
    """
    # Parameters that should remain as JSON strings (not parsed to lists/dicts)
    keep_as_string = {"changes"}

    result = {}
    for key, value in arguments.items():
        if key in keep_as_string:
            result[key] = value
        elif isinstance(value, str) and value.startswith(("[", "{")):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, (list, dict)):
                    result[key] = parsed
                else:
                    result[key] = value
            except json.JSONDecodeError:
                result[key] = value
        elif isinstance(value, dict):
            result[key] = _parse_json_encoded_strings(value)
        else:
            result[key] = value
    return result


def _tool_call_fingerprint(tool_call: ToolCall) -> str:
    """Create a stable fingerprint for deduplicating identical tool calls in one step."""
    return json.dumps(
        {"name": tool_call.name, "arguments": tool_call.arguments},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _deduplicate_tool_calls(
    tool_calls: list[ToolCall], step_num: int
) -> tuple[list[ToolCall], dict[str, list[ToolCall]]]:
    """Deduplicate identical tool calls, returning unique calls and a map of duplicates by primary ID."""
    deduped: list[ToolCall] = []
    duplicate_calls_by_id: dict[str, list[ToolCall]] = {}
    seen_fingerprints: dict[str, ToolCall] = {}

    for tool_call in tool_calls:
        fingerprint = _tool_call_fingerprint(tool_call)
        primary_call = seen_fingerprints.get(fingerprint)
        if primary_call is None:
            seen_fingerprints[fingerprint] = tool_call
            deduped.append(tool_call)
            duplicate_calls_by_id[tool_call.id] = []
        else:
            duplicate_calls_by_id[primary_call.id].append(tool_call)

    duplicate_count = len(tool_calls) - len(deduped)
    if duplicate_count > 0:
        logger.info(
            "Step %s: deduplicated %s duplicate tool call(s) (%s requested, %s executed)",
            step_num,
            duplicate_count,
            len(tool_calls),
            len(deduped),
        )

    return deduped, duplicate_calls_by_id


class _SchemaStagger:
    """Stagger schema patch calls to avoid 412 conflicts from concurrent writes."""

    _TOOLS: ClassVar[set[str]] = {"patch_schema", "patch_schema_with_subagent"}
    _DELAY_SECONDS = 0.5

    def __init__(self) -> None:
        self._counter = 0

    async def maybe_delay(self, tool_name: str) -> None:
        if tool_name not in self._TOOLS:
            return
        delay = self._counter * self._DELAY_SECONDS
        self._counter += 1
        if delay > 0:
            logger.info("Staggering %s by %.1fs to avoid conflicts", tool_name, delay)
            await asyncio.sleep(delay)


def _to_serializable(obj: object) -> object:
    """Convert a dataclass or Pydantic model to a JSON-serializable form."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    return obj


def serialize_tool_result(result: object) -> str:
    """Serialize a tool result to a string for storage in context.

    Handles pydantic models, dataclasses, dicts, lists, and other objects properly.
    """
    if result is None:
        return "Tool executed successfully (no output)"

    result = _to_serializable(result)
    if isinstance(result, list):
        result = [_to_serializable(item) for item in result]

    if isinstance(result, dict | list):
        return json.dumps(result, separators=COMPACT_JSON_SEPARATORS, default=str)

    return str(result)


def drain_token_queue(tokens: TokenTracker, token_queue: queue.Queue[SubAgentTokenUsage]) -> None:
    """Drain all pending token usage from the queue."""
    while True:
        try:
            usage = token_queue.get_nowait()
            tokens.accumulate_sub(usage)
            logger.info(
                f"Sub-agent '{usage.tool_name}' token usage (iter {usage.iteration}): "
                f"in={usage.input_tokens}, out={usage.output_tokens}, "
                f"cumulative total: in={tokens.total_input}, out={tokens.total_output}"
            )
        except queue.Empty:
            break


async def execute_tool_with_progress(
    tool_call: ToolCall,
    step_num: int,
    tool_calls: list[ToolCall],
    tool_progress: tuple[int, int],
    mcp_connection: MCPConnection,
    tokens: TokenTracker,
) -> AsyncIterator[ToolStartStep | ToolResult]:
    """Execute a tool and yield progress updates for sub-agents.

    For tools with sub-agents, this yields ToolStartStep updates
    with sub_agent_progress. Always yields the final ToolResult.
    """
    # Cautious persona: gate write operations behind user confirmation
    agent_ctx = get_context()
    blocked_result = await check_cautious_write_gate(tool_call, agent_ctx, mcp_connection)
    if blocked_result is not None:
        yield blocked_result
        return

    progress_queue: queue.Queue[SubAgentProgress] = queue.Queue()
    token_queue: queue.Queue[SubAgentTokenUsage] = queue.Queue()

    def progress_callback(progress: SubAgentProgress) -> None:
        progress_queue.put(progress)

    def token_callback(usage: SubAgentTokenUsage) -> None:
        token_queue.put(usage)

    logger.info("Tool call: %s(%s)", tool_call.name, tool_call.arguments)

    try:
        if tool_call.name in get_internal_tool_names():
            logger.info(f"Calling internal tool {tool_call.name}")
            # Create a per-tool AgentContext copy with isolated callbacks
            # to avoid races when multiple tools run in parallel
            agent_ctx = get_context()
            tool_ctx = dataclasses.replace(
                agent_ctx,
                progress_callback=progress_callback,
                token_callback=token_callback,
            )

            def _run_internal_tool(tool_ctx: AgentContext, name: str, arguments: dict) -> object:
                set_context(tool_ctx)
                return execute_internal_tool(name, arguments)

            loop = asyncio.get_running_loop()
            ctx = copy_context()
            future = loop.run_in_executor(
                None, partial(ctx.run, _run_internal_tool, tool_ctx, tool_call.name, tool_call.arguments)
            )

            while not future.done():
                try:
                    progress = progress_queue.get_nowait()
                    yield ToolStartStep(
                        step_number=step_num,
                        tool_calls=tool_calls,
                        tool_progress=tool_progress,
                        current_tool=tool_call.name,
                        current_tool_call_id=tool_call.id,
                        sub_agent_progress=progress,
                    )
                except queue.Empty:
                    pass

                drain_token_queue(tokens, token_queue)
                await asyncio.sleep(0.1)

            drain_token_queue(tokens, token_queue)

            result = future.result()
            content = str(result)
            logger.info(f"Internal tool {tool_call.name} result: {content}")
        else:
            result = await mcp_connection.call_tool(tool_call.name, tool_call.arguments)
            content = serialize_tool_result(result)

        content = maybe_spill(content, tool_call.name, step_num, get_context().get_output_dir(), tool_call.id)
        content = truncate_content(content)
        yield ToolResult(tool_call_id=tool_call.id, name=tool_call.name, content=content)

    except Exception as e:
        error_msg = f"Tool {tool_call.name} failed: {e}"
        logger.warning(f"Tool {tool_call.name} failed: {e}", exc_info=True)
        yield ToolResult(tool_call_id=tool_call.id, name=tool_call.name, content=error_msg, is_error=True)


async def execute_tools_with_progress(
    mcp_connection: MCPConnection,
    tokens: TokenTracker,
    memory: AgentMemory,
    step_num: int,
    response_text: str,
    tool_calls: list[ToolCall],
    input_tokens: int,
    output_tokens: int,
    thinking_blocks: list[ThinkingBlockData] | None = None,
) -> AsyncIterator[ToolStartStep | ToolResultStep]:
    """Execute tools in parallel and yield progress updates."""
    memory_step = MemoryStep(
        step_number=step_num,
        text=response_text or None,
        tool_calls=tool_calls,
        thinking_blocks=thinking_blocks or [],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    deduped_tool_calls, duplicate_calls_by_id = _deduplicate_tool_calls(tool_calls, step_num)
    total_tools = len(deduped_tool_calls)

    yield ToolStartStep(
        step_number=step_num,
        tool_calls=deduped_tool_calls,
        tool_progress=(0, total_tools),
    )

    progress_queue: asyncio.Queue[ToolStartStep] = asyncio.Queue()
    results_by_id: dict[str, ToolResult] = {}

    # Stagger schema patch calls to avoid 412 conflicts from concurrent writes
    stagger = _SchemaStagger()

    async def _execute_single_tool(tool_call: ToolCall, duplicate_calls: list[ToolCall], idx: int) -> None:
        await stagger.maybe_delay(tool_call.name)

        tool_progress = (idx, total_tools)
        async for progress_or_result in execute_tool_with_progress(
            tool_call, step_num, deduped_tool_calls, tool_progress, mcp_connection, tokens
        ):
            if isinstance(progress_or_result, ToolStartStep):
                await progress_queue.put(progress_or_result)
            elif isinstance(progress_or_result, ToolResult):
                results_by_id[tool_call.id] = progress_or_result
                for duplicate_call in duplicate_calls:
                    results_by_id[duplicate_call.id] = ToolResult(
                        tool_call_id=duplicate_call.id,
                        name=duplicate_call.name,
                        content=progress_or_result.content,
                        is_error=progress_or_result.is_error,
                    )

    tasks = [
        asyncio.create_task(_execute_single_tool(tool_call, duplicate_calls_by_id[tool_call.id], idx))
        for idx, tool_call in enumerate(deduped_tool_calls, 1)
    ]

    try:
        pending = set(tasks)
        while pending:
            _done, pending = await asyncio.wait(pending, timeout=0.05, return_when=asyncio.FIRST_COMPLETED)

            while not progress_queue.empty():
                yield progress_queue.get_nowait()

        while not progress_queue.empty():
            yield progress_queue.get_nowait()
    except asyncio.CancelledError:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise

    memory_results = [results_by_id[tc.id] for tc in tool_calls if tc.id in results_by_id]
    streamed_results = [results_by_id[tc.id] for tc in deduped_tool_calls if tc.id in results_by_id]
    memory_step.tool_results = memory_results
    memory.add_step(memory_step)

    yield ToolResultStep(
        step_number=step_num,
        tool_calls=deduped_tool_calls,
        tool_results=streamed_results,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
