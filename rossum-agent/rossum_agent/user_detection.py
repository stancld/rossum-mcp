"""User detection utilities for Teleport-based authentication."""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def get_user_id_from_headers(headers: dict[str, Any] | None) -> str | None:
    """Extract user ID from Teleport headers.

    Args:
        headers: HTTP request headers

    Returns:
        User ID string or None if not found
    """
    if not headers:
        return None

    teleport_headers = ["X-Teleport-Login", "X-Forwarded-User", "X-Remote-User"]

    for header in teleport_headers:
        if value := headers.get(header):
            logger.info(f"Found user ID in header {header}: {value}")
            return str(value)

    return None


def get_user_id_from_cookie(cookie_string: str | None) -> str | None:
    """Extract user ID from Teleport session cookie.

    Args:
        cookie_string: Raw cookie string

    Returns:
        Hashed user ID or None if not found
    """
    if not cookie_string:
        return None

    match = re.search(r"__Host-grv_app_session_subject=([a-f0-9]+)", cookie_string)
    if match:
        session_hash = match.group(1)
        # Use first 16 chars of the hash as user ID
        user_id = f"cookie_{session_hash[:16]}"
        logger.info(f"Found user ID from cookie: {user_id}")
        return user_id

    return None


def detect_user_id(headers: dict[str, Any] | None = None, cookie: str | None = None) -> str | None:
    """Detect user ID from available sources.

    Priority:
    1. Teleport headers
    2. Session cookie (fallback)

    Args:
        headers: HTTP request headers
        cookie: Raw cookie string

    Returns:
        User ID string or None if not found
    """
    # Try headers first
    if user_id := get_user_id_from_headers(headers) or get_user_id_from_cookie(cookie):
        return user_id

    logger.warning("No user ID found in headers or cookies")
    return None


def normalize_user_id(user_id: str | None) -> str:
    """Normalize user ID for use in Redis keys.

    Args:
        user_id: Raw user ID

    Returns:
        Normalized user ID suitable for Redis keys
    """
    return re.sub(r"[^a-zA-Z0-9_-]", "_", user_id).lower() if user_id else "default"
