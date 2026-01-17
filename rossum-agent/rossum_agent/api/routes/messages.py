"""Message endpoints with SSE streaming."""

from __future__ import annotations

import logging
from collections.abc import Callable  # noqa: TC003 - Required at runtime for service getter type hints
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from rossum_agent.api.dependencies import RossumCredentials, get_validated_credentials
from rossum_agent.api.models.schemas import (
    DocumentContent,
    FileCreatedEvent,
    ImageContent,
    MessageRequest,
    StepEvent,
    StreamDoneEvent,
    SubAgentProgressEvent,
    SubAgentTextEvent,
)
from rossum_agent.api.services.agent_service import (
    AgentService,  # noqa: TC001 - Required at runtime for FastAPI Depends()
)
from rossum_agent.api.services.chat_service import (
    ChatService,  # noqa: TC001 - Required at runtime for FastAPI Depends()
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/chats", tags=["messages"])

_get_chat_service: Callable[[], ChatService] | None = None
_get_agent_service: Callable[[], AgentService] | None = None


def set_chat_service_getter(getter: Callable[[], ChatService]) -> None:
    global _get_chat_service
    _get_chat_service = getter


def set_agent_service_getter(getter: Callable[[], AgentService]) -> None:
    global _get_agent_service
    _get_agent_service = getter


def get_chat_service_dep() -> ChatService:
    if _get_chat_service is None:
        raise RuntimeError("Chat service getter not configured")
    return _get_chat_service()


def get_agent_service_dep() -> AgentService:
    if _get_agent_service is None:
        raise RuntimeError("Agent service getter not configured")
    return _get_agent_service()


def _format_sse_event(event_type: str, data: str) -> str:
    """Format an SSE event string."""
    return f"event: {event_type}\ndata: {data}\n\n"


type AgentEvent = StreamDoneEvent | SubAgentProgressEvent | SubAgentTextEvent | StepEvent


@dataclass
class ProcessedEvent:
    """Result of processing an agent event."""

    sse_event: str | None = None
    done_event: StreamDoneEvent | None = None
    final_response_update: str | None = None


def _process_agent_event(event: AgentEvent) -> ProcessedEvent:
    """Process a single agent event and return structured result."""
    if isinstance(event, StreamDoneEvent):
        return ProcessedEvent(done_event=event)
    if isinstance(event, SubAgentProgressEvent):
        return ProcessedEvent(sse_event=_format_sse_event("sub_agent_progress", event.model_dump_json()))
    if isinstance(event, SubAgentTextEvent):
        return ProcessedEvent(sse_event=_format_sse_event("sub_agent_text", event.model_dump_json()))
    sse = _format_sse_event("step", event.model_dump_json())
    if event.type == "text" and event.is_streaming:
        return ProcessedEvent(sse_event=sse, final_response_update=event.content)
    final_response = event.content if event.type == "final_answer" and event.content else None
    return ProcessedEvent(sse_event=sse, final_response_update=final_response)


def _yield_file_events(output_dir: Path | None, chat_id: str) -> Iterator[str]:
    """Yield SSE events for created files in the output directory."""
    logger.info(f"_yield_file_events called with output_dir={output_dir}, chat_id={chat_id}")
    if output_dir is None:
        logger.info("output_dir is None, returning")
        return
    if output_dir.exists():
        logger.info(f"output_dir exists, listing files: {list(output_dir.iterdir())}")
        for file_path in output_dir.iterdir():
            if file_path.is_file():
                logger.info(f"Yielding file_created event for {file_path.name}")
                file_event = FileCreatedEvent(
                    filename=file_path.name, url=f"/api/v1/chats/{chat_id}/files/{file_path.name}"
                )
                yield _format_sse_event("file_created", file_event.model_dump_json())
    else:
        logger.info(f"output_dir {output_dir} does not exist")


@router.post(
    "/{chat_id}/messages",
    response_class=StreamingResponse,
    responses={
        200: {"description": "SSE stream of agent step events", "content": {"text/event-stream": {}}},
        404: {"description": "Chat not found"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit("10/minute")
async def send_message(
    request: Request,
    chat_id: str,
    message: MessageRequest,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)] = None,  # type: ignore[assignment]
    chat_service: Annotated[ChatService, Depends(get_chat_service_dep)] = None,  # type: ignore[assignment]
    agent_service: Annotated[AgentService, Depends(get_agent_service_dep)] = None,  # type: ignore[assignment]
) -> StreamingResponse:
    """Send a message and stream the agent's response via SSE.

    Args:
        request: FastAPI request object (required for rate limiting).
        chat_id: Chat session identifier.
        message: Message request with content.
        credentials: Validated Rossum credentials.
        chat_service: Chat service instance.
        agent_service: Agent service instance.

    Returns:
        StreamingResponse with SSE events.

    Raises:
        HTTPException: If chat not found.
    """
    chat_data = chat_service.get_chat_data(credentials.user_id, chat_id)
    if chat_data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    history = chat_data.messages
    mcp_mode = chat_data.metadata.mcp_mode
    user_prompt = message.content
    images: list[ImageContent] | None = message.images
    documents: list[DocumentContent] | None = message.documents

    async def event_generator() -> Iterator[str]:  # type: ignore[misc]
        final_response: str | None = None
        done_event: StreamDoneEvent | None = None

        try:
            async for event in agent_service.run_agent(
                prompt=user_prompt,
                images=images,
                documents=documents,
                conversation_history=history,
                rossum_api_token=credentials.token,
                rossum_api_base_url=credentials.api_url,
                rossum_url=message.rossum_url,
                mcp_mode=mcp_mode,  # type: ignore[arg-type]
            ):
                result = _process_agent_event(event)
                if result.done_event:
                    done_event = result.done_event
                if result.final_response_update:
                    final_response = result.final_response_update
                if result.sse_event:
                    yield result.sse_event

        except Exception as e:
            logger.error(f"Error during agent execution: {e}", exc_info=True)
            error_event = StepEvent(type="error", step_number=0, content=str(e), is_final=True)
            yield _format_sse_event("error", error_event.model_dump_json())
            return

        updated_history = agent_service.build_updated_history(
            existing_history=history,
            user_prompt=user_prompt,
            final_response=final_response,
            images=images,
            documents=documents,
        )
        chat_service.save_messages(
            user_id=credentials.user_id,
            chat_id=chat_id,
            messages=updated_history,
            output_dir=agent_service.output_dir,
            metadata=chat_data.metadata,
        )

        for file_event in _yield_file_events(agent_service.output_dir, chat_id):
            yield file_event

        if done_event:
            yield _format_sse_event("done", done_event.model_dump_json())

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
