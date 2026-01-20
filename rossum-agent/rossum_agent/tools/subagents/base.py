"""Shared base module for sub-agents.

Provides common infrastructure for sub-agents that use iterative LLM calls with tool use:
- Unified iteration loop with token tracking
- Context saving for debugging
- Consistent logging patterns
- Progress and token usage reporting
"""

from __future__ import annotations

import json
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
    get_output_dir,
    report_progress,
    report_token_usage,
)

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


def save_iteration_context(
    tool_name: str,
    iteration: int,
    max_iterations: int,
    messages: list[dict[str, Any]],
    system_prompt: str,
    tools: list[dict[str, Any]],
    max_tokens: int,
) -> None:
    """Save agent input context to file for debugging.

    Args:
        tool_name: Name of the sub-agent tool (e.g., "debug_hook", "patch_schema").
        iteration: Current iteration number (1-indexed).
        max_iterations: Maximum number of iterations.
        messages: Current conversation messages.
        system_prompt: System prompt used.
        tools: Tool definitions.
        max_tokens: Max tokens setting.
    """
    try:
        output_dir = get_output_dir()
        context_file = output_dir / f"{tool_name}_context_iter_{iteration}.json"
        context_data = {
            "iteration": iteration,
            "max_iterations": max_iterations,
            "model": get_model_id(),
            "max_tokens": max_tokens,
            "system_prompt": system_prompt,
            "messages": messages,
            "tools": tools,
        }
        context_file.write_text(json.dumps(context_data, indent=2, default=str))
        logger.info(f"{tool_name} sub-agent: saved context to {context_file}")
    except Exception as e:
        logger.warning(f"Failed to save {tool_name} context: {e}")


class SubAgent(ABC):
    """Base class for sub-agents with iterative tool use.

    Provides a unified iteration loop with:
    - Token tracking and reporting
    - Progress reporting
    - Context saving for debugging
    - Consistent logging
    """

    def __init__(self, config: SubAgentConfig) -> None:
        """Initialize the sub-agent.

        Args:
            config: Configuration for the sub-agent.
        """
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
        """Execute a tool call from the LLM.

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Input arguments for the tool.

        Returns:
            Tool result as a string.
        """

    @abstractmethod
    def process_response_block(self, block: Any, iteration: int, max_iterations: int) -> dict[str, Any] | None:
        """Process a response block for special handling (e.g., web search).

        Args:
            block: Response content block.
            iteration: Current iteration number (1-indexed).
            max_iterations: Maximum iterations.

        Returns:
            Tool result dict if the block was processed, None otherwise.
        """

    def run(self, initial_message: str) -> SubAgentResult:
        """Run the sub-agent iteration loop."""
        messages: list[dict[str, Any]] = [{"role": "user", "content": initial_message}]
        total_input_tokens = 0
        total_output_tokens = 0
        current_iteration = 0

        response = None
        try:
            for iteration in range(self.config.max_iterations):
                current_iteration = iteration + 1
                iter_start = time.perf_counter()

                logger.info(
                    f"{self.config.tool_name} sub-agent: iteration {current_iteration}/{self.config.max_iterations}"
                )

                report_progress(
                    SubAgentProgress(
                        tool_name=self.config.tool_name,
                        iteration=current_iteration,
                        max_iterations=self.config.max_iterations,
                        status="thinking",
                    )
                )

                save_iteration_context(
                    tool_name=self.config.tool_name,
                    iteration=current_iteration,
                    max_iterations=self.config.max_iterations,
                    messages=messages,
                    system_prompt=self.config.system_prompt,
                    tools=self.config.tools,
                    max_tokens=self.config.max_tokens,
                )

                llm_start = time.perf_counter()
                response = self.client.messages.create(
                    model=get_model_id(),
                    max_tokens=self.config.max_tokens,
                    system=self.config.system_prompt,
                    messages=messages,
                    tools=self.config.tools,
                )
                llm_elapsed_ms = (time.perf_counter() - llm_start) * 1000

                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                total_input_tokens += input_tokens
                total_output_tokens += output_tokens

                logger.info(
                    f"{self.config.tool_name} [iter {current_iteration}]: "
                    f"LLM {llm_elapsed_ms:.1f}ms, tokens in={input_tokens} out={output_tokens}"
                )

                report_token_usage(
                    SubAgentTokenUsage(
                        tool_name=self.config.tool_name,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        iteration=current_iteration,
                    )
                )

                has_tool_use = any(hasattr(block, "type") and block.type == "tool_use" for block in response.content)

                if response.stop_reason == "end_of_turn" or not has_tool_use:
                    iter_elapsed_ms = (time.perf_counter() - iter_start) * 1000
                    logger.info(
                        f"{self.config.tool_name}: completed after {current_iteration} iterations "
                        f"in {iter_elapsed_ms:.1f}ms (stop_reason={response.stop_reason}, has_tool_use={has_tool_use})"
                    )
                    report_progress(
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
                        iteration_tool_calls.append(tool_name)

                        logger.info(f"{self.config.tool_name} [iter {current_iteration}]: calling tool '{tool_name}'")

                        report_progress(
                            SubAgentProgress(
                                tool_name=self.config.tool_name,
                                iteration=current_iteration,
                                max_iterations=self.config.max_iterations,
                                current_tool=tool_name,
                                tool_calls=iteration_tool_calls.copy(),
                                status="running_tool",
                            )
                        )

                        try:
                            tool_start = time.perf_counter()
                            result = self.execute_tool(tool_name, tool_input)
                            tool_elapsed_ms = (time.perf_counter() - tool_start) * 1000
                            logger.info(
                                f"{self.config.tool_name}: tool '{tool_name}' executed in {tool_elapsed_ms:.1f}ms"
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

            logger.warning(f"{self.config.tool_name}: max iterations ({self.config.max_iterations}) reached")
            text_parts = [block.text for block in response.content if hasattr(block, "text")] if response else []
            return SubAgentResult(
                analysis="\n".join(text_parts) if text_parts else "Max iterations reached",
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                iterations_used=self.config.max_iterations,
            )

        except Exception as e:
            logger.exception(f"Error in {self.config.tool_name} sub-agent")
            return SubAgentResult(
                analysis=f"Error calling Opus sub-agent: {e}",
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                iterations_used=current_iteration,
            )
