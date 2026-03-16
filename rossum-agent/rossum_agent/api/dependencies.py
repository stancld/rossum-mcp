"""FastAPI dependencies for the API."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Annotated
from urllib.parse import urlparse

import httpx
from fastapi import Header, HTTPException, Request, status

from rossum_agent.api.services.agent_service import AgentService
from rossum_agent.api.services.chat_service import ChatService
from rossum_agent.api.services.file_service import FileService
from rossum_agent.redis_storage import RedisStorage

logger = logging.getLogger(__name__)

# Base allowed hosts pattern
_BASE_ALLOWED_HOSTS = r"elis\.rossum\.ai|api\.elis\.rossum\.ai|(.*\.)?api\.rossum\.ai|.*\.rossum\.(app|ai)|(elis|api\.elis)\.develop\.r8\.lol"

# Additional hosts from environment variable (comma-separated regex patterns)
_ADDITIONAL_HOSTS = os.environ.get("ADDITIONAL_ALLOWED_ROSSUM_HOSTS", "")


def _build_allowed_hosts_pattern() -> re.Pattern[str]:
    """Build the allowed hosts regex pattern including any additional hosts."""
    patterns = [_BASE_ALLOWED_HOSTS]
    if _ADDITIONAL_HOSTS:
        additional = [p.strip() for p in _ADDITIONAL_HOSTS.split(",") if p.strip()]
        patterns.extend(additional)
    return re.compile(f"^({'|'.join(patterns)})$")


ALLOWED_ROSSUM_HOST_PATTERN = _build_allowed_hosts_pattern()


def validate_rossum_api_url(url: str) -> str:
    """Validate and normalize the Rossum API URL to prevent SSRF."""
    try:
        parsed = urlparse(url)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid X-Rossum-Api-Url format") from e

    if parsed.scheme != "https":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Rossum-Api-Url must use HTTPS",
        )

    if not parsed.hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid X-Rossum-Api-Url: missing hostname"
        )

    if not ALLOWED_ROSSUM_HOST_PATTERN.match(parsed.hostname):
        logger.warning(f"Rejected non-Rossum API URL: {parsed.hostname}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Rossum-Api-Url must be a valid Rossum API endpoint",
        )

    api_base = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port and parsed.port != 443:
        api_base = f"{api_base}:{parsed.port}"

    # Preserve /api prefix if present (some Rossum environments use /api/v1 path)
    if parsed.path:
        path = parsed.path.rstrip("/")
        # Strip /v1 suffix to avoid duplication when we append /v1/auth/user
        path = path.removesuffix("/v1")
        if path:
            api_base = f"{api_base}{path}"

    return api_base


@dataclass
class RossumCredentials:
    """Rossum API credentials extracted from request headers."""

    token: str
    api_url: str
    user_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None


async def get_rossum_credentials(
    x_rossum_token: Annotated[str, Header(alias="X-Rossum-Token")],
    x_rossum_api_url: Annotated[str, Header(alias="X-Rossum-Api-Url")],
) -> RossumCredentials:
    if not x_rossum_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-Rossum-Token header")
    if not x_rossum_api_url:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-Rossum-Api-Url header")

    return RossumCredentials(token=x_rossum_token, api_url=x_rossum_api_url)


async def get_validated_credentials(
    x_rossum_token: Annotated[str, Header(alias="X-Rossum-Token")],
    x_rossum_api_url: Annotated[str, Header(alias="X-Rossum-Api-Url")],
) -> RossumCredentials:
    """Validate token against Rossum API /v1/auth/user and extract user_id."""
    credentials = await get_rossum_credentials(x_rossum_token, x_rossum_api_url)

    # Validate and normalize API URL to prevent SSRF
    api_base = validate_rossum_api_url(credentials.api_url)
    # Strip trailing /v1 to avoid duplication (URL might be .../api or .../api/v1)
    api_base_normalized = api_base.rstrip("/")
    api_base_normalized = api_base_normalized.removesuffix("/v1")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_base_normalized}/v1/auth/user",
                headers={"Authorization": f"Bearer {credentials.token}"},
                timeout=10.0,
            )

            if response.status_code == 401:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Rossum API token")

            if response.status_code != 200:
                logger.warning(f"Rossum API returned {response.status_code}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to validate token with Rossum API"
                )

            try:
                user_data = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"Rossum API returned invalid JSON: {e}. Response text: {response.text!r}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY, detail="Rossum API returned invalid response"
                ) from e

            user_id = str(user_data.get("id", ""))

            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY, detail="Rossum API did not return user ID"
                )

            return RossumCredentials(
                token=credentials.token,
                api_url=credentials.api_url,
                user_id=user_id,
                first_name=user_data.get("first_name"),
                last_name=user_data.get("last_name"),
                email=user_data.get("email"),
            )

    except httpx.RequestError as e:
        logger.error(f"Failed to connect to Rossum API: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to connect to Rossum API") from e


def get_chat_service(request: Request) -> ChatService:
    """Get the ChatService from app state."""
    if not hasattr(request.app.state, "chat_service"):
        raise RuntimeError("Chat service not initialized - ensure lifespan context is used")
    return request.app.state.chat_service


def get_agent_service(request: Request) -> AgentService:
    """Get the AgentService from app state."""
    if not hasattr(request.app.state, "agent_service"):
        raise RuntimeError("Agent service not initialized - ensure lifespan context is used")
    return request.app.state.agent_service


def get_file_service(request: Request) -> FileService:
    """Get the FileService from app state."""
    if not hasattr(request.app.state, "file_service"):
        raise RuntimeError("File service not initialized - ensure lifespan context is used")
    return request.app.state.file_service


def get_redis_storage(request: Request) -> RedisStorage:
    """Get the shared RedisStorage for change tracking."""
    if not hasattr(request.app.state, "redis_storage"):
        raise RuntimeError("Redis storage not initialized - ensure lifespan context is used")
    return request.app.state.redis_storage
