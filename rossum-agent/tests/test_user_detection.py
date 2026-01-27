"""Tests for rossum_agent.user_detection module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import jwt
import pytest
import requests
from rossum_agent.user_detection import (
    decode_jwt_username,
    fetch_jwt_public_key,
    get_user_from_jwt,
    normalize_user_id,
)


class TestFetchJwtPublicKey:
    """Test fetch_jwt_public_key function."""

    @patch("rossum_agent.user_detection.requests.get")
    @patch("rossum_agent.user_detection.jwt.algorithms.RSAAlgorithm.from_jwk")
    def test_fetches_and_returns_public_key(self, mock_from_jwk: MagicMock, mock_get: MagicMock):
        """Test successful fetch of JWT public key."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"keys": [{"kty": "RSA", "n": "test", "e": "AQAB"}]}
        mock_get.return_value = mock_response

        mock_public_key = MagicMock()
        mock_from_jwk.return_value = mock_public_key

        result = fetch_jwt_public_key("https://example.com/.well-known/jwks.json")

        mock_get.assert_called_once_with("https://example.com/.well-known/jwks.json")
        mock_response.raise_for_status.assert_called_once()
        assert result == mock_public_key

    @patch("rossum_agent.user_detection.requests.get")
    def test_raises_error_when_no_keys_in_response(self, mock_get: MagicMock):
        """Test ValueError when response has no keys."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "no keys"}
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match="No JWT key found"):
            fetch_jwt_public_key("https://example.com/jwks")

    @patch("rossum_agent.user_detection.requests.get")
    def test_raises_for_http_error(self, mock_get: MagicMock):
        """Test that HTTP errors are propagated."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        with pytest.raises(requests.HTTPError):
            fetch_jwt_public_key("https://example.com/jwks")


class TestDecodeJwtUsername:
    """Test decode_jwt_username function."""

    @patch("rossum_agent.user_detection.jwt.decode")
    def test_decodes_username_from_token(self, mock_decode: MagicMock):
        """Test successful username extraction from JWT."""
        mock_public_key = MagicMock()
        mock_decode.return_value = {"username": "test-user", "exp": 9999999999}

        result = decode_jwt_username(mock_public_key, "valid.jwt.token")

        assert result == "test-user"
        mock_decode.assert_called_once_with(
            "valid.jwt.token", mock_public_key, algorithms=["RS256"], options={"verify_aud": False}
        )

    @patch("rossum_agent.user_detection.jwt.decode")
    def test_propagates_invalid_token_error(self, mock_decode: MagicMock):
        """Test that invalid token errors are propagated."""
        mock_public_key = MagicMock()
        mock_decode.side_effect = jwt.InvalidTokenError("Invalid signature")

        with pytest.raises(jwt.InvalidTokenError):
            decode_jwt_username(mock_public_key, "invalid.token")


class TestGetUserFromJwt:
    """Test get_user_from_jwt function."""

    def test_returns_none_for_empty_token(self):
        """Test None is returned when token is None or empty."""
        assert get_user_from_jwt(None) is None
        assert get_user_from_jwt("") is None

    @patch.dict("os.environ", {}, clear=True)
    def test_returns_none_when_jwks_url_not_set(self):
        """Test None is returned when TELEPORT_JWT_JWKS_URL is not set."""
        result = get_user_from_jwt("some.jwt.token")
        assert result is None

    @patch("rossum_agent.user_detection.fetch_jwt_public_key")
    @patch("rossum_agent.user_detection.decode_jwt_username")
    @patch.dict("os.environ", {"TELEPORT_JWT_JWKS_URL": "https://jwks.example.com"})
    def test_returns_username_on_success(self, mock_decode: MagicMock, mock_fetch: MagicMock):
        """Test username is returned on successful verification."""
        mock_public_key = MagicMock()
        mock_fetch.return_value = mock_public_key
        mock_decode.return_value = "authenticated-user"

        result = get_user_from_jwt("valid.jwt.token")

        assert result == "authenticated-user"
        mock_fetch.assert_called_once_with("https://jwks.example.com")
        mock_decode.assert_called_once_with(public_key=mock_public_key, token="valid.jwt.token")

    @patch("rossum_agent.user_detection.fetch_jwt_public_key")
    @patch.dict("os.environ", {"TELEPORT_JWT_JWKS_URL": "https://jwks.example.com"})
    def test_returns_none_on_request_error(self, mock_fetch: MagicMock):
        """Test None is returned when JWKS fetch fails."""
        mock_fetch.side_effect = requests.RequestException("Network error")

        result = get_user_from_jwt("some.jwt.token")

        assert result is None

    @patch("rossum_agent.user_detection.fetch_jwt_public_key")
    @patch("rossum_agent.user_detection.decode_jwt_username")
    @patch.dict("os.environ", {"TELEPORT_JWT_JWKS_URL": "https://jwks.example.com"})
    def test_returns_none_on_invalid_token(self, mock_decode: MagicMock, mock_fetch: MagicMock):
        """Test None is returned when token is invalid."""
        mock_fetch.return_value = MagicMock()
        mock_decode.side_effect = jwt.InvalidTokenError("Bad token")

        result = get_user_from_jwt("invalid.jwt.token")

        assert result is None

    @patch("rossum_agent.user_detection.fetch_jwt_public_key")
    @patch("rossum_agent.user_detection.decode_jwt_username")
    @patch.dict("os.environ", {"TELEPORT_JWT_JWKS_URL": "https://jwks.example.com"})
    def test_returns_none_on_key_error(self, mock_decode: MagicMock, mock_fetch: MagicMock):
        """Test None is returned when username key is missing."""
        mock_fetch.return_value = MagicMock()
        mock_decode.side_effect = KeyError("username")

        result = get_user_from_jwt("token.without.username")

        assert result is None

    @patch("rossum_agent.user_detection.fetch_jwt_public_key")
    @patch.dict("os.environ", {"TELEPORT_JWT_JWKS_URL": "https://jwks.example.com"})
    def test_returns_none_on_value_error(self, mock_fetch: MagicMock):
        """Test None is returned when value error occurs during decoding."""
        mock_fetch.side_effect = ValueError("Invalid key format")

        result = get_user_from_jwt("some.token")

        assert result is None


class TestNormalizeUserId:
    """Test normalize_user_id function."""

    def test_returns_default_for_none(self):
        """Test 'default' is returned for None input."""
        assert normalize_user_id(None) == "default"

    def test_returns_default_for_empty_string(self):
        """Test 'default' is returned for empty string."""
        assert normalize_user_id("") == "default"

    def test_converts_to_lowercase(self):
        """Test user ID is converted to lowercase."""
        assert normalize_user_id("UserName") == "username"
        assert normalize_user_id("ADMIN") == "admin"

    def test_replaces_special_characters_with_underscore(self):
        """Test special characters are replaced with underscores."""
        assert normalize_user_id("user@example.com") == "user_example_com"
        assert normalize_user_id("user.name") == "user_name"
        assert normalize_user_id("user name") == "user_name"

    def test_preserves_allowed_characters(self):
        """Test alphanumeric, underscore, and hyphen are preserved."""
        assert normalize_user_id("user_name") == "user_name"
        assert normalize_user_id("user-name") == "user-name"
        assert normalize_user_id("user123") == "user123"
        assert normalize_user_id("user_name-123") == "user_name-123"

    def test_complex_normalization(self):
        """Test complex user IDs are properly normalized."""
        assert normalize_user_id("John.Doe@Company.COM") == "john_doe_company_com"
        assert normalize_user_id("user+tag@email.com") == "user_tag_email_com"
