"""Tests for request cancellation support."""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from rossum_agent.api.main import app
from rossum_agent.api.routes.messages import _watch_disconnect
from rossum_agent.api.services.agent_service import AgentService, _ChatRunState


class TestChatRunState:
    """Tests for _ChatRunState dataclass."""

    def test_defaults(self):
        state = _ChatRunState()
        assert isinstance(state.lock, asyncio.Lock)
        assert state.active_task is None
        assert state.run_id == 0


class TestAgentServiceRunRegistry:
    """Tests for AgentService run registration and cancellation."""

    def test_get_chat_run_state_creates_new(self):
        service = AgentService()
        state = service._get_chat_run_state("chat_1")
        assert isinstance(state, _ChatRunState)
        assert state is service._get_chat_run_state("chat_1")

    def test_get_chat_run_state_separate_chats(self):
        service = AgentService()
        state1 = service._get_chat_run_state("chat_1")
        state2 = service._get_chat_run_state("chat_2")
        assert state1 is not state2

    @pytest.mark.asyncio
    async def test_register_run_assigns_task_and_increments_id(self):
        service = AgentService()
        run_id = await service._register_run("chat_1")
        assert run_id == 1
        state = service._chat_runs["chat_1"]
        assert state.active_task is asyncio.current_task()
        assert state.run_id == 1

    @pytest.mark.asyncio
    async def test_register_run_increments_id_each_call(self):
        service = AgentService()
        id1 = await service._register_run("chat_1")
        await service._clear_run("chat_1", id1)
        id2 = await service._register_run("chat_1")
        assert id2 == 2

    @pytest.mark.asyncio
    async def test_register_run_cancels_previous_task(self):
        service = AgentService()

        async def long_running():
            await asyncio.sleep(100)

        task = asyncio.create_task(long_running())
        state = service._get_chat_run_state("chat_1")
        state.active_task = task
        state.run_id = 1

        run_id = await service._register_run("chat_1")
        assert run_id == 2
        assert task.cancelling() or task.cancelled() or task.done()
        await service._clear_run("chat_1", run_id)

    @pytest.mark.asyncio
    async def test_clear_run_clears_matching_id(self):
        service = AgentService()
        run_id = await service._register_run("chat_1")
        await service._clear_run("chat_1", run_id)
        assert service._chat_runs["chat_1"].active_task is None

    @pytest.mark.asyncio
    async def test_clear_run_ignores_mismatched_id(self):
        service = AgentService()
        run_id = await service._register_run("chat_1")
        await service._clear_run("chat_1", run_id - 1)
        assert service._chat_runs["chat_1"].active_task is not None

    def test_cancel_run_no_state(self):
        service = AgentService()
        assert service.cancel_run("nonexistent") is False

    def test_cancel_run_no_active_task(self):
        service = AgentService()
        service._get_chat_run_state("chat_1")
        assert service.cancel_run("chat_1") is False

    @pytest.mark.asyncio
    async def test_cancel_run_cancels_active_task(self):
        service = AgentService()

        async def long_running():
            await asyncio.sleep(100)

        task = asyncio.create_task(long_running())
        state = service._get_chat_run_state("chat_1")
        state.active_task = task
        state.run_id = 1

        result = service.cancel_run("chat_1")
        assert result is True
        assert task.cancelling() or task.cancelled() or task.done()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_cancel_run_done_task_returns_false(self):
        service = AgentService()

        async def quick():
            return

        task = asyncio.create_task(quick())
        await task

        state = service._get_chat_run_state("chat_1")
        state.active_task = task
        state.run_id = 1

        assert service.cancel_run("chat_1") is False


class TestWatchDisconnect:
    """Tests for _watch_disconnect helper."""

    @pytest.mark.asyncio
    async def test_watch_disconnect_calls_cancel_on_disconnect(self):
        request = MagicMock()
        call_count = 0

        async def is_disconnected():
            nonlocal call_count
            call_count += 1
            return call_count >= 2

        request.is_disconnected = is_disconnected
        agent_service = MagicMock()
        agent_service.cancel_run = MagicMock(return_value=True)

        await _watch_disconnect(request, "chat_1", agent_service)
        agent_service.cancel_run.assert_called_once_with("chat_1")

    @pytest.mark.asyncio
    async def test_watch_disconnect_exits_cleanly_on_cancellation(self):
        """Test that _watch_disconnect handles CancelledError gracefully."""
        request = MagicMock()

        async def never_disconnected():
            return False

        request.is_disconnected = never_disconnected
        agent_service = MagicMock()

        task = asyncio.create_task(_watch_disconnect(request, "chat_1", agent_service))
        # Let the watcher start polling
        await asyncio.sleep(0.1)
        task.cancel()
        # Should not raise — CancelledError is suppressed inside _watch_disconnect
        with contextlib.suppress(asyncio.CancelledError):
            await task

        agent_service.cancel_run.assert_not_called()


class TestCancelEndpoint:
    """Tests for POST /chats/{chat_id}/cancel endpoint."""

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_chat_returns_404(self, mock_httpx_success):
        mock_chat_service = MagicMock()
        mock_chat_service.chat_exists.return_value = False

        mock_agent_service = MagicMock()

        app.state.chat_service = mock_chat_service
        app.state.agent_service = mock_agent_service

        with patch("rossum_agent.api.dependencies.httpx.AsyncClient", return_value=mock_httpx_success):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/chats/chat_nonexistent/cancel",
                    headers={"X-Rossum-Token": "test_token", "X-Rossum-Api-Url": "https://api.rossum.ai"},
                )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_existing_chat_no_active_run(self, mock_httpx_success):
        mock_chat_service = MagicMock()
        mock_chat_service.chat_exists.return_value = True

        mock_agent_service = MagicMock()
        mock_agent_service.cancel_run.return_value = False

        app.state.chat_service = mock_chat_service
        app.state.agent_service = mock_agent_service

        with patch("rossum_agent.api.dependencies.httpx.AsyncClient", return_value=mock_httpx_success):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/chats/chat_123/cancel",
                    headers={"X-Rossum-Token": "test_token", "X-Rossum-Api-Url": "https://api.rossum.ai"},
                )

        assert response.status_code == 200
        assert response.json() == {"cancelled": False}

    @pytest.mark.asyncio
    async def test_cancel_existing_chat_with_active_run(self, mock_httpx_success):
        mock_chat_service = MagicMock()
        mock_chat_service.chat_exists.return_value = True

        mock_agent_service = MagicMock()
        mock_agent_service.cancel_run.return_value = True

        app.state.chat_service = mock_chat_service
        app.state.agent_service = mock_agent_service

        with patch("rossum_agent.api.dependencies.httpx.AsyncClient", return_value=mock_httpx_success):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/chats/chat_123/cancel",
                    headers={"X-Rossum-Token": "test_token", "X-Rossum-Api-Url": "https://api.rossum.ai"},
                )

        assert response.status_code == 200
        assert response.json() == {"cancelled": True}


async def _noop_watch_disconnect(request, chat_id, agent_service):
    """No-op replacement for _watch_disconnect in tests."""


class TestSendMessageCancellation:
    """Tests for cancellation behavior in send_message."""

    @pytest.mark.asyncio
    async def test_send_message_passes_chat_id_to_run_agent(self, mock_httpx_success, mock_run_agent_factory):
        from rossum_agent.storage import ChatData, ChatMetadata

        calls, mock_run_agent = mock_run_agent_factory()

        mock_chat_service = MagicMock()
        mock_chat_service.get_chat_data.return_value = ChatData(
            messages=[], metadata=ChatMetadata(mcp_mode="read-only")
        )
        mock_chat_service.save_messages.return_value = True

        mock_agent_service = MagicMock()
        mock_agent_service.run_agent = mock_run_agent
        mock_agent_service.get_output_dir.return_value = None
        mock_agent_service.build_updated_history.return_value = []

        app.state.chat_service = mock_chat_service
        app.state.agent_service = mock_agent_service

        with (
            patch("rossum_agent.api.dependencies.httpx.AsyncClient", return_value=mock_httpx_success),
            patch("rossum_agent.api.routes.messages._watch_disconnect", _noop_watch_disconnect),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/chats/chat_42/messages",
                    json={"content": "Hello"},
                    headers={"X-Rossum-Token": "test_token", "X-Rossum-Api-Url": "https://api.rossum.ai"},
                )

        assert response.status_code == 200
        assert len(calls) == 1
        assert calls[0]["chat_id"] == "chat_42"

    @pytest.mark.asyncio
    async def test_cancelled_request_does_not_save_history(self, mock_httpx_success):
        from rossum_agent.storage import ChatData, ChatMetadata

        mock_chat_service = MagicMock()
        mock_chat_service.get_chat_data.return_value = ChatData(
            messages=[], metadata=ChatMetadata(mcp_mode="read-only")
        )

        async def mock_run_agent_that_gets_cancelled(*args, **kwargs):
            raise asyncio.CancelledError
            yield

        mock_agent_service = MagicMock()
        mock_agent_service.run_agent = mock_run_agent_that_gets_cancelled
        mock_agent_service.get_output_dir.return_value = None

        app.state.chat_service = mock_chat_service
        app.state.agent_service = mock_agent_service

        with (
            patch("rossum_agent.api.dependencies.httpx.AsyncClient", return_value=mock_httpx_success),
            patch("rossum_agent.api.routes.messages._watch_disconnect", _noop_watch_disconnect),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/chats/chat_42/messages",
                    json={"content": "Hello"},
                    headers={"X-Rossum-Token": "test_token", "X-Rossum-Api-Url": "https://api.rossum.ai"},
                )

        assert response.status_code == 200
        mock_chat_service.save_messages.assert_not_called()
