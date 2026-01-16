"""Agent service for running the Rossum Agent."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Literal

from rossum_agent.agent.core import RossumAgent, create_agent
from rossum_agent.agent.memory import AgentMemory
from rossum_agent.agent.models import AgentConfig, AgentStep, StepType
from rossum_agent.api.models.schemas import (
    DocumentContent,
    ImageContent,
    StepEvent,
    StreamDoneEvent,
    SubAgentProgressEvent,
    SubAgentTextEvent,
)
from rossum_agent.prompts import get_system_prompt
from rossum_agent.rossum_mcp_integration import connect_mcp_server
from rossum_agent.streamlit_app.response_formatting import get_display_tool_name
from rossum_agent.tools import (
    SubAgentProgress,
    SubAgentText,
    set_mcp_connection,
    set_output_dir,
    set_progress_callback,
    set_text_callback,
)
from rossum_agent.url_context import extract_url_context, format_context_for_prompt
from rossum_agent.utils import create_session_output_dir, set_session_output_dir

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from anthropic.types import ImageBlockParam, TextBlockParam

    from rossum_agent.agent.types import UserContent

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
        status=progress.status,
    )


def _create_tool_start_event(step: AgentStep, current_tool: str) -> StepEvent:
    """Create a tool_start event from an AgentStep."""
    current_tool_args = None
    for tc in step.tool_calls:
        if tc.name == current_tool:
            current_tool_args = tc.arguments
            break
    display_name = get_display_tool_name(current_tool, current_tool_args)
    return StepEvent(
        type="tool_start",
        step_number=step.step_number,
        tool_name=display_name,
        tool_arguments=current_tool_args,
        tool_progress=step.tool_progress,
    )


def _create_tool_result_event(step: AgentStep) -> StepEvent:
    """Create a tool_result event from an AgentStep."""
    last_result = step.tool_results[-1]
    return StepEvent(
        type="tool_result",
        step_number=step.step_number,
        tool_name=last_result.name,
        result=last_result.content,
        is_error=last_result.is_error,
    )


def convert_step_to_event(step: AgentStep) -> StepEvent:
    """Convert an AgentStep to a StepEvent for SSE streaming.

    Extended thinking mode produces three distinct content types:
    - "thinking": Model's chain-of-thought reasoning (from thinking blocks)
    - "intermediate": Model's response text before tool calls
    - "final_answer": Model's final response (no more tool calls)

    Per Claude's extended thinking API, thinking blocks contain internal reasoning
    while text blocks contain the actual response. Both are streamed separately.
    """
    if step.error:
        event = StepEvent(type="error", step_number=step.step_number, content=step.error, is_final=True)
    elif step.is_final and step.final_answer:
        event = StepEvent(type="final_answer", step_number=step.step_number, content=step.final_answer, is_final=True)
    elif step.step_type == StepType.INTERMEDIATE and step.accumulated_text is not None:
        event = StepEvent(
            type="intermediate", step_number=step.step_number, content=step.accumulated_text, is_streaming=True
        )
    elif step.step_type == StepType.FINAL_ANSWER and step.accumulated_text is not None:
        event = StepEvent(
            type="final_answer", step_number=step.step_number, content=step.accumulated_text, is_streaming=True
        )
    elif step.current_tool and step.tool_progress:
        event = _create_tool_start_event(step, step.current_tool)
    elif step.tool_results and not step.is_streaming:
        event = _create_tool_result_event(step)
    elif step.step_type == StepType.THINKING or step.thinking is not None:
        event = StepEvent(
            type="thinking", step_number=step.step_number, content=step.thinking, is_streaming=step.is_streaming
        )
    else:
        event = StepEvent(type="thinking", step_number=step.step_number, content=None, is_streaming=step.is_streaming)

    logger.info(f"StepEvent: type={event.type}, step={event.step_number}, is_streaming={event.is_streaming}")
    return event


class AgentService:
    """Service for running the Rossum Agent.

    Manages MCP connection lifecycle and agent execution for API requests.
    """

    def __init__(self) -> None:
        """Initialize agent service."""
        self._output_dir: Path | None = None
        self._sub_agent_queue: asyncio.Queue[SubAgentProgressEvent | SubAgentTextEvent] | None = None
        self._last_memory: AgentMemory | None = None

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
        documents: list[DocumentContent] | None = None,
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
        if documents:
            logger.info(f"Including {len(documents)} documents in the prompt")

        self._output_dir = create_session_output_dir()
        set_session_output_dir(self._output_dir)
        set_output_dir(self._output_dir)
        logger.info(f"Created session output directory: {self._output_dir}")

        if documents:
            self._save_documents_to_output_dir(documents)

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

                user_content = self._build_user_content(prompt, images, documents)

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

                    self._last_memory = agent.memory

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
            set_output_dir(None)
            self._sub_agent_queue = None

    def _save_documents_to_output_dir(self, documents: list[DocumentContent]) -> None:
        """Save uploaded documents to the output directory.

        Args:
            documents: List of documents to save.
        """
        import base64  # noqa: PLC0415 - import here to avoid circular import at module level

        if self._output_dir is None:
            logger.warning("Cannot save documents: output directory not set")
            return

        for doc in documents:
            file_path = self._output_dir / doc.filename
            try:
                file_data = base64.b64decode(doc.data)
                file_path.write_bytes(file_data)
                logger.info(f"Saved document to {file_path}")
            except Exception as e:
                logger.error(f"Failed to save document {doc.filename}: {e}")

    def _build_user_content(
        self, prompt: str, images: list[ImageContent] | None, documents: list[DocumentContent] | None = None
    ) -> UserContent:
        """Build user content for the agent, optionally including images and documents.

        Args:
            prompt: The user's text prompt.
            images: Optional list of images to include.
            documents: Optional list of documents (paths are included in prompt).

        Returns:
            Either a plain string (text-only) or a list of content blocks (multimodal).
        """
        if not images and not documents:
            return prompt

        content: list[ImageBlockParam | TextBlockParam] = []
        if images:
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
        if documents and self._output_dir:
            doc_paths = [str(self._output_dir / doc.filename) for doc in documents]
            doc_info = "\n".join(f"- {path}" for path in doc_paths)
            content.append({"type": "text", "text": f"[Uploaded documents available for processing:\n{doc_info}]"})
        content.append({"type": "text", "text": prompt})
        return content

    def _restore_conversation_history(self, agent: RossumAgent, history: list[dict[str, Any]]) -> None:
        """Restore conversation history to the agent.

        Args:
            agent: The RossumAgent instance.
            history: List of step dicts with 'type' key indicating step type.
                     Supports both new format (with 'type') and legacy format (with 'role').
        """
        if not history:
            return

        first_item = history[0]
        if "type" in first_item and first_item["type"] in ("task_step", "memory_step"):
            agent.memory = AgentMemory.from_dict(history)
        else:
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

        result: list[ImageBlockParam | TextBlockParam] = []
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
        documents: list[DocumentContent] | None = None,
    ) -> list[dict[str, Any]]:
        """Build updated conversation history after agent execution.

        Stores task steps and assistant text responses, but strips out tool calls
        and tool results to keep context lean for multi-turn conversations.

        Args:
            existing_history: Previous conversation history (ignored if memory available).
            user_prompt: The user's prompt that was just processed.
            final_response: The agent's final response, if any.
            images: Optional list of images included with the user prompt.
            documents: Optional list of documents included with the user prompt.
        """
        if self._last_memory is not None:
            lean_history: list[dict[str, Any]] = []
            for step_dict in self._last_memory.to_dict():
                if step_dict.get("type") == "task_step":
                    lean_history.append(step_dict)
                elif step_dict.get("type") == "memory_step":
                    text = step_dict.get("text")
                    thinking_blocks = step_dict.get("thinking_blocks", [])
                    if text or thinking_blocks:
                        lean_history.append(
                            {
                                "type": "memory_step",
                                "step_number": step_dict.get("step_number", 0),
                                "text": text,
                                "tool_calls": [],
                                "tool_results": [],
                                "thinking_blocks": thinking_blocks,
                            }
                        )
            return lean_history

        updated = list(existing_history)
        user_content = self._build_user_content(user_prompt, images)
        if documents:
            doc_names = ", ".join(doc.filename for doc in documents)
            if isinstance(user_content, str):
                user_content = f"[Uploaded documents: {doc_names}]\n\n{user_content}"
            else:
                user_content.insert(0, {"type": "text", "text": f"[Uploaded documents: {doc_names}]"})
        updated.append({"role": "user", "content": user_content})
        if final_response:
            updated.append({"role": "assistant", "content": final_response})
        return updated
