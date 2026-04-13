from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from rossum_api import APIClientError, AsyncRossumAPIClient
from rossum_api.dtos import Token
from slowapi import Limiter
from slowapi.util import get_remote_address

from rossum_agent.api.dependencies import RossumCredentials, get_chat_service, get_validated_credentials
from rossum_agent.api.models.schemas import ErrorResponse, ReportToSlackRequest, ReportToSlackResponse
from rossum_agent.api.services.chat_service import ChatService
from rossum_agent.api.services.slack_service import SlackService, SlackServiceError
from rossum_agent.url_context import extract_url_context

logger = structlog.get_logger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/chats", tags=["slack"])


@dataclass
class SlackContext:
    reporter_name: str | None = None
    user_id: str | None = None
    organization_name: str | None = None
    organization_id: int | None = None
    queue_id: int | None = None
    queue_name: str | None = None


def _reporter_name_from_credentials(credentials: RossumCredentials) -> str | None:
    """Build reporter name from /auth/user data stored in credentials."""
    full_name = f"{credentials.first_name or ''} {credentials.last_name or ''}".strip()
    if full_name and credentials.email:
        return f"{full_name} ({credentials.email})"
    return full_name or credentials.email


async def _fetch_slack_context(credentials: RossumCredentials, queue_id: int | None = None) -> SlackContext:
    api_base = credentials.api_url.rstrip("/")

    ctx = SlackContext(user_id=credentials.user_id)
    try:
        client = AsyncRossumAPIClient(base_url=api_base, credentials=Token(token=credentials.token))

        try:
            user = await client.retrieve_user(int(credentials.user_id))
            full_name = f"{user.first_name} {user.last_name}".strip()
            ctx.reporter_name = full_name or user.username
        except APIClientError as e:
            if e.status_code != 404:
                raise
            # Support access: user_id from /auth/user may not exist in the target org
            ctx.reporter_name = _reporter_name_from_credentials(credentials)
            logger.info(f"User {credentials.user_id} not found, using auth fallback: {ctx.reporter_name}")

        org = await client.retrieve_own_organization()
        ctx.organization_name = org.name
        ctx.organization_id = org.id

        if queue_id:
            ctx.queue_id = queue_id
            queue = await client.retrieve_queue(queue_id)
            ctx.queue_name = queue.name
    except Exception:
        logger.warning("Failed to fetch Slack context from Rossum API", exc_info=True)

    return ctx


@dataclass
class SlackConfig:
    bot_token: str
    channel: str


def get_slack_config() -> SlackConfig:
    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    channel = os.environ.get("SLACK_CHANNEL")
    if not bot_token or not channel:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack not configured (SLACK_BOT_TOKEN, SLACK_CHANNEL)",
        )
    return SlackConfig(bot_token=bot_token, channel=channel)


@router.post(
    "/{chat_id}/report-to-slack",
    response_model=ReportToSlackResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Chat not found"},
        501: {"model": ErrorResponse, "description": "Slack integration not installed"},
        502: {"model": ErrorResponse, "description": "Slack service error"},
        503: {"model": ErrorResponse, "description": "Slack not configured"},
    },
)
@limiter.limit("5/minute")
async def report_to_slack(
    request: Request,
    chat_id: str,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    slack_config: Annotated[SlackConfig, Depends(get_slack_config)],
    body: ReportToSlackRequest | None = None,
) -> ReportToSlackResponse:
    if not chat_service.chat_exists(credentials.user_id, chat_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    messages = chat_service.get_messages(credentials.user_id, chat_id)
    if messages is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    try:
        slack_service = SlackService(slack_bot_token=slack_config.bot_token)
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Slack integration not available. Install the slack extra: pip install rossum-agent[slack]",
        ) from e

    rossum_url = body.rossum_url if body else None
    url_context = extract_url_context(rossum_url)
    slack_ctx = await _fetch_slack_context(credentials, url_context.queue_id)

    try:
        slack_ts = await slack_service.post_conversation(
            channel=slack_config.channel,
            chat_id=chat_id,
            messages=messages,
            reporter_name=slack_ctx.reporter_name,
            user_id=slack_ctx.user_id,
            organization_name=slack_ctx.organization_name,
            organization_id=slack_ctx.organization_id,
            queue_id=slack_ctx.queue_id,
            queue_name=slack_ctx.queue_name,
        )
    except SlackServiceError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=e.detail) from e

    return ReportToSlackResponse(chat_id=chat_id, channel=slack_config.channel, slack_ts=slack_ts)
