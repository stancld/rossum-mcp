"""Agent service for running the Rossum Agent."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Literal

from rossum_agent.agent.core import RossumAgent, create_agent
from rossum_agent.agent.models import AgentConfig, AgentStep
from rossum_agent.api.models.schemas import (
    ImageContent,
    StepEvent,
    StreamDoneEvent,
    SubAgentProgressEvent,
    SubAgentTextEvent,
)
from rossum_agent.internal_tools import (
    SubAgentProgress,
    SubAgentText,
    set_mcp_connection,
    set_progress_callback,
    set_text_callback,
)
from rossum_agent.mcp_tools import connect_mcp_server
from rossum_agent.prompts import get_system_prompt
from rossum_agent.url_context import extract_url_context, format_context_for_prompt
from rossum_agent.utils import create_session_output_dir, set_session_output_dir

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from rossum_agent.agent.types import ContentBlock, UserContent

logger = logging.getLogger(__name__)


def convert_sub_agent_progress_to_event(progress: SubAgentProgress) -> SubAgentProgressEvent:
    """Convert a SubAgentProgress to a SubAgentProgressEvent for SSE streaming.

    Args:
        progress: The SubAgentProgress from the internal tool.

    Returns:
        SubAgentProgressEvent suitable for SSE transmission.
    """
    return SubAgentProgressEvent(
        tool_name=progress.tool_name,
        iteration=progress.iteration,
        max_iterations=progress.max_iterations,
        current_tool=progress.current_tool,
        tool_calls=progress.tool_calls,
        status=progress.status,  # type: ignore[arg-type]
    )


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
        self._sub_agent_queue: asyncio.Queue[SubAgentProgressEvent | SubAgentTextEvent] | None = None

    @property
    def output_dir(self) -> Path | None:
        """Get the output directory for the current run."""
        return self._output_dir

    def _on_sub_agent_progress(self, progress: SubAgentProgress) -> None:
        """Callback for sub-agent progress updates.

        Converts the progress to an event and puts it on the queue for streaming.
        """
        if self._sub_agent_queue is not None:
            event = convert_sub_agent_progress_to_event(progress)
            try:
                self._sub_agent_queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Sub-agent progress queue full, dropping event")

    def _on_sub_agent_text(self, text: SubAgentText) -> None:
        """Callback for sub-agent text streaming.

        Converts the text to an event and puts it on the queue for streaming.
        """
        if self._sub_agent_queue is not None:
            event = SubAgentTextEvent(tool_name=text.tool_name, text=text.text, is_final=text.is_final)
            try:
                self._sub_agent_queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Sub-agent text queue full, dropping event")

    async def run_agent(
        self,
        prompt: str,
        conversation_history: list[dict[str, Any]],
        rossum_api_token: str,
        rossum_api_base_url: str,
        mcp_mode: Literal["read-only", "read-write"] = "read-only",
        rossum_url: str | None = None,
        images: list[ImageContent] | None = None,
    ) -> AsyncIterator[StepEvent | StreamDoneEvent | SubAgentProgressEvent | SubAgentTextEvent]:
        """Run the agent with a new prompt.

        Creates a fresh MCP connection, initializes the agent with conversation
        history, and streams step events.

        Yields:
            StepEvent objects during execution, SubAgentProgressEvent for sub-agent progress,
            SubAgentTextEvent for sub-agent text streaming, StreamDoneEvent at the end.
        """
        logger.info(f"Starting agent run with {len(conversation_history)} history messages")
        if images:
            logger.info(f"Including {len(images)} images in the prompt")

        self._output_dir = create_session_output_dir()
        set_session_output_dir(self._output_dir)
        logger.info(f"Created session output directory: {self._output_dir}")

        self._sub_agent_queue = asyncio.Queue(maxsize=100)
        set_progress_callback(self._on_sub_agent_progress)
        set_text_callback(self._on_sub_agent_text)

        system_prompt = get_system_prompt()
        url_context = extract_url_context(rossum_url)
        if not url_context.is_empty():
            context_section = format_context_for_prompt(url_context)
            system_prompt = system_prompt + "\n\n---\n" + context_section

        try:
            async with connect_mcp_server(
                rossum_api_token=rossum_api_token,
                rossum_api_base_url=rossum_api_base_url,
                mcp_mode=mcp_mode,
            ) as mcp_connection:
                agent = await create_agent(
                    mcp_connection=mcp_connection, system_prompt=system_prompt, config=AgentConfig()
                )

                set_mcp_connection(mcp_connection, asyncio.get_event_loop())

                self._restore_conversation_history(agent, conversation_history)

                total_steps = 0
                total_input_tokens = 0
                total_output_tokens = 0

                user_content = self._build_user_content(prompt, images)

                try:
                    async for step in agent.run(user_content):
                        while not self._sub_agent_queue.empty():
                            try:
                                sub_event = self._sub_agent_queue.get_nowait()
                                yield sub_event
                            except asyncio.QueueEmpty:
                                break

                        yield convert_step_to_event(step)

                        if not step.is_streaming:
                            total_steps = step.step_number
                            total_input_tokens = agent._total_input_tokens
                            total_output_tokens = agent._total_output_tokens

                    while not self._sub_agent_queue.empty():
                        try:
                            sub_event = self._sub_agent_queue.get_nowait()
                            yield sub_event
                        except asyncio.QueueEmpty:
                            break

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
        finally:
            set_progress_callback(None)
            set_text_callback(None)
            self._sub_agent_queue = None

    def _build_user_content(self, prompt: str, images: list[ImageContent] | None) -> UserContent:
        """Build user content for the agent, optionally including images.

        Args:
            prompt: The user's text prompt.
            images: Optional list of images to include.

        Returns:
            Either a plain string (text-only) or a list of content blocks (multimodal).
        """
        if not images:
            return prompt

        content: list[ContentBlock] = []
        for img in images:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img.media_type,
                        "data": img.data,
                    },
                }
            )
        content.append({"type": "text", "text": prompt})
        return content

    def _restore_conversation_history(self, agent: RossumAgent, history: list[dict[str, Any]]) -> None:
        """Restore conversation history to the agent.

        Args:
            agent: The RossumAgent instance.
            history: List of message dicts with 'role' and 'content' keys.
                     Content can be a string or a list of content blocks (for multimodal).
        """
        for msg in history:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                user_content = self._parse_stored_content(content)
                agent.add_user_message(user_content)
            elif role == "assistant":
                agent.add_assistant_message(content)

    def _parse_stored_content(self, content: str | list[dict[str, Any]]) -> UserContent:
        """Parse stored content back into UserContent format.

        Args:
            content: Either a string or a list of content block dicts.

        Returns:
            UserContent suitable for the agent.
        """
        if isinstance(content, str):
            return content

        result: list[ContentBlock] = []
        for block in content:
            block_type = block.get("type")
            if block_type == "image":
                source = block.get("source", {})
                result.append(
                    {
                        "type": "image",
                        "source": {
                            "type": source.get("type", "base64"),
                            "media_type": source.get("media_type", "image/png"),
                            "data": source.get("data", ""),
                        },
                    }
                )
            elif block_type == "text":
                result.append({"type": "text", "text": block.get("text", "")})

        return result if result else ""

    def build_updated_history(
        self,
        existing_history: list[dict[str, Any]],
        user_prompt: str,
        final_response: str | None,
        images: list[ImageContent] | None = None,
    ) -> list[dict[str, Any]]:
        """Build updated conversation history after agent execution.

        Args:
            existing_history: Previous conversation history.
            user_prompt: The user's prompt that was just processed.
            final_response: The agent's final response, if any.
            images: Optional list of images included with the user prompt.
        """
        updated = list(existing_history)
        user_content = self._build_user_content(user_prompt, images)
        updated.append({"role": "user", "content": user_content})
        if final_response:
            updated.append({"role": "assistant", "content": final_response})
        return updated
