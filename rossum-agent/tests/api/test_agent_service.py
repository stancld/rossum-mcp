"""Tests for AgentService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rossum_agent.agent.models import AgentStep, ToolResult
from rossum_agent.api.models.schemas import StepEvent
from rossum_agent.api.services.agent_service import AgentService, convert_step_to_event


class TestConvertStepToEvent:
    """Tests for convert_step_to_event function."""

    def test_convert_error_step(self):
        """Test converting error step."""
        step = AgentStep(step_number=1, error="Something went wrong")
        event = convert_step_to_event(step)

        assert event.type == "error"
        assert event.step_number == 1
        assert event.content == "Something went wrong"
        assert event.is_final is True

    def test_convert_final_answer_step(self):
        """Test converting final answer step."""
        step = AgentStep(
            step_number=2,
            final_answer="Here is your answer",
            is_final=True,
        )
        event = convert_step_to_event(step)

        assert event.type == "final_answer"
        assert event.step_number == 2
        assert event.content == "Here is your answer"
        assert event.is_final is True

    def test_convert_tool_start_step(self):
        """Test converting tool start step."""
        step = AgentStep(
            step_number=1,
            current_tool="list_annotations",
            tool_progress=(1, 3),
        )
        event = convert_step_to_event(step)

        assert event.type == "tool_start"
        assert event.step_number == 1
        assert event.tool_name == "list_annotations"
        assert event.tool_progress == (1, 3)

    def test_convert_tool_result_step(self):
        """Test converting tool result step."""
        step = AgentStep(
            step_number=1,
            tool_results=[
                ToolResult(
                    tool_call_id="call_123", name="list_annotations", content='{"annotations": []}', is_error=False
                ),
            ],
            is_streaming=False,
        )
        event = convert_step_to_event(step)

        assert event.type == "tool_result"
        assert event.step_number == 1
        assert event.tool_name == "list_annotations"
        assert event.result == '{"annotations": []}'
        assert event.is_error is False

    def test_convert_tool_result_error_step(self):
        """Test converting tool result with error."""
        step = AgentStep(
            step_number=1,
            tool_results=[
                ToolResult(
                    tool_call_id="call_456", name="get_annotation", content="Annotation not found", is_error=True
                ),
            ],
            is_streaming=False,
        )
        event = convert_step_to_event(step)

        assert event.type == "tool_result"
        assert event.is_error is True

    def test_convert_thinking_step(self):
        """Test converting thinking step."""
        step = AgentStep(step_number=1, thinking="I'll help you with that...", is_streaming=True)
        event = convert_step_to_event(step)

        assert event.type == "thinking"
        assert event.step_number == 1
        assert event.content == "I'll help you with that..."
        assert event.is_streaming is True

    def test_convert_thinking_step_not_streaming(self):
        """Test converting thinking step when not streaming."""
        step = AgentStep(step_number=1, thinking="Complete thought", is_streaming=False)
        event = convert_step_to_event(step)

        assert event.type == "thinking"
        assert event.is_streaming is False


class TestAgentServiceBuildUpdatedHistory:
    """Tests for build_updated_history method."""

    def test_build_history_with_response(self):
        """Test building history with final response."""
        service = AgentService()
        existing = [{"role": "user", "content": "Previous message"}]

        updated = service.build_updated_history(
            existing_history=existing, user_prompt="New question", final_response="Here is the answer"
        )

        assert len(updated) == 3
        assert updated[0] == {"role": "user", "content": "Previous message"}
        assert updated[1] == {"role": "user", "content": "New question"}
        assert updated[2] == {"role": "assistant", "content": "Here is the answer"}

    def test_build_history_without_response(self):
        """Test building history without final response."""
        service = AgentService()
        existing = []

        updated = service.build_updated_history(existing_history=existing, user_prompt="Question", final_response=None)

        assert len(updated) == 1
        assert updated[0] == {"role": "user", "content": "Question"}

    def test_build_history_does_not_mutate_original(self):
        """Test that building history doesn't mutate original list."""
        service = AgentService()
        existing = [{"role": "user", "content": "Original"}]

        updated = service.build_updated_history(
            existing_history=existing, user_prompt="New", final_response="Response"
        )

        assert len(existing) == 1
        assert len(updated) == 3


class TestAgentServiceRestoreConversationHistory:
    """Tests for _restore_conversation_history method."""

    def test_restore_user_messages(self):
        """Test restoring user messages."""
        service = AgentService()
        mock_agent = MagicMock()

        history = [{"role": "user", "content": "Hello"}, {"role": "user", "content": "Another question"}]

        service._restore_conversation_history(mock_agent, history)

        assert mock_agent.add_user_message.call_count == 2
        mock_agent.add_user_message.assert_any_call("Hello")
        mock_agent.add_user_message.assert_any_call("Another question")

    def test_restore_assistant_messages(self):
        """Test restoring assistant messages."""
        service = AgentService()
        mock_agent = MagicMock()

        history = [
            {"role": "assistant", "content": "Hello back"},
            {"role": "assistant", "content": "Here to help"},
        ]

        service._restore_conversation_history(mock_agent, history)

        assert mock_agent.add_assistant_message.call_count == 2

    def test_restore_mixed_messages(self):
        """Test restoring mixed user and assistant messages."""
        service = AgentService()
        mock_agent = MagicMock()

        history = [
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"},
            {"role": "user", "content": "Question 2"},
            {"role": "assistant", "content": "Answer 2"},
        ]

        service._restore_conversation_history(mock_agent, history)

        assert mock_agent.add_user_message.call_count == 2
        assert mock_agent.add_assistant_message.call_count == 2

    def test_restore_ignores_other_roles(self):
        """Test that non-user/assistant messages are ignored."""
        service = AgentService()
        mock_agent = MagicMock()

        history = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Question"},
            {"role": "tool", "content": "Tool output"},
            {"role": "assistant", "content": "Answer"},
        ]

        service._restore_conversation_history(mock_agent, history)

        assert mock_agent.add_user_message.call_count == 1
        assert mock_agent.add_assistant_message.call_count == 1

    def test_restore_empty_history(self):
        """Test restoring empty history."""
        service = AgentService()
        mock_agent = MagicMock()

        service._restore_conversation_history(mock_agent, [])

        mock_agent.add_user_message.assert_not_called()
        mock_agent.add_assistant_message.assert_not_called()


class TestAgentServiceRunAgent:
    """Tests for run_agent method."""

    @pytest.mark.asyncio
    async def test_run_agent_yields_events(self):
        """Test that run_agent yields step events."""
        from rossum_agent.api.models.schemas import StreamDoneEvent

        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent._total_input_tokens = 100
        mock_agent._total_output_tokens = 50

        async def mock_run(prompt):
            yield AgentStep(step_number=1, thinking="Processing...", is_streaming=True)
            yield AgentStep(step_number=1, final_answer="Done!", is_final=True)

        mock_agent.run = mock_run

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            events = []
            async for event in service.run_agent(
                prompt="Test prompt",
                conversation_history=[],
                rossum_api_token="test_token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                events.append(event)

            assert len(events) == 3
            assert isinstance(events[0], StepEvent)
            assert events[0].type == "thinking"
            assert isinstance(events[1], StepEvent)
            assert events[1].type == "final_answer"
            assert isinstance(events[2], StreamDoneEvent)

    @pytest.mark.asyncio
    async def test_run_agent_handles_error(self):
        """Test that run_agent yields error event on exception."""
        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()

        async def mock_run(prompt):
            raise RuntimeError("Agent failed")
            yield  # pragma: no cover

        mock_agent.run = mock_run

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            events = []
            async for event in service.run_agent(
                prompt="Test prompt",
                conversation_history=[],
                rossum_api_token="test_token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                events.append(event)

            assert len(events) == 1
            assert isinstance(events[0], StepEvent)
            assert events[0].type == "error"
            assert "Agent failed" in events[0].content

    @pytest.mark.asyncio
    async def test_run_agent_restores_history(self):
        """Test that run_agent restores conversation history."""
        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent._total_input_tokens = 0
        mock_agent._total_output_tokens = 0

        async def mock_run(prompt):
            yield AgentStep(step_number=1, final_answer="Done", is_final=True)

        mock_agent.run = mock_run

        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch.object(service, "_restore_conversation_history") as mock_restore,
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            async for _ in service.run_agent(
                prompt="Test",
                conversation_history=history,
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                pass

            mock_restore.assert_called_once_with(mock_agent, history)
