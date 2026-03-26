"""Message endpoints with SSE streaming."""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import logging
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from anthropic.types import TextBlock
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from rossum_agent.agent.memory import AgentMemory
from rossum_agent.api.commands import CommandContext, ParsedCommand, execute_command, parse_command
from rossum_agent.api.dependencies import (
    RossumCredentials,
    get_agent_service,
    get_chat_service,
    get_validated_credentials,
)
from rossum_agent.api.models.schemas import (
    AgentQuestionEvent,
    CancelResponse,
    DocumentContent,
    ErrorResponse,
    FileCreatedEvent,
    ImageContent,
    MCPMode,
    MessageRequest,
    Persona,
    StepEvent,
    StreamDoneEvent,
    SubAgentProgressEvent,
    SubAgentTextEvent,
    TaskSnapshotEvent,
)
from rossum_agent.api.services.agent_service import AgentService
from rossum_agent.api.services.chat_service import ChatService
from rossum_agent.bedrock_client import create_async_bedrock_client, get_small_model_id
from rossum_agent.change_tracking.store import CommitStore
from rossum_agent.mermaid_sanitizer import sanitize_mermaid_in_markdown
from rossum_agent.redis_client import RedisConnection
from rossum_agent.storage import ChatData
from rossum_agent.url_context import extract_url_context

# To prevent (legacy) proxy servers from dropping connections during long periods of thinking,
# we are sending SSE_KEEPALIVE_COMMENT every SSE_KEEPALIVE_INTERVAL as per recommendation:
# https://html.spec.whatwg.org/multipage/server-sent-events.html#authoring-notes
SSE_KEEPALIVE_INTERVAL = 15
SSE_KEEPALIVE_COMMENT = ": keepalive\n\n"

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/chats", tags=["messages"])


def _format_sse_event(event_type: str, data: str) -> str:
    """Format an SSE event string."""
    return f"event: {event_type}\ndata: {data}\n\n"


async def _generate_chat_summary(
    user_prompt: str, previous_summary: str | None = None, url_context: str | None = None
) -> str | None:
    """Generate a one-line chat summary via Claude Haiku. Updates previous summary if available."""
    try:
        context_prefix = f"Context: {url_context}\n" if url_context else ""
        if previous_summary:
            prompt = (
                f"{context_prefix}"
                f"Current summary: {previous_summary}\n"
                f"New user message: {user_prompt[:500]}\n\n"
                f"Update the summary to cover the full conversation. One sentence, max 10 words."
            )
        else:
            prompt = f"{context_prefix}Summarize this in one sentence (max 10 words): {user_prompt[:500]}"

        client = create_async_bedrock_client()
        response = await client.messages.create(
            model=get_small_model_id(),
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )
        text_block = next((b for b in response.content if isinstance(b, TextBlock)), None)
        return text_block.text.strip() if text_block else None
    except Exception as e:
        logger.warning(f"Failed to generate chat summary: {e}")
        return None


type AgentEvent = (
    StreamDoneEvent | SubAgentProgressEvent | SubAgentTextEvent | TaskSnapshotEvent | AgentQuestionEvent | StepEvent
)

_SSE_EVENT_NAMES = {
    SubAgentProgressEvent: "sub_agent_progress",
    SubAgentTextEvent: "sub_agent_text",
    TaskSnapshotEvent: "task_snapshot",
    AgentQuestionEvent: "agent_question",
}


@dataclass
class ProcessedEvent:
    sse_event: str | None = None
    done_event: StreamDoneEvent | None = None
    final_response_update: str | None = None
    is_step_complete: bool = False


@dataclass
class StreamState:
    final_response: str | None = None
    done_event: StreamDoneEvent | None = None


def _process_agent_event(event: AgentEvent) -> ProcessedEvent:
    if isinstance(event, StreamDoneEvent):
        return ProcessedEvent(done_event=event)

    event_name = _SSE_EVENT_NAMES.get(type(event), "step")

    # Sanitize mermaid blocks in final answers to fix common LLM syntax mistakes
    # (e.g. unquoted labels with parens/braces — see mermaid-js/mermaid#7002).
    if isinstance(event, StepEvent) and event.type == "final_answer" and not event.is_streaming and event.content:
        sanitized = sanitize_mermaid_in_markdown(event.content)
        if sanitized != event.content:
            event = event.model_copy(update={"content": sanitized})

    final_response = event.content if isinstance(event, StepEvent) and event.type == "final_answer" else None
    is_step_complete = (
        isinstance(event, StepEvent)
        and not event.is_streaming
        and event.type in ("tool_result", "final_answer", "error")
    )
    return ProcessedEvent(
        sse_event=_format_sse_event(event_name, event.model_dump_json()),
        final_response_update=final_response,
        is_step_complete=is_step_complete,
    )


def _yield_file_events(output_dir: Path | None, chat_id: str) -> Iterator[str]:
    """Yield SSE events for created files in the output directory."""
    if output_dir is None or not output_dir.exists():
        return
    for file_path in output_dir.iterdir():
        if file_path.is_file():
            file_event = FileCreatedEvent(
                filename=file_path.name, url=f"/api/v1/chats/{chat_id}/files/{file_path.name}"
            )
            yield _format_sse_event("file_created", file_event.model_dump_json())


def _save_chat_history(
    chat_service: ChatService,
    agent_service: AgentService,
    credentials: RossumCredentials,
    chat_id: str,
    chat_data: ChatData,
    history: list[dict],
    user_prompt: str,
    final_response: str | None,
    images: list[ImageContent] | None,
    documents: list[DocumentContent] | None,
    output_dir: Path | None,
    memory: AgentMemory | None,
    done_event: StreamDoneEvent | None = None,
    summary: str | None = None,
) -> None:
    """Persist updated conversation history after a successful agent run."""
    if done_event and done_event.config_commit_hash:
        chat_data.metadata.config_commits.append(done_event.config_commit_hash)
    if summary is not None:
        chat_data.metadata.summary = summary

    updated_history = agent_service.build_updated_history(
        existing_history=history,
        user_prompt=user_prompt,
        final_response=final_response,
        images=images,
        documents=documents,
        memory=memory,
    )
    chat_service.save_messages(
        user_id=credentials.user_id,
        chat_id=chat_id,
        messages=updated_history,
        output_dir=output_dir,
        metadata=chat_data.metadata,
    )


async def _stream_agent_response(
    *,
    request: Request,
    chat_id: str,
    user_prompt: str,
    message: MessageRequest,
    history: list[dict],
    credentials: RossumCredentials,
    agent_service: AgentService,
    mcp_mode: MCPMode,
    persona: Persona,
    images: list[ImageContent] | None,
    documents: list[DocumentContent] | None,
    state: StreamState,
    on_step_complete: Callable[[], None] | None = None,
) -> AsyncIterator[str]:
    watcher = asyncio.create_task(_watch_disconnect(request, chat_id, agent_service))

    try:
        agent_events = agent_service.run_agent(
            chat_id=chat_id,
            prompt=user_prompt,
            images=images,
            documents=documents,
            conversation_history=history,
            rossum_api_token=credentials.token,
            rossum_api_base_url=credentials.api_url,
            rossum_url=message.rossum_url,
            mcp_mode=mcp_mode,
            persona=persona,
        )
        async for event, is_keepalive in _with_sse_keepalive(agent_events):
            if is_keepalive:
                yield SSE_KEEPALIVE_COMMENT
                continue

            result = _process_agent_event(event)
            if result.done_event is not None:
                state.done_event = result.done_event
            if result.final_response_update and not (isinstance(event, StepEvent) and event.is_hook_output):
                state.final_response = result.final_response_update
            if result.sse_event is not None:
                yield result.sse_event
            if result.is_step_complete and on_step_complete is not None:
                on_step_complete()
    finally:
        watcher.cancel()


async def _watch_disconnect(request: Request, chat_id: str, agent_service: AgentService) -> None:
    """Poll for client disconnect and cancel the running agent."""
    try:
        while True:
            if await request.is_disconnected():
                logger.info(f"Client disconnected for chat {chat_id}, cancelling run")
                agent_service.cancel_run(chat_id)
                return
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        logger.debug(f"Disconnect watcher for chat {chat_id} cancelled")


def _resolve_mcp_mode(message: MessageRequest, chat_data: ChatData) -> MCPMode:
    """Resolve the effective MCP mode from the message and chat metadata."""
    if message.mcp_mode is not None:
        chat_data.metadata.mcp_mode = message.mcp_mode
        return message.mcp_mode
    return chat_data.metadata.mcp_mode


def _resolve_persona(message: MessageRequest, chat_data: ChatData) -> Persona:
    """Resolve the effective persona from the message and chat metadata."""
    if message.persona is not None:
        chat_data.metadata.persona = message.persona
    return chat_data.metadata.persona


async def _with_sse_keepalive(
    events: AsyncIterator[AgentEvent],
    interval: float = SSE_KEEPALIVE_INTERVAL,
) -> AsyncIterator[tuple[AgentEvent | None, bool]]:
    """Wrap an async event stream with periodic SSE keepalive signals.

    Yields (event, False) for real events and (None, True) for keepalive ticks.
    This prevents reverse proxies from closing idle connections during long
    model thinking pauses.

    Uses asyncio.wait() instead of asyncio.wait_for() to avoid cancelling the
    pending anext() task on timeout, which would corrupt the async generator state.

    Context is captured from each completed task and passed to the next one,
    so that context variables set by the async generator (e.g. output_dir)
    propagate across iterations.
    """
    ctx: contextvars.Context | None = None
    pending: asyncio.Task = asyncio.create_task(anext(events))
    try:
        while True:
            done, _ = await asyncio.wait({pending}, timeout=interval)
            if not done:
                yield None, True
                continue
            ctx = pending.get_context()
            try:
                event = pending.result()
            except StopAsyncIteration:
                break
            yield event, False
            pending = asyncio.create_task(anext(events), context=ctx)
    finally:
        if not pending.done():
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration):
                await pending


def _get_commit_store() -> CommitStore | None:
    """Create a CommitStore if Redis is available."""
    try:
        conn = RedisConnection()
        if conn.is_connected():
            return CommitStore(conn.client)
    except Exception as e:
        logger.warning(f"Commit store is unavailable: {e}")
    return None


def _handle_slash_command(
    command: ParsedCommand,
    chat_id: str,
    credentials: RossumCredentials,
    chat_service: ChatService,
) -> StreamingResponse:
    """Execute a slash command and return its result as an SSE stream."""
    commit_store = _get_commit_store() if command.name == "/list-commits" else None
    ctx = CommandContext(
        chat_id=chat_id,
        user_id=credentials.user_id,
        credentials_api_url=credentials.api_url,
        chat_service=chat_service,
        commit_store=commit_store,
        args=command.args,
    )

    async def command_event_generator() -> AsyncIterator[str]:
        result_text = await execute_command(command.name, ctx)
        step = StepEvent(type="final_answer", step_number=1, content=result_text, is_final=True)
        yield _format_sse_event("step", step.model_dump_json())
        done = StreamDoneEvent(total_steps=1, input_tokens=0, output_tokens=0)
        yield _format_sse_event("done", done.model_dump_json())

    return StreamingResponse(
        command_event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/{chat_id}/messages",
    response_class=StreamingResponse,
    responses={
        200: {"description": "SSE stream of agent step events", "content": {"text/event-stream": {}}},
        404: {"model": ErrorResponse, "description": "Chat not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
@limiter.limit("10/minute")
async def send_message(
    request: Request,
    chat_id: str,
    message: MessageRequest,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> StreamingResponse:
    """Send a message and stream the agent's response via SSE.

    If a previous request is still running for this chat, it will be cancelled
    before starting the new one. Client disconnects are also detected and will
    cancel the running agent.
    """
    chat_data = chat_service.get_chat_data(credentials.user_id, chat_id)
    if chat_data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    # Intercept slash commands — bypass the agent entirely
    command = parse_command(message.content)
    if command is not None:
        return _handle_slash_command(command, chat_id, credentials, chat_service)

    history = chat_data.messages
    mcp_mode = _resolve_mcp_mode(message, chat_data)
    persona = _resolve_persona(message, chat_data)
    user_prompt = message.content
    images: list[ImageContent] | None = message.images
    documents: list[DocumentContent] | None = message.documents

    async def event_generator() -> AsyncIterator[str]:
        state = StreamState()

        def _save_intermediate() -> None:
            """Persist current agent memory after each completed step."""
            memory = agent_service.get_last_memory(chat_id)
            if memory is None:
                return
            _save_chat_history(
                chat_service=chat_service,
                agent_service=agent_service,
                credentials=credentials,
                chat_id=chat_id,
                chat_data=chat_data,
                history=history,
                user_prompt=user_prompt,
                final_response=state.final_response,
                images=images,
                documents=documents,
                output_dir=agent_service.get_output_dir(chat_id),
                memory=memory,
            )

        try:
            async for chunk in _stream_agent_response(
                request=request,
                chat_id=chat_id,
                user_prompt=user_prompt,
                message=message,
                history=history,
                credentials=credentials,
                agent_service=agent_service,
                mcp_mode=mcp_mode,
                persona=persona,
                images=images,
                documents=documents,
                state=state,
                on_step_complete=_save_intermediate,
            ):
                yield chunk
        except asyncio.CancelledError:
            logger.info(f"Request cancelled for chat {chat_id}")
            return
        except Exception as e:
            logger.error(f"Error during agent execution: {e}", exc_info=True)
            error_event = StepEvent(type="error", step_number=0, content=str(e), is_final=True)
            yield _format_sse_event("step", error_event.model_dump_json())
            return

        output_dir = agent_service.get_output_dir(chat_id)
        memory = agent_service.pop_last_memory(chat_id)
        url_context = extract_url_context(message.rossum_url).to_context_string() or None
        summary = await _generate_chat_summary(
            user_prompt, previous_summary=chat_data.metadata.summary, url_context=url_context
        )

        _save_chat_history(
            chat_service=chat_service,
            agent_service=agent_service,
            credentials=credentials,
            chat_id=chat_id,
            chat_data=chat_data,
            history=history,
            user_prompt=user_prompt,
            final_response=state.final_response,
            images=images,
            documents=documents,
            output_dir=output_dir,
            memory=memory,
            done_event=state.done_event,
            summary=summary,
        )

        for file_event in _yield_file_events(output_dir, chat_id):
            yield file_event

        if state.done_event:
            yield _format_sse_event("done", state.done_event.model_dump_json())

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/{chat_id}/cancel",
    response_model=CancelResponse,
    responses={
        200: {"description": "Cancellation result"},
        404: {"model": ErrorResponse, "description": "Chat not found"},
    },
)
async def cancel_message(
    request: Request,
    chat_id: str,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> CancelResponse:
    """Cancel a running agent request for a chat."""
    if not chat_service.chat_exists(credentials.user_id, chat_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    cancelled = agent_service.cancel_run(chat_id)
    return CancelResponse(cancelled=cancelled)
