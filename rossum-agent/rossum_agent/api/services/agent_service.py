"""Agent service for running the Rossum Agent."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal

from rossum_agent.agent.core import RossumAgent, create_agent
from rossum_agent.agent.models import AgentConfig, AgentStep
from rossum_agent.api.models.schemas import StepEvent, StreamDoneEvent
from rossum_agent.mcp_tools import connect_mcp_server
from rossum_agent.prompts import get_system_prompt
from rossum_agent.url_context import extract_url_context, format_context_for_prompt
from rossum_agent.utils import create_session_output_dir, set_session_output_dir

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

logger = logging.getLogger(__name__)


def convert_step_to_event(step: AgentStep) -> StepEvent:
    """Convert an AgentStep to a StepEvent for SSE streaming.

    Args:
        step: The AgentStep from the agent.

    Returns:
        StepEvent suitable for SSE transmission.
    """
    if step.error:
        return StepEvent(type="error", step_number=step.step_number, content=step.error, is_final=True)

    if step.is_final and step.final_answer:
        return StepEvent(type="final_answer", step_number=step.step_number, content=step.final_answer, is_final=True)

    if step.current_tool and step.tool_progress:
        return StepEvent(
            type="tool_start",
            step_number=step.step_number,
            tool_name=step.current_tool,
            tool_progress=step.tool_progress,
        )

    if step.tool_results and not step.is_streaming:
        last_result = step.tool_results[-1]
        return StepEvent(
            type="tool_result",
            step_number=step.step_number,
            tool_name=last_result.name,
            result=last_result.content,
            is_error=last_result.is_error,
        )

    return StepEvent(
        type="thinking", step_number=step.step_number, content=step.thinking, is_streaming=step.is_streaming
    )


class AgentService:
    """Service for running the Rossum Agent.

    Manages MCP connection lifecycle and agent execution for API requests.
    """

    def __init__(self) -> None:
        """Initialize agent service."""
        self._output_dir: Path | None = None

    @property
    def output_dir(self) -> Path | None:
        """Get the output directory for the current run."""
        return self._output_dir

    async def run_agent(
        self,
        prompt: str,
        conversation_history: list[dict[str, Any]],
        rossum_api_token: str,
        rossum_api_base_url: str,
        mcp_mode: Literal["read-only", "read-write"] = "read-only",
        rossum_url: str | None = None,
    ) -> AsyncIterator[StepEvent | StreamDoneEvent]:
        """Run the agent with a new prompt.

        Creates a fresh MCP connection, initializes the agent with conversation
        history, and streams step events.

        Yields:
            StepEvent objects during execution, StreamDoneEvent at the end.
        """
        logger.info(f"Starting agent run with {len(conversation_history)} history messages")

        self._output_dir = create_session_output_dir()
        set_session_output_dir(self._output_dir)
        logger.info(f"Created session output directory: {self._output_dir}")

        system_prompt = get_system_prompt()
        url_context = extract_url_context(rossum_url)
        if not url_context.is_empty():
            context_section = format_context_for_prompt(url_context)
            system_prompt = system_prompt + "\n\n---\n" + context_section

        async with connect_mcp_server(
            rossum_api_token=rossum_api_token,
            rossum_api_base_url=rossum_api_base_url,
            mcp_mode=mcp_mode,
        ) as mcp_connection:
            agent = await create_agent(
                mcp_connection=mcp_connection, system_prompt=system_prompt, config=AgentConfig()
            )

            self._restore_conversation_history(agent, conversation_history)

            total_steps = 0
            total_input_tokens = 0
            total_output_tokens = 0

            try:
                async for step in agent.run(prompt):
                    yield convert_step_to_event(step)

                    if not step.is_streaming:
                        total_steps = step.step_number
                        total_input_tokens = agent._total_input_tokens
                        total_output_tokens = agent._total_output_tokens

                yield StreamDoneEvent(
                    total_steps=total_steps, input_tokens=total_input_tokens, output_tokens=total_output_tokens
                )

            except Exception as e:
                logger.error(f"Agent execution failed: {e}", exc_info=True)
                yield StepEvent(
                    type="error",
                    step_number=total_steps + 1,
                    content=f"Agent execution failed: {e}",
                    is_final=True,
                )

    def _restore_conversation_history(self, agent: RossumAgent, history: list[dict[str, Any]]) -> None:
        """Restore conversation history to the agent.

        Args:
            agent: The RossumAgent instance.
            history: List of message dicts with 'role' and 'content' keys.
        """
        for msg in history:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                agent.add_user_message(content)
            elif role == "assistant":
                agent.add_assistant_message(content)

    def build_updated_history(
        self, existing_history: list[dict[str, Any]], user_prompt: str, final_response: str | None
    ) -> list[dict[str, Any]]:
        """Build updated conversation history after agent execution.

        Args:
            existing_history: Previous conversation history.
            user_prompt: The user's prompt that was just processed.
            final_response: The agent's final response, if any.
        """
        updated = list(existing_history)
        updated.append({"role": "user", "content": user_prompt})
        if final_response:
            updated.append({"role": "assistant", "content": final_response})
        return updated
