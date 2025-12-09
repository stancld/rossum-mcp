"""FastAPI dependencies for the API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Annotated  # noqa: TC003 - Required at runtime for FastAPI dependency injection

import httpx
from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)


@dataclass
class RossumCredentials:
    """Rossum API credentials extracted from request headers."""

    token: str
    api_url: str
    user_id: str | None = None


async def get_rossum_credentials(
    x_rossum_token: Annotated[str, Header(alias="X-Rossum-Token")],
    x_rossum_api_url: Annotated[str, Header(alias="X-Rossum-Api-Url")],
) -> RossumCredentials:
    """Extract and validate Rossum credentials from request headers.

    Args:
        x_rossum_token: Rossum API token from X-Rossum-Token header.
        x_rossum_api_url: Rossum API URL from X-Rossum-Api-Url header.

    Returns:
        RossumCredentials with token and API URL.

    Raises:
        HTTPException: If credentials are missing or invalid.
    """
    if not x_rossum_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-Rossum-Token header")
    if not x_rossum_api_url:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-Rossum-Api-Url header")

    return RossumCredentials(token=x_rossum_token, api_url=x_rossum_api_url)


async def get_validated_credentials(
    x_rossum_token: Annotated[str, Header(alias="X-Rossum-Token")],
    x_rossum_api_url: Annotated[str, Header(alias="X-Rossum-Api-Url")],
) -> RossumCredentials:
    """Extract credentials and validate against Rossum API.

    Validates the token by calling the Rossum API /v1/auth/user endpoint.
    Extracts user ID from the response for user isolation.

    Args:
        x_rossum_token: Rossum API token from X-Rossum-Token header.
        x_rossum_api_url: Rossum API URL from X-Rossum-Api-Url header.

    Returns:
        RossumCredentials with token, API URL, and user_id.

    Raises:
        HTTPException: If credentials are missing or invalid.
    """
    credentials = await get_rossum_credentials(x_rossum_token, x_rossum_api_url)

    # Normalize API URL - strip trailing /v1 if present to avoid duplication
    api_base = credentials.api_url.rstrip("/")
    if api_base.endswith("/v1"):
        api_base = api_base[:-3]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_base}/v1/auth/user", headers={"Authorization": f"Bearer {credentials.token}"}, timeout=10.0
            )

            if response.status_code == 401:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Rossum API token")

            if response.status_code != 200:
                logger.warning(f"Rossum API returned {response.status_code}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to validate token with Rossum API"
                )

            user_data = response.json()
            user_id = str(user_data.get("id", ""))

            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY, detail="Rossum API did not return user ID"
                )

            return RossumCredentials(token=credentials.token, api_url=credentials.api_url, user_id=user_id)

    except httpx.RequestError as e:
        logger.error(f"Failed to connect to Rossum API: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to connect to Rossum API") from e
