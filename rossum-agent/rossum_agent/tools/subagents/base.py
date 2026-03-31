"""Shared base for sub-agents with iterative LLM tool-use loops."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from rossum_agent.bedrock_client import create_bedrock_client, get_model_id
from rossum_agent.tools.core import (
    SubAgentProgress,
    SubAgentTokenUsage,
    get_context,
)
from rossum_agent.utils import add_message_cache_breakpoint

logger = logging.getLogger(__name__)


@dataclass
class SubAgentConfig:
    """Configuration for a sub-agent iteration loop."""

    tool_name: str
    system_prompt: str
    tools: list[dict[str, Any]]
    max_iterations: int = 15
    max_tokens: int = 16384


@dataclass
class SubAgentResult:
    """Result from a sub-agent execution."""

    analysis: str
    input_tokens: int
    output_tokens: int
    iterations_used: int
    tool_calls: list[dict[str, Any]] | None = None


def _fmt_tool_call(name: str, inp: dict[str, Any]) -> str:
    """Format a tool call as 'name(preview)' for progress display."""
    if not isinstance(inp, dict):
        return name
    for key in ("pattern", "query", "slug", "text", "objective", "url", "path"):
        val = inp.get(key)
        if isinstance(val, str) and val.strip():
            s = " ".join(val.strip().split())
            return f"{name}({s[:50]}{'...' if len(s) > 50 else ''})"
    return name


class SubAgent(ABC):
    """Base class for sub-agents with iterative tool use.

    Provides a unified iteration loop with:
    - Token tracking and reporting
    - Progress reporting
    - Context saving for debugging
    - Consistent logging
    """

    def __init__(self, config: SubAgentConfig) -> None:
        self.config = config
        self._client = None

    @property
    def client(self):
        """Lazily create the Bedrock client."""
        if self._client is None:
            client_start = time.perf_counter()
            self._client = create_bedrock_client()
            elapsed_ms = (time.perf_counter() - client_start) * 1000
            logger.info(f"{self.config.tool_name}: Bedrock client created in {elapsed_ms:.1f}ms")
        return self._client

    @abstractmethod
    def execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool call from the LLM and return the result as a string."""

    def process_response_block(self, block: Any, iteration: int, max_iterations: int) -> dict[str, Any] | None:
        """Process a response block for special handling. Override if needed.

        Returns tool result dict if the block was processed, None otherwise.
        """
        return None

    def run(self, initial_message: str) -> SubAgentResult:
        """Run the sub-agent iteration loop."""
        messages: list[dict[str, Any]] = [{"role": "user", "content": initial_message}]
        total_input_tokens = 0
        total_output_tokens = 0
        current_iteration = 0
        all_tool_calls: list[dict[str, Any]] = []

        # Cache breakpoints: system prompt and tools (static per sub-agent)
        system = [{"type": "text", "text": self.config.system_prompt, "cache_control": {"type": "ephemeral"}}]
        tools = [*self.config.tools] if self.config.tools else []
        if tools:
            tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral"}}

        response = None
        try:
            for iteration in range(self.config.max_iterations):
                current_iteration = iteration + 1
                iter_start = time.perf_counter()

                logger.info(
                    f"{self.config.tool_name} sub-agent: iteration {current_iteration}/{self.config.max_iterations}"
                )

                get_context().report_progress(
                    SubAgentProgress(
                        tool_name=self.config.tool_name,
                        iteration=current_iteration,
                        max_iterations=self.config.max_iterations,
                        status="thinking",
                    )
                )

                # Cache breakpoint: last message
                add_message_cache_breakpoint(messages)

                # On the final iteration, omit tools and inject a synthesis
                # prompt so the LLM produces a useful answer instead of trying
                # to call more tools whose results would never be consumed.
                is_final_iteration = current_iteration == self.config.max_iterations
                iter_tools = tools
                if is_final_iteration:
                    iter_tools = []
                    messages = [
                        *messages,
                        {
                            "role": "user",
                            "content": "Synthesize your final answer from the information gathered so far.",
                        },
                    ]

                llm_start = time.perf_counter()
                response = self.client.messages.create(
                    model=get_model_id(),
                    max_tokens=self.config.max_tokens,
                    system=system,
                    messages=messages,
                    tools=iter_tools,
                )
                llm_elapsed_ms = (time.perf_counter() - llm_start) * 1000

                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                cache_creation = getattr(response.usage, "cache_creation_input_tokens", 0) or 0
                cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
                total_input_tokens += input_tokens
                total_output_tokens += output_tokens

                logger.info(
                    f"{self.config.tool_name} [iter {current_iteration}]: "
                    f"LLM {llm_elapsed_ms:.1f}ms, tokens in={input_tokens} out={output_tokens}"
                )

                get_context().report_token_usage(
                    SubAgentTokenUsage(
                        tool_name=self.config.tool_name,
                        input_tokens=input_tokens + cache_creation + cache_read,
                        output_tokens=output_tokens,
                        iteration=current_iteration,
                        cache_creation_input_tokens=cache_creation,
                        cache_read_input_tokens=cache_read,
                    )
                )

                has_tool_use = any(hasattr(block, "type") and block.type == "tool_use" for block in response.content)

                if response.stop_reason == "end_of_turn" or not has_tool_use:
                    iter_elapsed_ms = (time.perf_counter() - iter_start) * 1000
                    logger.info(
                        f"{self.config.tool_name}: completed after {current_iteration} iterations "
                        f"in {iter_elapsed_ms:.1f}ms (stop_reason={response.stop_reason}, has_tool_use={has_tool_use})"
                    )
                    get_context().report_progress(
                        SubAgentProgress(
                            tool_name=self.config.tool_name,
                            iteration=current_iteration,
                            max_iterations=self.config.max_iterations,
                            status="completed",
                        )
                    )
                    text_parts = [block.text for block in response.content if hasattr(block, "text")]
                    return SubAgentResult(
                        analysis="\n".join(text_parts) if text_parts else "No analysis provided",
                        input_tokens=total_input_tokens,
                        output_tokens=total_output_tokens,
                        iterations_used=current_iteration,
                        tool_calls=all_tool_calls or None,
                    )

                messages.append({"role": "assistant", "content": response.content})

                tool_results: list[dict[str, Any]] = []
                iteration_tool_calls: list[str] = []

                for block in response.content:
                    special_result = self.process_response_block(block, current_iteration, self.config.max_iterations)
                    if special_result:
                        tool_results.append(special_result)

                for block in response.content:
                    if hasattr(block, "type") and block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        display_call = _fmt_tool_call(tool_name, tool_input)
                        iteration_tool_calls.append(display_call)
                        all_tool_calls.append({"tool": tool_name, "input": tool_input})

                        logger.info(
                            f"{self.config.tool_name} [iter {current_iteration}]: calling tool '{display_call}'"
                        )

                        get_context().report_progress(
                            SubAgentProgress(
                                tool_name=self.config.tool_name,
                                iteration=current_iteration,
                                max_iterations=self.config.max_iterations,
                                current_tool=display_call,
                                tool_calls=iteration_tool_calls.copy(),
                                status="running_tool",
                            )
                        )

                        try:
                            tool_start = time.perf_counter()
                            result = self.execute_tool(tool_name, tool_input)
                            tool_elapsed_ms = (time.perf_counter() - tool_start) * 1000
                            result_preview = result[:200] + "..." if len(result) > 200 else result
                            logger.info(
                                f"{self.config.tool_name}: tool '{tool_name}' executed in {tool_elapsed_ms:.1f}ms"
                                f" | result: {result_preview}"
                            )
                            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
                        except Exception as e:
                            logger.warning(f"Tool {tool_name} failed: {e}")
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": f"Error: {e}",
                                    "is_error": True,
                                }
                            )

                if tool_results:
                    messages.append({"role": "user", "content": tool_results})

                    get_context().report_progress(
                        SubAgentProgress(
                            tool_name=self.config.tool_name,
                            iteration=current_iteration,
                            max_iterations=self.config.max_iterations,
                            tool_calls=iteration_tool_calls.copy(),
                            status="reasoning",
                        )
                    )

            logger.warning(f"{self.config.tool_name}: max iterations ({self.config.max_iterations}) reached")
            text_parts = [block.text for block in response.content if hasattr(block, "text")] if response else []
            return SubAgentResult(
                analysis="\n".join(text_parts) if text_parts else "Max iterations reached",
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                iterations_used=self.config.max_iterations,
                tool_calls=all_tool_calls or None,
            )

        except Exception as e:
            logger.exception(f"Error in {self.config.tool_name} sub-agent")
            return SubAgentResult(
                analysis=f"Error calling Opus sub-agent: {e}",
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                iterations_used=current_iteration,
            )
