"""Chat session CRUD endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from rossum_agent.api.dependencies import (
    RossumCredentials,
    get_chat_service,
    get_redis_connection,
    get_validated_credentials,
)
from rossum_agent.api.models.schemas import (
    ChatDetail,
    ChatListResponse,
    ChatResponse,
    CommitInfo,
    CommitListResponse,
    CreateChatRequest,
    DeleteResponse,
    EntityChangeInfo,
    ErrorResponse,
    FeedbackListResponse,
    FeedbackRequest,
    FeedbackResponse,
)
from rossum_agent.api.services.chat_service import ChatService
from rossum_agent.change_tracking.store import CommitStore
from rossum_agent.redis_client import RedisConnection

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_chat(
    request: Request,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    body: CreateChatRequest | None = None,
) -> ChatResponse:
    """Create a new chat session."""
    mcp_mode = body.mcp_mode if body else "read-only"
    persona = body.persona if body else "default"
    return chat_service.create_chat(user_id=credentials.user_id, mcp_mode=mcp_mode, persona=persona)


@router.get("", response_model=ChatListResponse)
async def list_chats(
    request: Request,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ChatListResponse:
    """List chat sessions for the authenticated user."""
    return chat_service.list_chats(user_id=credentials.user_id, limit=limit, offset=offset)


@router.get(
    "/{chat_id}", response_model=ChatDetail, responses={404: {"model": ErrorResponse, "description": "Chat not found"}}
)
async def get_chat(
    request: Request,
    chat_id: str,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatDetail:
    """Get detailed information about a chat session."""
    chat = chat_service.get_chat(user_id=credentials.user_id, chat_id=chat_id)

    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    return chat


@router.get(
    "/{chat_id}/commits",
    response_model=CommitListResponse,
    responses={404: {"model": ErrorResponse, "description": "Chat not found"}},
)
async def list_chat_commits(
    request: Request,
    chat_id: str,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    redis: Annotated[RedisConnection, Depends(get_redis_connection)],
) -> CommitListResponse:
    """List configuration commits made in a chat session."""
    chat_data = chat_service.get_chat_data(user_id=credentials.user_id, chat_id=chat_id)
    if chat_data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    commit_hashes = chat_data.metadata.config_commits
    if not commit_hashes or not redis.is_connected():
        return CommitListResponse(commits=[])

    commit_store = CommitStore(redis.client)
    commits = []
    for h in commit_hashes:
        commit = commit_store.get_commit(credentials.api_url, h)
        if commit is None:
            continue
        commits.append(
            CommitInfo(
                hash=commit.hash,
                timestamp=commit.timestamp,
                message=commit.message,
                user_request=commit.user_request,
                changes=[
                    EntityChangeInfo(
                        entity_type=c.entity_type,
                        entity_id=c.entity_id,
                        entity_name=c.entity_name,
                        operation=c.operation,
                    )
                    for c in commit.changes
                ],
            )
        )
    return CommitListResponse(commits=commits)


@router.delete(
    "/{chat_id}",
    response_model=DeleteResponse,
    responses={404: {"model": ErrorResponse, "description": "Chat not found"}},
)
async def delete_chat(
    request: Request,
    chat_id: str,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> DeleteResponse:
    if not chat_service.chat_exists(credentials.user_id, chat_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    deleted = chat_service.delete_chat(user_id=credentials.user_id, chat_id=chat_id)

    return DeleteResponse(deleted=deleted)


@router.put(
    "/{chat_id}/feedback",
    response_model=FeedbackResponse,
    responses={404: {"model": ErrorResponse, "description": "Chat not found"}},
)
async def submit_feedback(
    request: Request,
    chat_id: str,
    body: FeedbackRequest,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> FeedbackResponse:
    if not chat_service.chat_exists(credentials.user_id, chat_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    chat_service.save_feedback(credentials.user_id, chat_id, body.turn_index, body.is_positive)
    return FeedbackResponse(turn_index=body.turn_index, is_positive=body.is_positive)


@router.get(
    "/{chat_id}/feedback",
    response_model=FeedbackListResponse,
    responses={404: {"model": ErrorResponse, "description": "Chat not found"}},
)
async def get_feedback(
    request: Request,
    chat_id: str,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> FeedbackListResponse:
    if not chat_service.chat_exists(credentials.user_id, chat_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    feedback = chat_service.get_feedback(credentials.user_id, chat_id)
    return FeedbackListResponse(feedback=feedback)


@router.delete(
    "/{chat_id}/feedback/{turn_index}",
    response_model=DeleteResponse,
    responses={404: {"model": ErrorResponse, "description": "Chat not found"}},
)
async def delete_feedback(
    request: Request,
    chat_id: str,
    turn_index: int,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> DeleteResponse:
    """Remove feedback for a specific turn."""
    if not chat_service.chat_exists(credentials.user_id, chat_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    deleted = chat_service.delete_feedback(credentials.user_id, chat_id, turn_index)
    return DeleteResponse(deleted=deleted)
