"""Tests for concurrent API requests from multiple clients."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rossum_agent.agent.models import FinalAnswerStep
from rossum_agent.api.models.schemas import StepEvent
from rossum_agent.api.services.agent_service import AgentService, _request_context


class TestConcurrentAgentService:
    """Tests for concurrent AgentService usage with context isolation."""

    @pytest.mark.asyncio
    async def test_concurrent_run_agent_isolated_contexts(self, tmp_path):
        """Test that concurrent run_agent calls have isolated per-request contexts.

        This verifies the contextvar-based state management properly isolates
        per-request state like output_dir and event_queue between concurrent requests.
        """
        agent_service = AgentService()

        observed_contexts: dict[str, dict] = {}

        async def capture_context_and_run(request_id: str, delay: float) -> list:
            """Run agent and capture its context state."""
            events = []

            mock_mcp_connection = MagicMock()
            mock_agent = MagicMock()
            mock_agent.tokens.total_input = 100
            mock_agent.tokens.total_output = 50
            mock_agent.tokens.last_main_input = 100
            mock_agent.memory = MagicMock()
            mock_agent.get_token_usage_breakdown.return_value = {}
            mock_agent.log_token_usage_summary = MagicMock()

            async def mock_run(prompt):
                ctx = _request_context.get()
                observed_contexts[request_id] = {
                    "output_dir": str(agent_service.get_output_dir(request_id)),
                    "has_queue": ctx.event_queue is not None,
                    "queue_id": id(ctx.event_queue) if ctx.event_queue else None,
                }
                await asyncio.sleep(delay)
                yield FinalAnswerStep(step_number=1, final_answer=f"Response for {request_id}")

            mock_agent.run = mock_run

            output_dir = tmp_path / f"output_{request_id}"
            output_dir.mkdir(exist_ok=True)

            with (
                patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
                patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
                patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=output_dir),
                patch("rossum_agent.api.services.agent_service.get_system_prompt", return_value="test prompt"),
                patch("rossum_agent.api.services.agent_service.extract_url_context") as mock_extract,
                patch.object(
                    AgentService,
                    "_setup_change_tracking",
                    new_callable=AsyncMock,
                    return_value=(None, None, "https://api.rossum.ai"),
                ),
            ):
                mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
                mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_create_agent.return_value = mock_agent
                mock_url_context = MagicMock()
                mock_url_context.is_empty.return_value = True
                mock_extract.return_value = mock_url_context

                async for event in agent_service.run_agent(
                    chat_id=request_id,
                    prompt=f"Test prompt for {request_id}",
                    conversation_history=[],
                    rossum_api_token="test_token",
                    rossum_api_base_url="https://api.rossum.ai",
                ):
                    events.append(event)

            return events

        task1 = asyncio.create_task(capture_context_and_run("request_1", delay=0.01))
        task2 = asyncio.create_task(capture_context_and_run("request_2", delay=0.005))

        results = await asyncio.gather(task1, task2)

        assert len(results[0]) > 0
        assert len(results[1]) > 0

        assert "request_1" in observed_contexts
        assert "request_2" in observed_contexts

        assert observed_contexts["request_1"]["output_dir"] != observed_contexts["request_2"]["output_dir"]
        assert observed_contexts["request_1"]["queue_id"] != observed_contexts["request_2"]["queue_id"]
        assert observed_contexts["request_1"]["has_queue"] is True
        assert observed_contexts["request_2"]["has_queue"] is True

    @pytest.mark.asyncio
    async def test_concurrent_requests_no_queue_none_error(self, tmp_path):
        """Test that a request finishing doesn't set another request's queue to None.

        This specifically tests the bug where concurrent requests would fail with:
        'NoneType' object has no attribute 'empty'
        """
        agent_service = AgentService()

        errors: list[str] = []

        async def run_with_varying_delay(request_id: str, delay: float) -> str:
            """Run agent with specified delay, return result or error."""
            mock_mcp_connection = MagicMock()
            mock_agent = MagicMock()
            mock_agent.tokens.total_input = 100
            mock_agent.tokens.total_output = 50
            mock_agent.tokens.last_main_input = 100
            mock_agent.memory = MagicMock()
            mock_agent.get_token_usage_breakdown.return_value = {}
            mock_agent.log_token_usage_summary = MagicMock()

            async def mock_run(prompt):
                await asyncio.sleep(delay)
                ctx = _request_context.get()
                if ctx.event_queue is None:
                    errors.append(f"{request_id}: Queue was None!")
                    raise AttributeError("'NoneType' object has no attribute 'empty'")
                yield FinalAnswerStep(step_number=1, final_answer=f"Done: {request_id}")

            mock_agent.run = mock_run

            output_dir = tmp_path / f"output_{request_id}"
            output_dir.mkdir(exist_ok=True)

            with (
                patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
                patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
                patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=output_dir),
                patch("rossum_agent.api.services.agent_service.get_system_prompt", return_value="test"),
                patch("rossum_agent.api.services.agent_service.extract_url_context") as mock_extract,
                patch.object(
                    AgentService,
                    "_setup_change_tracking",
                    new_callable=AsyncMock,
                    return_value=(None, None, "https://api.rossum.ai"),
                ),
            ):
                mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
                mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_create_agent.return_value = mock_agent
                mock_url_context = MagicMock()
                mock_url_context.is_empty.return_value = True
                mock_extract.return_value = mock_url_context

                try:
                    final_answer = None
                    async for event in agent_service.run_agent(
                        chat_id=request_id,
                        prompt=f"Test {request_id}",
                        conversation_history=[],
                        rossum_api_token="token",
                        rossum_api_base_url="https://api.rossum.ai",
                    ):
                        if isinstance(event, StepEvent) and event.type == "final_answer":
                            final_answer = event.content
                    return final_answer or "no answer"
                except AttributeError as e:
                    return f"ERROR: {e}"

        fast_task = asyncio.create_task(run_with_varying_delay("fast", delay=0.002))
        slow_task = asyncio.create_task(run_with_varying_delay("slow", delay=0.01))

        fast_result, slow_result = await asyncio.gather(fast_task, slow_task)

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert "ERROR" not in fast_result, f"Fast request failed: {fast_result}"
        assert "ERROR" not in slow_result, f"Slow request failed: {slow_result}"
        assert "Done: fast" in fast_result
        assert "Done: slow" in slow_result

    @pytest.mark.asyncio
    async def test_output_dir_property_returns_correct_context(self, tmp_path):
        """Test that the output_dir property returns the correct per-request value."""
        agent_service = AgentService()

        output_dirs_observed: dict[str, str] = {}

        async def capture_output_dir(request_id: str) -> None:
            mock_mcp_connection = MagicMock()
            mock_agent = MagicMock()
            mock_agent.tokens.total_input = 0
            mock_agent.tokens.total_output = 0
            mock_agent.tokens.last_main_input = 0
            mock_agent.memory = MagicMock()
            mock_agent.get_token_usage_breakdown.return_value = {}
            mock_agent.log_token_usage_summary = MagicMock()

            async def mock_run(prompt):
                output_dirs_observed[request_id] = str(agent_service.get_output_dir(request_id))
                yield FinalAnswerStep(step_number=1, final_answer="done")

            mock_agent.run = mock_run

            output_dir = tmp_path / f"output_{request_id}"
            output_dir.mkdir(exist_ok=True)

            with (
                patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
                patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
                patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=output_dir),
                patch("rossum_agent.api.services.agent_service.get_system_prompt", return_value="test"),
                patch("rossum_agent.api.services.agent_service.extract_url_context") as mock_extract,
                patch.object(
                    AgentService,
                    "_setup_change_tracking",
                    new_callable=AsyncMock,
                    return_value=(None, None, "https://api.rossum.ai"),
                ),
            ):
                mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
                mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_create_agent.return_value = mock_agent
                mock_url_context = MagicMock()
                mock_url_context.is_empty.return_value = True
                mock_extract.return_value = mock_url_context

                async for _ in agent_service.run_agent(
                    chat_id=request_id,
                    prompt="test",
                    conversation_history=[],
                    rossum_api_token="token",
                    rossum_api_base_url="https://api.rossum.ai",
                ):
                    pass

        task1 = asyncio.create_task(capture_output_dir("req_a"))
        task2 = asyncio.create_task(capture_output_dir("req_b"))

        await asyncio.gather(task1, task2)

        assert "req_a" in output_dirs_observed
        assert "req_b" in output_dirs_observed
        assert output_dirs_observed["req_a"] != output_dirs_observed["req_b"]
        assert "output_req_a" in output_dirs_observed["req_a"]
        assert "output_req_b" in output_dirs_observed["req_b"]
