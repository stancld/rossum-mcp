"""Tests for graceful shutdown behavior."""

from __future__ import annotations

import asyncio
import signal
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from rossum_agent.agent.models import FinalAnswerStep, StepType, TextDeltaStep
from rossum_agent.api.main import (
    _drain_and_shutdown,
    _install_sigterm_handler,
    app,
)
from rossum_agent.api.models.schemas import StreamDoneEvent
from rossum_agent.api.shutdown import shutdown_state

from .conftest import create_mock_httpx_client


class TestGracefulShutdownMiddleware:
    """Tests for GracefulShutdownMiddleware."""

    def test_normal_request_passes_through(self, mock_chat_service):
        """Requests pass through when not shutting down."""
        app.state.chat_service = mock_chat_service
        mock_chat_service.is_connected.return_value = True
        client = TestClient(app)

        response = client.get("/api/v1/health")
        assert response.status_code == status.HTTP_200_OK

    def test_rejects_new_requests_during_shutdown(self, mock_chat_service, mock_agent_service, mock_file_service):
        """New requests get 503 during graceful shutdown."""
        app.state.chat_service = mock_chat_service
        app.state.agent_service = mock_agent_service
        app.state.file_service = mock_file_service
        shutdown_state.shutting_down = True
        client = TestClient(app)

        with patch("rossum_agent.api.dependencies.httpx.AsyncClient") as mock_httpx:
            mock_httpx.return_value = create_mock_httpx_client()
            response = client.post(
                "/api/v1/chats",
                headers={"X-Rossum-Token": "test", "X-Rossum-Api-Url": "https://api.rossum.ai"},
            )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json()["detail"] == "Server is shutting down"

    def test_health_endpoint_accessible_during_shutdown(self, mock_chat_service):
        """Health endpoint remains accessible during shutdown but returns 503 for K8s readiness probes."""
        app.state.chat_service = mock_chat_service
        mock_chat_service.is_connected.return_value = True
        shutdown_state.shutting_down = True
        client = TestClient(app)

        response = client.get("/api/v1/health")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json()["status"] == "shutting_down"


class TestHealthDuringShutdown:
    """Tests for health endpoint shutdown status."""

    def test_health_returns_shutting_down_with_503(self, mock_chat_service):
        """Health returns shutting_down status with 503 when SIGTERM received."""
        app.state.chat_service = mock_chat_service
        mock_chat_service.is_connected.return_value = True
        shutdown_state.shutting_down = True
        client = TestClient(app)

        response = client.get("/api/v1/health")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "shutting_down"
        assert data["storage_connected"] is True

    def test_health_normal_when_not_shutting_down(self, mock_chat_service):
        """Health returns healthy when not shutting down."""
        app.state.chat_service = mock_chat_service
        mock_chat_service.is_connected.return_value = True
        client = TestClient(app)

        response = client.get("/api/v1/health")
        assert response.json()["status"] == "healthy"


class TestSigtermHandler:
    """Tests for SIGTERM signal handler installation."""

    def test_sigterm_sets_shutting_down_flag(self):
        """SIGTERM handler sets the shutting_down flag."""
        loop = asyncio.new_event_loop()

        handler_called = False

        def mock_add_signal_handler(sig, callback):
            nonlocal handler_called
            if sig == signal.SIGTERM:
                # Simulate SIGTERM by calling the callback directly
                callback()
                handler_called = True

        mock_app = MagicMock()
        shutdown_state.shutting_down = False

        with (
            patch("asyncio.get_running_loop", return_value=loop),
            patch.object(loop, "add_signal_handler", side_effect=mock_add_signal_handler),
            patch.object(loop, "remove_signal_handler"),
            patch("asyncio.ensure_future"),
        ):
            _install_sigterm_handler(mock_app)

        assert handler_called
        assert shutdown_state.shutting_down is True
        loop.close()

    @pytest.mark.asyncio
    async def test_drain_and_shutdown_exits_when_no_active_requests(self):
        """Drain task triggers uvicorn shutdown via SIGINT when no active requests remain."""
        shutdown_state.active_requests = 0

        with patch("os.kill") as mock_kill:
            await _drain_and_shutdown()

        mock_kill.assert_called_once()
        assert mock_kill.call_args[0][1] == signal.SIGINT

    @pytest.mark.asyncio
    async def test_drain_waits_for_active_requests(self):
        """Drain task waits until active requests reach zero before terminating."""
        shutdown_state.active_requests = 2

        call_count = 0
        original_sleep = asyncio.sleep

        async def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            shutdown_state.active_requests -= 1
            await original_sleep(0)

        with patch("os.kill") as mock_kill, patch("asyncio.sleep", side_effect=fake_sleep):
            await _drain_and_shutdown()

        assert call_count == 2
        mock_kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_drain_timeout_forces_shutdown(self):
        """Drain task forces shutdown after timeout even with active requests."""
        shutdown_state.active_requests = 5
        sleep_count = 0
        original_sleep = asyncio.sleep

        async def counting_sleep(seconds):
            nonlocal sleep_count
            sleep_count += 1
            await original_sleep(0)

        with (
            patch("os.kill") as mock_kill,
            patch("asyncio.sleep", side_effect=counting_sleep),
        ):
            await _drain_and_shutdown()

        # Should have looped 120 times (600s / 5s interval) then forced shutdown
        assert sleep_count == 120
        assert shutdown_state.active_requests == 5  # never drained
        mock_kill.assert_called_once()
        assert mock_kill.call_args[0][1] == signal.SIGINT


class TestStreamingRequestTracking:
    """Tests that the middleware tracks SSE streaming responses for their full lifetime."""

    def test_active_requests_tracked_during_sse_stream(self, mock_chat_service, mock_agent_service, mock_file_service):
        """Active request count stays > 0 while an SSE stream is open.

        This verifies the middleware wraps the full ASGI call (not just the
        initial response), so streaming responses are counted until they finish.
        """
        active_during_stream: list[int] = []

        async def mock_run_agent(*args, **kwargs):
            # Record active_requests while mid-stream — should be >= 1
            active_during_stream.append(shutdown_state.active_requests)
            yield TextDeltaStep(
                step_number=1,
                step_type=StepType.INTERMEDIATE,
                text_delta="Thinking...",
                accumulated_text="Thinking...",
            )
            active_during_stream.append(shutdown_state.active_requests)
            yield FinalAnswerStep(step_number=2, final_answer="Done!", input_tokens=100, output_tokens=50)
            yield StreamDoneEvent(total_steps=2, input_tokens=100, output_tokens=50)

        app.state.chat_service = mock_chat_service
        app.state.agent_service = mock_agent_service
        app.state.file_service = mock_file_service

        mock_agent_service.run_agent = mock_run_agent
        mock_agent_service.get_output_dir.return_value = None
        mock_agent_service.build_updated_history.return_value = []
        mock_chat_service.load_messages.return_value = []
        mock_chat_service.save_messages = MagicMock()
        mock_chat_service.update_chat_title = MagicMock()

        client = TestClient(app)

        with patch("rossum_agent.api.dependencies.httpx.AsyncClient") as mock_httpx:
            mock_httpx.return_value = create_mock_httpx_client()
            response = client.post(
                "/api/v1/chats/test-chat/messages",
                json={"content": "Hello"},
                headers={"X-Rossum-Token": "test", "X-Rossum-Api-Url": "https://api.rossum.ai"},
            )

        assert response.status_code == status.HTTP_200_OK
        # The request was counted as active while the stream was being produced
        assert all(count >= 1 for count in active_during_stream), (
            f"Expected active_requests >= 1 during stream, got {active_during_stream}"
        )
        # After the response is fully consumed, the counter should be back to 0
        assert shutdown_state.active_requests == 0

    def test_sse_stream_rejected_during_shutdown(self, mock_chat_service, mock_agent_service, mock_file_service):
        """New SSE streaming requests are rejected with 503 during shutdown."""
        app.state.chat_service = mock_chat_service
        app.state.agent_service = mock_agent_service
        app.state.file_service = mock_file_service
        shutdown_state.shutting_down = True

        client = TestClient(app)

        with patch("rossum_agent.api.dependencies.httpx.AsyncClient") as mock_httpx:
            mock_httpx.return_value = create_mock_httpx_client()
            response = client.post(
                "/api/v1/chats/test-chat/messages",
                json={"content": "Hello"},
                headers={"X-Rossum-Token": "test", "X-Rossum-Api-Url": "https://api.rossum.ai"},
            )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
