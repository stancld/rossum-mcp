"""Message endpoints with SSE streaming (AI SDK UI Message Stream protocol)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from rossum_agent.agent.models import FileCreatedPart, FinalAnswerStep, StepType, TextDeltaStep
from rossum_agent.api.commands import CommandContext, ParsedCommand, execute_command, parse_command
from rossum_agent.api.dependencies import (
    RossumCredentials,
    get_agent_service,
    get_chat_service,
    get_validated_credentials,
)
from rossum_agent.api.models.schemas import (
    CancelResponse,
    DocumentContent,
    ErrorResponse,
    ImageContent,
    MCPMode,
    MessageRequest,
    Persona,
    StreamDoneEvent,
)
from rossum_agent.api.routes.helpers import (
    SSE_KEEPALIVE_COMMENT,
    generate_chat_summary,
    get_commit_store,
    resolve_mcp_mode,
    resolve_persona,
    save_chat_history,
    watch_disconnect,
    with_sse_keepalive,
)
from rossum_agent.api.routes.stream_adapter import (
    StreamState,
    build_finish_events,
    convert_agent_event,
)
from rossum_agent.api.services.agent_service.service import AgentService
from rossum_agent.api.services.chat_service import ChatService
from rossum_agent.url_context import extract_url_context

STREAM_DONE = "data: [DONE]\n\n"


def _iter_file_created_events(output_dir: Path | None, chat_id: str) -> list[dict]:
    """Build data-file-created wire events for files in the output directory."""
    if output_dir is None or not output_dir.exists():
        return []
    events: list[dict] = []
    for wire in (
        convert_agent_event(
            FileCreatedPart(filename=f.name, url=f"/api/v1/chats/{chat_id}/files/{f.name}"),
            StreamState(),
        )
        for f in sorted(output_dir.iterdir())
        if f.is_file()
    ):
        events.extend(wire)
    return events


RESPONSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
    "x-vercel-ai-ui-message-stream": "v1",
}

logger = structlog.get_logger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/chats", tags=["messages"])


def _format_sse(event: dict) -> str:
    return f"data: {json.dumps(event, separators=(',', ':'))}\n\n"


@dataclass
class _ResponseMeta:
    """Route-level metadata collected during streaming (not wire-protocol state)."""

    final_response: str | None = None
    done_event: StreamDoneEvent | None = None


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
    meta: _ResponseMeta,
) -> AsyncIterator[str]:
    watcher = asyncio.create_task(watch_disconnect(request, chat_id, agent_service))

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
        async for event, is_keepalive in with_sse_keepalive(agent_events):
            if is_keepalive:
                yield SSE_KEEPALIVE_COMMENT
                continue

            if isinstance(event, StreamDoneEvent):
                meta.done_event = event
                continue
            if isinstance(event, FinalAnswerStep) and not event.is_hook_output:
                meta.final_response = event.final_answer
            elif isinstance(event, TextDeltaStep) and event.step_type == StepType.FINAL_ANSWER:
                meta.final_response = event.accumulated_text

            try:
                wire_events = convert_agent_event(event, state)
            except Exception:
                logger.exception(f"Failed to convert event {type(event).__name__}")
                wire_events = []

            for wire_event in wire_events:
                yield _format_sse(wire_event)
    finally:
        watcher.cancel()


def _handle_slash_command(
    command: ParsedCommand,
    chat_id: str,
    credentials: RossumCredentials,
    chat_service: ChatService,
) -> StreamingResponse:
    commit_store = get_commit_store() if command.name == "/list-commits" else None
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
        yield _format_sse({"type": "start"})
        text_id = "text_cmd"
        yield _format_sse({"type": "text-start", "id": text_id})
        yield _format_sse({"type": "text-delta", "id": text_id, "delta": result_text})
        yield _format_sse({"type": "text-end", "id": text_id})
        yield _format_sse({"type": "finish"})
        yield STREAM_DONE

    return StreamingResponse(
        command_event_generator(),
        media_type="text/event-stream",
        headers=RESPONSE_HEADERS,
    )


async def _parse_message_request(request: Request) -> MessageRequest:
    """Parse MessageRequest from raw body, bypassing FastAPI's body parsing.

    Handles double-encoded JSON (body is a JSON string containing another JSON string)
    which some clients may send.
    """
    try:
        raw = await request.body()
        data = json.loads(raw)
        if isinstance(data, str):
            data = json.loads(data)
        return MessageRequest.model_validate(data)
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e


@router.post(
    "/{chat_id}/messages",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "AI SDK UI Message Stream v1 compatible SSE stream",
            "content": {"text/event-stream": {}},
        },
        404: {"model": ErrorResponse, "description": "Chat not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
@limiter.limit("10/minute")
async def send_message(
    request: Request,
    chat_id: str,
    message: Annotated[MessageRequest, Depends(_parse_message_request)],
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> StreamingResponse:
    chat_data = chat_service.get_chat_data(credentials.user_id, chat_id)
    if chat_data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    command = parse_command(message.content)
    if command is not None:
        return _handle_slash_command(command, chat_id, credentials, chat_service)

    history = chat_data.messages
    mcp_mode = resolve_mcp_mode(message, chat_data)
    persona = resolve_persona(message, chat_data)
    user_prompt = message.content
    images: list[ImageContent] | None = message.images
    documents: list[DocumentContent] | None = message.documents

    async def event_generator() -> AsyncIterator[str]:
        state = StreamState()
        meta = _ResponseMeta()

        yield _format_sse({"type": "start"})

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
                meta=meta,
            ):
                yield chunk
        except asyncio.CancelledError:
            logger.info(f"Request cancelled for chat {chat_id}")
            return
        except Exception as e:
            logger.error(f"Error during agent execution: {e}", exc_info=True)
            for event in build_finish_events(state):
                yield _format_sse(event)
            yield _format_sse({"type": "error", "errorText": "An internal error has occurred"})
            yield STREAM_DONE
            return

        output_dir = agent_service.get_output_dir(chat_id)
        memory = agent_service.pop_last_memory(chat_id)
        url_context = extract_url_context(message.rossum_url).to_context_string() or None
        summary = await generate_chat_summary(
            user_prompt, previous_summary=chat_data.metadata.summary, url_context=url_context
        )

        save_chat_history(
            chat_service=chat_service,
            agent_service=agent_service,
            credentials=credentials,
            chat_id=chat_id,
            chat_data=chat_data,
            history=history,
            user_prompt=user_prompt,
            final_response=meta.final_response,
            images=images,
            documents=documents,
            output_dir=output_dir,
            memory=memory,
            done_event=meta.done_event,
            summary=summary,
        )

        for event in _iter_file_created_events(output_dir, chat_id):
            yield _format_sse(event)

        for event in build_finish_events(state):
            yield _format_sse(event)

        yield STREAM_DONE

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=RESPONSE_HEADERS,
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
    if not chat_service.chat_exists(credentials.user_id, chat_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    cancelled = agent_service.cancel_run(chat_id)
    return CancelResponse(cancelled=cancelled)
