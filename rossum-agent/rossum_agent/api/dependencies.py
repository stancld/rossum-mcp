"""FastAPI dependencies for the API."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Annotated  # noqa: TC003 - Required at runtime for FastAPI dependency injection
from urllib.parse import urlparse

import httpx
from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)

# Base allowed hosts pattern
_BASE_ALLOWED_HOSTS = (
    r"elis\.rossum\.ai|api\.elis\.rossum\.ai|api\.rossum\.ai|.*\.rossum\.app|(elis|api\.elis)\.develop\.r8\.lol"
)

# Additional hosts from environment variable (comma-separated regex patterns)
# Example: ADDITIONAL_ALLOWED_ROSSUM_HOSTS=".*\.review\.r8\.lol,.*\.staging\.example\.com"
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
    """Validate that the Rossum API URL is a trusted Rossum domain.

    This prevents SSRF attacks by ensuring we only make requests to known Rossum endpoints.

    Args:
        url: The API URL to validate.

    Returns:
        The validated and normalized API base URL.

    Raises:
        HTTPException: If the URL is not a valid Rossum API endpoint.
    """
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
        if path.endswith("/v1"):
            path = path[:-3]
        if path:
            api_base = f"{api_base}{path}"

    return api_base


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

    # Validate and normalize API URL to prevent SSRF
    api_base = validate_rossum_api_url(credentials.api_url)
    # Strip trailing /v1 to avoid duplication (URL might be .../api or .../api/v1)
    api_base_normalized = api_base.rstrip("/")
    if api_base_normalized.endswith("/v1"):
        api_base_normalized = api_base_normalized[:-3]

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

            return RossumCredentials(token=credentials.token, api_url=credentials.api_url, user_id=user_id)

    except httpx.RequestError as e:
        logger.error(f"Failed to connect to Rossum API: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to connect to Rossum API") from e
