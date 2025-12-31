"""Tests for API main module."""

from __future__ import annotations

import json
import logging
import sys
from unittest.mock import MagicMock, patch

import pytest
import rossum_agent.api.main as main_module
import uvicorn
from fastapi import status
from fastapi.testclient import TestClient
from rossum_agent.api.main import (
    MAX_REQUEST_SIZE,
    app,
    get_agent_service,
    get_chat_service,
    get_file_service,
    main,
    rate_limit_exceeded_handler,
    shutdown_event,
    startup_event,
)
from rossum_agent.api.routes import health

from .conftest import create_mock_httpx_client


class TestRequestSizeLimitMiddleware:
    """Tests for RequestSizeLimitMiddleware."""

    def test_request_within_limit(self, mock_chat_service):
        """Test that requests within size limit pass through."""
        health.set_chat_service_getter(lambda: mock_chat_service)
        mock_chat_service.is_connected.return_value = True
        client = TestClient(app)

        response = client.get("/api/v1/health")
        assert response.status_code == status.HTTP_200_OK

    def test_request_exceeds_limit(self):
        """Test that requests exceeding size limit are rejected with 413."""
        client = TestClient(app)

        large_content = "x" * (MAX_REQUEST_SIZE + 1)

        with patch("rossum_agent.api.dependencies.httpx.AsyncClient") as mock_httpx:
            mock_httpx.return_value = create_mock_httpx_client()
            response = client.post(
                "/api/v1/chats",
                content=large_content,
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(len(large_content)),
                    "X-Rossum-Token": "test",
                    "X-Rossum-Api-Url": "https://api.rossum.ai",
                },
            )

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        assert "Request body too large" in response.json()["detail"]


class TestRateLimitExceededHandler:
    """Tests for rate_limit_exceeded_handler."""

    def test_rate_limit_exceeded_returns_429(self):
        """Test that rate limit exceeded returns 429 with proper detail."""
        mock_request = MagicMock()
        mock_request.scope = {"type": "http", "path": "/test"}

        class MockRateLimitExceeded(Exception):
            detail = "10 per minute"

        exc = MockRateLimitExceeded()

        response = rate_limit_exceeded_handler(mock_request, exc)  # type: ignore[arg-type]

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        body = json.loads(response.body)
        assert "Rate limit exceeded" in body["detail"]


class TestServiceGetters:
    """Tests for service getter functions.

    Note: The autouse fixture reset_main_service_singletons handles resetting
    the singleton state before and after each test.
    """

    def test_get_chat_service_creates_singleton(self):
        """Test that get_chat_service returns same instance."""
        with patch("rossum_agent.api.main.ChatService") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            result1 = get_chat_service()
            result2 = get_chat_service()

            mock_cls.assert_called_once()
            assert result1 is result2

    def test_get_agent_service_creates_singleton(self):
        """Test that get_agent_service returns same instance."""
        with patch("rossum_agent.api.main.AgentService") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            result1 = get_agent_service()
            result2 = get_agent_service()

            mock_cls.assert_called_once()
            assert result1 is result2

    def test_get_file_service_creates_singleton(self):
        """Test that get_file_service returns same instance."""
        with (
            patch("rossum_agent.api.main.FileService") as mock_file_cls,
            patch("rossum_agent.api.main.ChatService") as mock_chat_cls,
        ):
            mock_chat_instance = MagicMock()
            mock_chat_instance.storage = MagicMock()
            mock_chat_cls.return_value = mock_chat_instance

            mock_file_instance = MagicMock()
            mock_file_cls.return_value = mock_file_instance

            result1 = get_file_service()
            result2 = get_file_service()

            mock_file_cls.assert_called_once()
            assert result1 is result2


class TestStartupShutdown:
    """Tests for startup and shutdown events.

    Note: The autouse fixture reset_main_service_singletons handles resetting
    the singleton state before and after each test.
    """

    @pytest.mark.asyncio
    async def test_startup_logs_redis_connected(self, caplog):
        """Test startup event logs Redis connection status when connected."""
        mock_chat_service = MagicMock()
        mock_chat_service.is_connected.return_value = True

        with (
            patch("rossum_agent.api.main.ChatService", return_value=mock_chat_service),
            caplog.at_level(logging.INFO),
        ):
            await startup_event()

        assert mock_chat_service.is_connected.called
        assert any("redis" in rec.message.lower() for rec in caplog.records)
        assert any(rec.levelno == logging.INFO for rec in caplog.records if "redis" in rec.message.lower())

    @pytest.mark.asyncio
    async def test_startup_logs_redis_disconnected(self, caplog):
        """Test startup event logs warning when Redis disconnected."""
        mock_chat_service = MagicMock()
        mock_chat_service.is_connected.return_value = False

        with (
            patch("rossum_agent.api.main.ChatService", return_value=mock_chat_service),
            caplog.at_level(logging.WARNING),
        ):
            await startup_event()

        assert mock_chat_service.is_connected.called
        assert any("redis" in rec.message.lower() for rec in caplog.records)
        assert any(rec.levelno == logging.WARNING for rec in caplog.records if "redis" in rec.message.lower())

    @pytest.mark.asyncio
    async def test_shutdown_closes_storage(self):
        """Test shutdown event closes storage when chat_service exists."""
        mock_storage = MagicMock()
        mock_chat_service = MagicMock()
        mock_chat_service.storage = mock_storage
        main_module._chat_service = mock_chat_service

        await shutdown_event()
        mock_storage.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_handles_no_chat_service(self, caplog):
        """Test shutdown event handles case when chat_service is None."""
        with caplog.at_level(logging.DEBUG):
            await shutdown_event()

        error_records = [rec for rec in caplog.records if rec.levelno >= logging.ERROR]
        assert len(error_records) == 0


class TestMainCLI:
    """Tests for CLI entry point."""

    def test_main_runs_uvicorn(self):
        """Test that main runs uvicorn with correct parameters."""
        with (
            patch.object(sys, "argv", ["rossum-agent-api", "--host", "127.0.0.1", "--port", "9000"]),
            patch.object(uvicorn, "run") as mock_run,
        ):
            main()

            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == "rossum_agent.api.main:app"
            assert call_args[1]["host"] == "127.0.0.1"
            assert call_args[1]["port"] == 9000

    def test_main_with_reload_flag(self):
        """Test that main handles --reload flag."""
        with (
            patch.object(sys, "argv", ["rossum-agent-api", "--reload"]),
            patch.object(uvicorn, "run") as mock_run,
        ):
            main()

            call_args = mock_run.call_args
            assert call_args[0][0] == "rossum_agent.api.main:app"
            assert call_args[1]["reload"] is True
            assert call_args[1]["workers"] == 1

    def test_main_with_workers(self):
        """Test that main handles --workers flag."""
        with (
            patch.object(sys, "argv", ["rossum-agent-api", "--workers", "4"]),
            patch.object(uvicorn, "run") as mock_run,
        ):
            main()

            call_args = mock_run.call_args
            assert call_args[0][0] == "rossum_agent.api.main:app"
            assert call_args[1]["workers"] == 4
