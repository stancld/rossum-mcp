"""Message endpoints with SSE streaming."""

from __future__ import annotations

import logging
from collections.abc import Callable  # noqa: TC003 - Required at runtime for service getter type hints
from typing import Annotated  # noqa: TC003 - Required at runtime for FastAPI dependency injection

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from rossum_agent.api.dependencies import RossumCredentials, get_validated_credentials
from rossum_agent.api.models.schemas import (
    MessageRequest,
    StepEvent,
    StreamDoneEvent,
)
from rossum_agent.api.services.agent_service import (
    AgentService,  # noqa: TC001 - Required at runtime for FastAPI Depends()
)
from rossum_agent.api.services.chat_service import (
    ChatService,  # noqa: TC001 - Required at runtime for FastAPI Depends()
)

logger = logging.getLogger(__name__)

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


@router.post(
    "/{chat_id}/messages",
    response_class=StreamingResponse,
    responses={
        200: {"description": "SSE stream of agent step events", "content": {"text/event-stream": {}}},
        404: {"description": "Chat not found"},
    },
)
async def send_message(
    chat_id: str,
    request: MessageRequest,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)] = None,  # type: ignore[assignment]
    chat_service: Annotated[ChatService, Depends(get_chat_service_dep)] = None,  # type: ignore[assignment]
    agent_service: Annotated[AgentService, Depends(get_agent_service_dep)] = None,  # type: ignore[assignment]
) -> StreamingResponse:
    """Send a message and stream the agent's response via SSE.

    Args:
        chat_id: Chat session identifier.
        request: Message request with content.
        credentials: Validated Rossum credentials.
        chat_service: Chat service instance.
        agent_service: Agent service instance.

    Returns:
        StreamingResponse with SSE events.

    Raises:
        HTTPException: If chat not found.
    """
    if not chat_service.chat_exists(credentials.user_id, chat_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    history = chat_service.get_messages(credentials.user_id, chat_id) or []

    async def event_generator():
        final_response: str | None = None

        try:
            async for event in agent_service.run_agent(
                prompt=request.content,
                conversation_history=history,
                rossum_api_token=credentials.token,
                rossum_api_base_url=credentials.api_url,
            ):
                if isinstance(event, StreamDoneEvent):
                    yield f"event: done\ndata: {event.model_dump_json()}\n\n"
                elif isinstance(event, StepEvent):
                    if event.type == "final_answer" and event.content:
                        final_response = event.content
                    yield f"event: step\ndata: {event.model_dump_json()}\n\n"

        except Exception as e:
            logger.error(f"Error during agent execution: {e}", exc_info=True)
            error_event = StepEvent(type="error", step_number=0, content=str(e), is_final=True)
            yield f"event: error\ndata: {error_event.model_dump_json()}\n\n"
            return

        updated_history = agent_service.build_updated_history(
            existing_history=history, user_prompt=request.content, final_response=final_response
        )
        chat_service.save_messages(user_id=credentials.user_id, chat_id=chat_id, messages=updated_history)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
