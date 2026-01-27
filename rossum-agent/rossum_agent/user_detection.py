"""User detection utilities for Teleport-based authentication."""

from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING

import jwt
import jwt.algorithms
import requests

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric import rsa

logger = logging.getLogger(__name__)


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

    return jwt.algorithms.RSAAlgorithm.from_jwk(response_json["keys"][0])  # type: ignore[return-value,attr-defined]


def decode_jwt_username(public_key: rsa.RSAPublicKey, token: str) -> str:
    """Validate and decode the JWT to extract username.

    Args:
        public_key: RSA public key for verification
        token: JWT token string

    Returns:
        Username from the JWT token
    """
    decoded_token = jwt.decode(token, public_key, algorithms=["RS256"], options={"verify_aud": False})
    username: str = decoded_token["username"]
    return username


def get_user_from_jwt(jwt_token: str | None) -> str | None:
    """Extract username from JWT token using Teleport JWKS verification.

    Requires TELEPORT_JWT_JWKS_URL environment variable.

    Args:
        jwt_token: The JWT token string

    Returns:
        Username string or None if authentication fails
    """
    if not jwt_token:
        return None

    if not (jwks_url := os.environ.get("TELEPORT_JWT_JWKS_URL")):
        logger.warning("TELEPORT_JWT_JWKS_URL not set, cannot verify JWT")
        return None

    try:
        public_key = fetch_jwt_public_key(jwks_url)
        username = decode_jwt_username(public_key=public_key, token=jwt_token)
        logger.info(f"User {username} authenticated using Teleport JWT")
        return username
    except requests.RequestException as e:
        logger.error(f"Failed to fetch JWKS: {e}")
        return None
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid JWT token: {e}")
        return None
    except (KeyError, ValueError) as e:
        logger.error(f"Failed to decode JWT claims: {e}")
        return None


def normalize_user_id(user_id: str | None) -> str:
    """Normalize user ID for use in Redis keys.

    Args:
        user_id: Raw user ID

    Returns:
        Normalized user ID suitable for Redis keys
    """
    return re.sub(r"[^a-zA-Z0-9_-]", "_", user_id).lower() if user_id else "default"
