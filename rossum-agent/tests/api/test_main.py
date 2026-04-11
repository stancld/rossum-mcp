"""Tests for API main module."""

from __future__ import annotations

import json
import logging
import sys
from unittest.mock import MagicMock, patch

import pytest
import uvicorn
from fastapi import status
from fastapi.testclient import TestClient
from rossum_agent.api.main import (
    MAX_REQUEST_SIZE,
    _create_storage,
    _run_gunicorn,
    app,
    lifespan,
    main,
    rate_limit_exceeded_handler,
)

from .conftest import create_mock_httpx_client


class TestRequestSizeLimitMiddleware:
    """Tests for RequestSizeLimitMiddleware."""

    def test_request_within_limit(self, mock_chat_service):
        """Test that requests within size limit pass through."""
        app.state.chat_service = mock_chat_service
        mock_chat_service.is_connected.return_value = True
        client = TestClient(app)

        response = client.get("/api/v1/health")
        assert response.status_code == status.HTTP_200_OK

    def test_request_exceeds_limit(self, mock_chat_service, mock_agent_service, mock_file_service):
        """Test that requests exceeding size limit are rejected with 413."""
        app.state.chat_service = mock_chat_service
        app.state.agent_service = mock_agent_service
        app.state.file_service = mock_file_service
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


class TestCreateStorage:
    """Tests for _create_storage factory function."""

    def test_creates_postgres_storage(self):
        """Test that _create_storage creates and initializes PostgresStorage."""
        with patch("rossum_agent.api.main.PostgresStorage") as mock_pg_cls:
            mock_pg_instance = MagicMock()
            mock_pg_cls.return_value = mock_pg_instance

            result = _create_storage()

            assert result is mock_pg_instance
            mock_pg_instance.initialize.assert_called_once()


class TestInitServices:
    """Tests for service initialization."""

    def test_init_services_creates_all_services(self):
        """Test that _init_services creates all services and stores them in app.state."""
        from fastapi import FastAPI
        from rossum_agent.api.main import _init_services

        mock_storage = MagicMock()

        with (
            patch("rossum_agent.api.main._create_storage", return_value=mock_storage),
            patch("rossum_agent.api.main.ChatService") as mock_chat_cls,
            patch("rossum_agent.api.main.AgentService") as mock_agent_cls,
            patch("rossum_agent.api.main.FileService") as mock_file_cls,
        ):
            mock_chat_instance = MagicMock()
            mock_chat_instance.storage = mock_storage
            mock_chat_cls.return_value = mock_chat_instance

            mock_agent_instance = MagicMock()
            mock_agent_cls.return_value = mock_agent_instance

            mock_file_instance = MagicMock()
            mock_file_cls.return_value = mock_file_instance

            test_app = FastAPI()
            _init_services(test_app)

            mock_chat_cls.assert_called_once_with(storage=mock_storage)
            mock_agent_cls.assert_called_once()
            mock_file_cls.assert_called_once_with(storage=mock_storage)

            assert test_app.state.chat_service is mock_chat_instance
            assert test_app.state.agent_service is mock_agent_instance
            assert test_app.state.file_service is mock_file_instance

    def test_init_services_creates_valkey_connection(self):
        """Test that _init_services creates valkey_connection for change tracking."""
        from fastapi import FastAPI
        from rossum_agent.api.main import _init_services

        mock_storage = MagicMock()
        mock_valkey = MagicMock()

        with (
            patch("rossum_agent.api.main._create_storage", return_value=mock_storage),
            patch("rossum_agent.api.main.ChatService") as mock_chat_cls,
            patch("rossum_agent.api.main.AgentService"),
            patch("rossum_agent.api.main.FileService"),
            patch("rossum_agent.api.main.ValkeyConnection", return_value=mock_valkey) as mock_valkey_cls,
        ):
            mock_chat_instance = MagicMock()
            mock_chat_instance.storage = mock_storage
            mock_chat_cls.return_value = mock_chat_instance

            test_app = FastAPI()
            _init_services(test_app)

            mock_valkey_cls.assert_called_once()
            assert test_app.state.valkey_connection is mock_valkey

    def test_init_services_skips_existing_valkey_connection(self):
        """Test that _init_services doesn't overwrite existing valkey_connection."""
        from fastapi import FastAPI
        from rossum_agent.api.main import _init_services

        mock_storage = MagicMock()
        existing_valkey = MagicMock()

        with (
            patch("rossum_agent.api.main._create_storage", return_value=mock_storage),
            patch("rossum_agent.api.main.ChatService") as mock_chat_cls,
            patch("rossum_agent.api.main.AgentService"),
            patch("rossum_agent.api.main.FileService"),
        ):
            mock_chat_instance = MagicMock()
            mock_chat_instance.storage = mock_storage
            mock_chat_cls.return_value = mock_chat_instance

            test_app = FastAPI()
            test_app.state.valkey_connection = existing_valkey
            _init_services(test_app)

            assert test_app.state.valkey_connection is existing_valkey


class TestLifespan:
    """Tests for lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_logs_storage_connected(self, caplog):
        """Test lifespan logs storage connection status when connected."""
        mock_chat_service = MagicMock()
        mock_chat_service.is_connected.return_value = True

        with (
            patch("rossum_agent.api.main._create_storage"),
            patch("rossum_agent.api.main.ChatService", return_value=mock_chat_service),
            patch("rossum_agent.api.main.AgentService"),
            patch("rossum_agent.api.main.FileService"),
            caplog.at_level(logging.INFO),
        ):
            async with lifespan(app):
                pass

        assert mock_chat_service.is_connected.called
        assert any("chat storage" in rec.message.lower() for rec in caplog.records)
        assert any(rec.levelno == logging.INFO for rec in caplog.records if "chat storage" in rec.message.lower())

    @pytest.mark.asyncio
    async def test_lifespan_logs_storage_disconnected(self, caplog):
        """Test lifespan logs warning when storage disconnected."""
        mock_chat_service = MagicMock()
        mock_chat_service.is_connected.return_value = False

        with (
            patch("rossum_agent.api.main._create_storage"),
            patch("rossum_agent.api.main.ChatService", return_value=mock_chat_service),
            patch("rossum_agent.api.main.AgentService"),
            patch("rossum_agent.api.main.FileService"),
            caplog.at_level(logging.WARNING),
        ):
            async with lifespan(app):
                pass

        assert mock_chat_service.is_connected.called
        assert any("chat storage" in rec.message.lower() for rec in caplog.records)
        assert any(rec.levelno == logging.WARNING for rec in caplog.records if "chat storage" in rec.message.lower())

    @pytest.mark.asyncio
    async def test_lifespan_closes_storage_on_shutdown(self):
        """Test lifespan closes storage on shutdown."""
        mock_storage = MagicMock()
        mock_chat_service = MagicMock()
        mock_chat_service.storage = mock_storage
        mock_chat_service.is_connected.return_value = True

        with (
            patch("rossum_agent.api.main._create_storage"),
            patch("rossum_agent.api.main.ChatService", return_value=mock_chat_service),
            patch("rossum_agent.api.main.AgentService"),
            patch("rossum_agent.api.main.FileService"),
        ):
            async with lifespan(app):
                pass

        mock_storage.close.assert_called_once()


class TestBuildCorsOriginRegex:
    """Tests for _build_cors_origin_regex function."""

    def test_default_cors_pattern(self):
        """Test that default CORS pattern includes rossum.app."""
        with patch.dict("os.environ", {"ADDITIONAL_ALLOWED_ROSSUM_HOSTS": ""}):
            from importlib import reload

            import rossum_agent.api.main as main_mod

            reload(main_mod)

            regex = main_mod._build_cors_origin_regex()
            import re

            pattern = re.compile(regex)
            assert pattern.match("https://us.rossum.app")
            assert pattern.match("https://eu.rossum.app")
            assert not pattern.match("https://test.review.r8.lol")

    def test_cors_with_additional_hosts(self):
        """Test that additional hosts are included in CORS pattern."""
        with patch.dict("os.environ", {"ADDITIONAL_ALLOWED_ROSSUM_HOSTS": r".*\.review\.r8\.lol"}):
            from importlib import reload

            import rossum_agent.api.main as main_mod

            reload(main_mod)

            regex = main_mod._build_cors_origin_regex()
            import re

            pattern = re.compile(regex)
            assert pattern.match("https://us.rossum.app")
            assert pattern.match("https://test.review.r8.lol")

    def test_cors_with_multiple_additional_hosts(self):
        """Test that multiple additional hosts are included in CORS pattern."""
        with patch.dict(
            "os.environ", {"ADDITIONAL_ALLOWED_ROSSUM_HOSTS": r".*\.review\.r8\.lol,.*\.staging\.example\.com"}
        ):
            from importlib import reload

            import rossum_agent.api.main as main_mod

            reload(main_mod)

            regex = main_mod._build_cors_origin_regex()
            import re

            pattern = re.compile(regex)
            assert pattern.match("https://us.rossum.app")
            assert pattern.match("https://test.review.r8.lol")
            assert pattern.match("https://app.staging.example.com")


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

    def test_main_default_server_is_uvicorn(self):
        """Test that default server is uvicorn for backwards compatibility."""
        with (
            patch.object(sys, "argv", ["rossum-agent-api"]),
            patch.object(uvicorn, "run") as mock_run,
        ):
            main()

            mock_run.assert_called_once()


class TestMainCLIGunicorn:
    """Tests for CLI entry point with gunicorn."""

    def test_main_runs_gunicorn(self):
        """Test that main runs gunicorn with correct parameters."""
        mock_app_class = MagicMock()
        mock_app_instance = MagicMock()
        mock_app_class.return_value = mock_app_instance

        with (
            patch.object(
                sys, "argv", ["rossum-agent-api", "--server", "gunicorn", "--host", "127.0.0.1", "--port", "8080"]
            ),
            patch.dict(
                "sys.modules", {"gunicorn": MagicMock(), "gunicorn.app": MagicMock(), "gunicorn.app.base": MagicMock()}
            ),
            patch("rossum_agent.api.main._run_gunicorn") as mock_run_gunicorn,
        ):
            main()

            mock_run_gunicorn.assert_called_once()
            args = mock_run_gunicorn.call_args[0][0]
            assert args.server == "gunicorn"
            assert args.host == "127.0.0.1"
            assert args.port == 8080

    def test_main_gunicorn_rejects_reload(self):
        """Test that gunicorn exits with error when --reload is used."""
        import argparse

        args = argparse.Namespace(
            host="127.0.0.1",
            port=8000,
            reload=True,
            workers=1,
            server="gunicorn",
        )

        with pytest.raises(SystemExit) as exc_info:
            _run_gunicorn(args)

        assert exc_info.value.code == 1

    def test_main_workers_flag_works_with_both_servers(self):
        """Test that --workers flag works with both uvicorn and gunicorn."""
        with (
            patch.object(sys, "argv", ["rossum-agent-api", "--workers", "4"]),
            patch.object(uvicorn, "run") as mock_uvicorn_run,
        ):
            main()
            assert mock_uvicorn_run.call_args[1]["workers"] == 4

        with (
            patch.object(sys, "argv", ["rossum-agent-api", "--server", "gunicorn", "--workers", "4"]),
            patch("rossum_agent.api.main._run_gunicorn") as mock_run_gunicorn,
        ):
            main()
            args = mock_run_gunicorn.call_args[0][0]
            assert args.workers == 4

    def test_run_gunicorn_standalone_application(self):
        """Test that StandaloneApplication is configured correctly."""
        import argparse

        from gunicorn.app.base import BaseApplication
        from rossum_agent.api.main import (
            GUNICORN_GRACEFUL_TIMEOUT,
            GUNICORN_KEEPALIVE,
            GUNICORN_TIMEOUT,
        )

        args = argparse.Namespace(
            host="127.0.0.1",
            port=8000,
            reload=False,
            workers=2,
            server="gunicorn",
        )

        captured_app = None

        def mock_run(self):
            nonlocal captured_app
            captured_app = self

        with patch.object(BaseApplication, "run", mock_run):
            _run_gunicorn(args)

        assert captured_app is not None
        assert captured_app.app_uri == "rossum_agent.api.main:app"
        assert captured_app.options["bind"] == "127.0.0.1:8000"
        assert captured_app.options["workers"] == 2
        assert captured_app.options["worker_class"] == "uvicorn_worker.UvicornWorker"
        assert captured_app.options["timeout"] == GUNICORN_TIMEOUT
        assert captured_app.options["graceful_timeout"] == GUNICORN_GRACEFUL_TIMEOUT
        assert captured_app.options["keepalive"] == GUNICORN_KEEPALIVE
