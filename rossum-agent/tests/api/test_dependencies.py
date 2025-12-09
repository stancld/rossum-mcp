"""Tests for API dependencies."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException
from rossum_agent.api.dependencies import (
    RossumCredentials,
    get_rossum_credentials,
    get_validated_credentials,
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

            await get_validated_credentials(x_rossum_token="test_token", x_rossum_api_url="https://custom.rossum.ai")

            mock_async_client.get.assert_called_once()
            call_args = mock_async_client.get.call_args
            assert "https://custom.rossum.ai/v1/auth/user" in call_args[0]
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

            await get_validated_credentials(
                x_rossum_token="test_token", x_rossum_api_url="https://us.api.rossum.ai/v1"
            )

            mock_async_client.get.assert_called_once()
            call_args = mock_async_client.get.call_args
            # Should be /v1/auth/user, not /v1/v1/auth/user
            assert call_args[0][0] == "https://us.api.rossum.ai/v1/auth/user"
