"""User detection utilities for Teleport-based authentication."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import jwt
import requests

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric import rsa

logger = logging.getLogger(__name__)


@dataclass
class TeleportJWTClaims:
    """Claims extracted from a Teleport JWT token."""

    username: str
    roles: list[str]
    traits: dict[str, list[str]]
    issuer: str | None
    subject: str | None
    audience: str | None


def fetch_jwt_public_key(jwks_url: str) -> rsa.RSAPublicKey:
    """Fetch public key from internal Teleport JWK endpoint.

    Args:
        jwks_url: URL to the JWKS endpoint

    Returns:
        RSA public key for JWT verification

    Raises:
        ValueError: If no JWT key found in response
    """
    response = requests.get(jwks_url)
    response.raise_for_status()

    response_json = response.json()
    if "keys" not in response_json:
        raise ValueError("No JWT key found in Teleport JWK endpoint response")

    return jwt.algorithms.RSAAlgorithm.from_jwk(response_json["keys"][0])


def decode_jwt_claims(public_key: rsa.RSAPublicKey, token: str, audience: str) -> TeleportJWTClaims:
    """Validate and decode the JWT claims using public key and token from Request.

    Args:
        public_key: RSA public key for verification
        token: JWT token string
        audience: Expected audience claim

    Returns:
        Decoded JWT claims
    """
    decoded_token = jwt.decode(token, public_key, algorithms=["RS256"], audience=audience)
    return TeleportJWTClaims(
        username=decoded_token["username"],
        roles=decoded_token.get("roles", []),
        traits=decoded_token.get("traits", {}),
        issuer=decoded_token.get("iss"),
        subject=decoded_token.get("sub"),
        audience=decoded_token.get("aud"),
    )


def get_user_from_jwt(jwt_token: str | None) -> str | None:
    """Extract username from JWT token using Teleport JWKS verification.

    Requires TELEPORT_JWT_JWKS_URL and TELEPORT_JWT_AUDIENCE environment variables.

    Args:
        jwt_token: The JWT token string

    Returns:
        Username string or None if authentication fails
    """
    if not jwt_token:
        return None

    jwks_url = os.environ.get("TELEPORT_JWT_JWKS_URL")
    audience = os.environ.get("TELEPORT_JWT_AUDIENCE")

    if not jwks_url:
        logger.warning("TELEPORT_JWT_JWKS_URL not set, cannot verify JWT")
        return None

    if not audience:
        logger.warning("TELEPORT_JWT_AUDIENCE not set, cannot verify JWT")
        return None

    try:
        public_key = fetch_jwt_public_key(jwks_url)
        claims = decode_jwt_claims(
            public_key=public_key,
            token=jwt_token,
            audience=audience,
        )
        logger.info(f"User {claims.username} authenticated using Teleport JWT")
        return claims.username
    except requests.RequestException as e:
        logger.error(f"Failed to fetch JWKS: {e}")
        return None
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid JWT token: {e}")
        return None
    except (KeyError, ValueError) as e:
        logger.error(f"Failed to decode JWT claims: {e}")
        return None


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


def detect_user_id(
    headers: dict[str, Any] | None = None,
    cookie: str | None = None,
    jwt_token: str | None = None,
) -> str | None:
    """Detect user ID from available sources.

    Priority:
    1. JWT token (most reliable)
    2. Teleport headers
    3. Session cookie (fallback)

    Args:
        headers: HTTP request headers
        cookie: Raw cookie string
        jwt_token: JWT token string

    Returns:
        User ID string or None if not found
    """
    # Try JWT first (most reliable)
    if user_id := get_user_from_jwt(jwt_token):
        return user_id

    # Try headers
    if user_id := get_user_id_from_headers(headers):
        return user_id

    # Try cookie as fallback
    if user_id := get_user_id_from_cookie(cookie):
        return user_id

    logger.warning("No user ID found in JWT, headers, or cookies")
    return None


def normalize_user_id(user_id: str | None) -> str:
    """Normalize user ID for use in Redis keys.

    Args:
        user_id: Raw user ID

    Returns:
        Normalized user ID suitable for Redis keys
    """
    return re.sub(r"[^a-zA-Z0-9_-]", "_", user_id).lower() if user_id else "default"
