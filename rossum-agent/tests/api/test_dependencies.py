"""Tests for API dependencies."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException
from rossum_agent.api.dependencies import (
    RossumCredentials,
    get_rossum_credentials,
    get_validated_credentials,
    validate_rossum_api_url,
)


class TestRossumCredentials:
    """Tests for RossumCredentials dataclass."""

    def test_credentials_with_all_fields(self):
        """Test credentials with all fields."""
        creds = RossumCredentials(token="test_token", api_url="https://api.rossum.ai", user_id="user_123")

        assert creds.token == "test_token"
        assert creds.api_url == "https://api.rossum.ai"
        assert creds.user_id == "user_123"

    def test_credentials_without_user_id(self):
        """Test credentials without user_id."""
        creds = RossumCredentials(token="test_token", api_url="https://api.rossum.ai")

        assert creds.token == "test_token"
        assert creds.user_id is None


class TestGetRossumCredentials:
    """Tests for get_rossum_credentials function."""

    @pytest.mark.asyncio
    async def test_valid_credentials(self):
        """Test extraction of valid credentials."""
        creds = await get_rossum_credentials(x_rossum_token="test_token", x_rossum_api_url="https://api.rossum.ai")

        assert creds.token == "test_token"
        assert creds.api_url == "https://api.rossum.ai"
        assert creds.user_id is None

    @pytest.mark.asyncio
    async def test_empty_token_raises(self):
        """Test that empty token raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            await get_rossum_credentials(x_rossum_token="", x_rossum_api_url="https://api.rossum.ai")

        assert exc_info.value.status_code == 401
        assert "X-Rossum-Token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_empty_api_url_raises(self):
        """Test that empty API URL raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            await get_rossum_credentials(x_rossum_token="test_token", x_rossum_api_url="")

        assert exc_info.value.status_code == 401
        assert "X-Rossum-Api-Url" in exc_info.value.detail


class TestGetValidatedCredentials:
    """Tests for get_validated_credentials function."""

    @pytest.mark.asyncio
    async def test_valid_token_returns_credentials_with_user_id(self):
        """Test that valid token returns credentials with user_id."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 12345, "email": "user@example.com"}

        with patch("rossum_agent.api.dependencies.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            creds = await get_validated_credentials(
                x_rossum_token="valid_token", x_rossum_api_url="https://api.rossum.ai"
            )

            assert creds.token == "valid_token"
            assert creds.api_url == "https://api.rossum.ai"
            assert creds.user_id == "12345"

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self):
        """Test that invalid token returns 401."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("rossum_agent.api.dependencies.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            with pytest.raises(HTTPException) as exc_info:
                await get_validated_credentials(
                    x_rossum_token="invalid_token", x_rossum_api_url="https://api.rossum.ai"
                )

            assert exc_info.value.status_code == 401
            assert "Invalid Rossum API token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_api_error_returns_502(self):
        """Test that API error returns 502."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("rossum_agent.api.dependencies.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            with pytest.raises(HTTPException) as exc_info:
                await get_validated_credentials(x_rossum_token="token", x_rossum_api_url="https://api.rossum.ai")

            assert exc_info.value.status_code == 502
            assert "Failed to validate token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_connection_error_returns_502(self):
        """Test that connection error returns 502."""
        with patch("rossum_agent.api.dependencies.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            with pytest.raises(HTTPException) as exc_info:
                await get_validated_credentials(x_rossum_token="token", x_rossum_api_url="https://api.rossum.ai")

            assert exc_info.value.status_code == 502
            assert "Failed to connect to Rossum API" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_missing_user_id_returns_502(self):
        """Test that missing user ID in response returns 502."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"email": "user@example.com"}

        with patch("rossum_agent.api.dependencies.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            with pytest.raises(HTTPException) as exc_info:
                await get_validated_credentials(x_rossum_token="token", x_rossum_api_url="https://api.rossum.ai")

            assert exc_info.value.status_code == 502
            assert "did not return user ID" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_empty_headers_still_checked_first(self):
        """Test that empty headers are checked before API call."""
        with pytest.raises(HTTPException) as exc_info:
            await get_validated_credentials(x_rossum_token="", x_rossum_api_url="https://api.rossum.ai")

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_calls_correct_api_endpoint(self):
        """Test that the correct API endpoint is called."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 123}

        with patch("rossum_agent.api.dependencies.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            await get_validated_credentials(x_rossum_token="test_token", x_rossum_api_url="https://custom.rossum.app")

            mock_async_client.get.assert_called_once()
            call_args = mock_async_client.get.call_args
            assert "https://custom.rossum.app/v1/auth/user" in call_args[0]
            assert call_args.kwargs["headers"]["Authorization"] == "Bearer test_token"

    @pytest.mark.asyncio
    async def test_normalizes_api_url_with_v1_suffix(self):
        """Test that API URL with /v1 suffix is normalized to avoid duplication."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 456}

        with patch("rossum_agent.api.dependencies.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            await get_validated_credentials(x_rossum_token="test_token", x_rossum_api_url="https://us.rossum.app/v1")

            mock_async_client.get.assert_called_once()
            call_args = mock_async_client.get.call_args
            # Should normalize and use base URL
            assert call_args[0][0] == "https://us.rossum.app/v1/auth/user"

    @pytest.mark.asyncio
    async def test_preserves_original_api_url_with_v1_suffix(self):
        """Test that returned credentials preserve original API URL including /v1 path."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 789}

        with patch("rossum_agent.api.dependencies.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            creds = await get_validated_credentials(
                x_rossum_token="test_token", x_rossum_api_url="https://elis.develop.r8.lol/api/v1"
            )

            # Should preserve the original URL with /api/v1 for MCP server
            assert creds.api_url == "https://elis.develop.r8.lol/api/v1"


class TestGetValidatedCredentialsEdgeCases:
    """Additional edge case tests for get_validated_credentials."""

    @pytest.mark.asyncio
    async def test_invalid_json_response_returns_502(self):
        """Test that invalid JSON response returns 502."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "doc", 0)
        mock_response.text = "not valid json"

        with patch("rossum_agent.api.dependencies.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            with pytest.raises(HTTPException) as exc_info:
                await get_validated_credentials(x_rossum_token="token", x_rossum_api_url="https://api.rossum.ai")

            assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_api_url_with_trailing_slash_and_v1(self):
        """Test that API URL with trailing slash and /v1 is normalized correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 123}

        with patch("rossum_agent.api.dependencies.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            await get_validated_credentials(x_rossum_token="test_token", x_rossum_api_url="https://us.rossum.app/v1/")

            mock_async_client.get.assert_called_once()
            call_args = mock_async_client.get.call_args
            assert "/v1/v1/auth" not in call_args[0][0]


class TestValidateRossumApiUrl:
    """Tests for validate_rossum_api_url SSRF prevention."""

    def test_invalid_url_format_raises(self):
        """Test that invalid URL format raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_rossum_api_url("not a valid url ://malformed")

        assert exc_info.value.status_code == 400

    def test_allows_elis_rossum_ai(self):
        """Test that elis.rossum.ai is allowed."""
        result = validate_rossum_api_url("https://elis.rossum.ai")
        assert result == "https://elis.rossum.ai"

    def test_allows_rossum_app_subdomain(self):
        """Test that *.rossum.app domains are allowed."""
        result = validate_rossum_api_url("https://us.rossum.app")
        assert result == "https://us.rossum.app"

    def test_allows_elis_develop_r8_lol(self):
        """Test that elis.develop.r8.lol is allowed."""
        result = validate_rossum_api_url("https://elis.develop.r8.lol")
        assert result == "https://elis.develop.r8.lol"

    def test_rejects_http_scheme(self):
        """Test that HTTP (non-HTTPS) is rejected."""
        with pytest.raises(HTTPException) as exc_info:
            validate_rossum_api_url("http://elis.rossum.ai")

        assert exc_info.value.status_code == 400
        assert "HTTPS" in exc_info.value.detail

    def test_rejects_internal_ip(self):
        """Test that internal IPs are rejected (SSRF prevention)."""
        with pytest.raises(HTTPException) as exc_info:
            validate_rossum_api_url("https://10.0.0.5:8080")

        assert exc_info.value.status_code == 400

    def test_rejects_localhost(self):
        """Test that localhost is rejected."""
        with pytest.raises(HTTPException) as exc_info:
            validate_rossum_api_url("https://localhost:8000")

        assert exc_info.value.status_code == 400

    def test_rejects_arbitrary_domain(self):
        """Test that arbitrary domains are rejected."""
        with pytest.raises(HTTPException) as exc_info:
            validate_rossum_api_url("https://evil.com")

        assert exc_info.value.status_code == 400

    def test_rejects_similar_looking_domain(self):
        """Test that domains that look like Rossum but aren't are rejected."""
        with pytest.raises(HTTPException) as exc_info:
            validate_rossum_api_url("https://rossum.ai.evil.com")

        assert exc_info.value.status_code == 400

    def test_preserves_path_components(self):
        """Test that path components are preserved (only trailing /v1 is stripped)."""
        result = validate_rossum_api_url("https://elis.rossum.ai/api/v1")
        assert result == "https://elis.rossum.ai/api"

    def test_strips_only_v1_suffix(self):
        """Test that only trailing /v1 is stripped, rest of path preserved."""
        result = validate_rossum_api_url("https://elis.rossum.ai/v1")
        assert result == "https://elis.rossum.ai"

    def test_preserves_non_standard_port(self):
        """Test that non-443 ports are preserved if specified."""
        result = validate_rossum_api_url("https://elis.develop.r8.lol:8443")
        assert result == "https://elis.develop.r8.lol:8443"

    def test_rejects_missing_hostname(self):
        """Test that URLs without hostname are rejected."""
        with pytest.raises(HTTPException) as exc_info:
            validate_rossum_api_url("https://")

        assert exc_info.value.status_code == 400
