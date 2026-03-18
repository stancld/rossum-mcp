"""Tests for AgentService."""

from __future__ import annotations

import asyncio
import base64
import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rossum_agent.agent.memory import AgentMemory, MemoryStep, TaskStep
from rossum_agent.agent.models import (
    ErrorStep,
    FinalAnswerStep,
    TaskSnapshotPart,
    ThinkingBlockData,
    ThinkingStep,
    ToolCall,
    ToolResult,
    ToolResultStep,
)
from rossum_agent.api.models.schemas import ImageContent
from rossum_agent.api.services.agent_service import (
    AgentService,
    _log_commit_hook,
)
from rossum_agent.change_tracking.models import ConfigCommit, EntityChange


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


class TestAgentServiceRestoreConversationHistoryNewFormat:
    """Tests for _restore_conversation_history with new memory format."""

    def test_restore_new_format_sets_memory_directly(self):
        """Test that new format history sets agent.memory directly."""
        service = AgentService()
        mock_agent = MagicMock()
        mock_agent.memory = AgentMemory()

        history = [
            {"type": "task_step", "task": "What is 2+2?"},
            {
                "type": "memory_step",
                "step_number": 1,
                "text": "The answer is 4.",
                "tool_calls": [],
                "tool_results": [],
                "input_tokens": 100,
                "output_tokens": 50,
            },
        ]

        service._restore_conversation_history(mock_agent, history)

        assert isinstance(mock_agent.memory, AgentMemory)
        assert len(mock_agent.memory.steps) == 2
        assert isinstance(mock_agent.memory.steps[0], TaskStep)
        assert mock_agent.memory.steps[0].task == "What is 2+2?"
        assert isinstance(mock_agent.memory.steps[1], MemoryStep)
        assert mock_agent.memory.steps[1].text == "The answer is 4."

    def test_restore_new_format_with_tool_calls(self):
        """Test restoring new format with tool calls and results."""
        service = AgentService()
        mock_agent = MagicMock()
        mock_agent.memory = AgentMemory()

        history = [
            {"type": "task_step", "task": "Get the weather"},
            {
                "type": "memory_step",
                "step_number": 1,
                "text": "Let me check the weather.",
                "tool_calls": [{"id": "tc1", "name": "get_weather", "arguments": {"city": "Prague"}}],
                "tool_results": [
                    {"tool_call_id": "tc1", "name": "get_weather", "content": "Sunny, 25C", "is_error": False}
                ],
                "input_tokens": 200,
                "output_tokens": 100,
            },
            {
                "type": "memory_step",
                "step_number": 2,
                "text": "It's sunny and 25°C in Prague.",
                "tool_calls": [],
                "tool_results": [],
            },
        ]

        service._restore_conversation_history(mock_agent, history)

        assert len(mock_agent.memory.steps) == 3
        step1 = mock_agent.memory.steps[1]
        assert len(step1.tool_calls) == 1
        assert step1.tool_calls[0].name == "get_weather"
        assert step1.tool_calls[0].arguments == {"city": "Prague"}
        assert len(step1.tool_results) == 1
        assert step1.tool_results[0].content == "Sunny, 25C"

    def test_restore_new_format_multi_turn(self):
        """Test restoring multi-turn conversation in new format."""
        service = AgentService()
        mock_agent = MagicMock()
        mock_agent.memory = AgentMemory()

        history = [
            {"type": "task_step", "task": "Hello"},
            {"type": "memory_step", "step_number": 1, "text": "Hi there!"},
            {"type": "task_step", "task": "What can you do?"},
            {"type": "memory_step", "step_number": 2, "text": "I can help with many things."},
            {"type": "task_step", "task": "Tell me a joke"},
            {"type": "memory_step", "step_number": 3, "text": "Why did the programmer quit? No arrays!"},
        ]

        service._restore_conversation_history(mock_agent, history)

        assert len(mock_agent.memory.steps) == 6
        messages = mock_agent.memory.write_to_messages()
        assert len(messages) == 6
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"

    def test_restore_detects_legacy_format(self):
        """Test that legacy format (with 'role') uses old restore method."""
        service = AgentService()
        mock_agent = MagicMock()

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        service._restore_conversation_history(mock_agent, history)

        mock_agent.add_user_message.assert_called_once_with("Hello")
        mock_agent.add_assistant_message.assert_called_once_with("Hi there!")


class TestAgentServiceBuildUpdatedHistoryWithMemory:
    """Tests for build_updated_history using stored memory."""

    def test_build_history_uses_stored_memory(self):
        """Test that build_updated_history uses memory when provided."""
        service = AgentService()

        memory = AgentMemory()
        memory.add_task("What is 2+2?")
        memory.steps.append(MemoryStep(step_number=1, text="The answer is 4."))

        updated = service.build_updated_history(
            existing_history=[], user_prompt="ignored", final_response="ignored", memory=memory
        )

        assert len(updated) == 2
        assert updated[0]["type"] == "task_step"
        assert updated[0]["task"] == "What is 2+2?"
        assert updated[1]["type"] == "memory_step"
        assert updated[1]["text"] == "The answer is 4."

    def test_build_history_preserves_tool_calls_and_results(self):
        """Test that tool calls and results are preserved in history."""
        service = AgentService()

        memory = AgentMemory()
        memory.add_task("Check the weather")
        memory.steps.append(
            MemoryStep(
                step_number=1,
                text="Let me check...",
                tool_calls=[ToolCall(id="tc1", name="weather", arguments={"city": "NYC"})],
                tool_results=[ToolResult(tool_call_id="tc1", name="weather", content="Rainy")],
            )
        )
        memory.steps.append(MemoryStep(step_number=2, text="It's rainy in NYC."))

        updated = service.build_updated_history(
            existing_history=[], user_prompt="ignored", final_response="ignored", memory=memory
        )

        assert len(updated) == 3
        assert updated[0]["type"] == "task_step"
        assert updated[1]["type"] == "memory_step"
        assert updated[1]["text"] == "Let me check..."
        assert updated[1]["tool_calls"] == [{"id": "tc1", "name": "weather", "arguments": {"city": "NYC"}}]
        assert updated[1]["tool_results"] == [
            {"tool_call_id": "tc1", "name": "weather", "content": "Rainy", "is_error": False}
        ]
        assert updated[2]["text"] == "It's rainy in NYC."

    def test_build_history_preserves_steps_with_only_tool_calls(self):
        """Test that memory steps with tool calls but no text are preserved."""
        service = AgentService()

        memory = AgentMemory()
        memory.add_task("Do something")
        memory.steps.append(
            MemoryStep(
                step_number=1,
                text=None,
                tool_calls=[ToolCall(id="tc1", name="tool", arguments={})],
                tool_results=[ToolResult(tool_call_id="tc1", name="tool", content="result")],
            )
        )
        memory.steps.append(MemoryStep(step_number=2, text="Final answer"))

        updated = service.build_updated_history(
            existing_history=[], user_prompt="ignored", final_response="ignored", memory=memory
        )

        assert len(updated) == 3
        assert updated[0]["type"] == "task_step"
        assert updated[1]["type"] == "memory_step"
        assert updated[1]["text"] is None
        assert updated[1]["tool_calls"] == [{"id": "tc1", "name": "tool", "arguments": {}}]
        assert updated[1]["tool_results"] == [
            {"tool_call_id": "tc1", "name": "tool", "content": "result", "is_error": False}
        ]
        assert updated[2]["type"] == "memory_step"
        assert updated[2]["text"] == "Final answer"

    def test_build_history_preserves_steps_with_only_tool_results(self):
        """Test that memory steps with tool results but no text are preserved."""
        service = AgentService()

        memory = AgentMemory()
        memory.add_task("Do something")
        memory.steps.append(
            MemoryStep(
                step_number=1,
                text=None,
                tool_calls=[],
                tool_results=[ToolResult(tool_call_id="tc1", name="tool", content="result")],
            )
        )
        memory.steps.append(MemoryStep(step_number=2, text="Final answer"))

        updated = service.build_updated_history(
            existing_history=[], user_prompt="ignored", final_response="ignored", memory=memory
        )

        assert len(updated) == 3
        assert updated[0]["type"] == "task_step"
        assert updated[1]["type"] == "memory_step"
        assert updated[1]["text"] is None
        assert updated[1]["tool_calls"] == []
        assert updated[1]["tool_results"] == [
            {"tool_call_id": "tc1", "name": "tool", "content": "result", "is_error": False}
        ]
        assert updated[2]["type"] == "memory_step"
        assert updated[2]["text"] == "Final answer"

    def test_build_history_falls_back_when_no_memory(self):
        """Test fallback to legacy behavior when memory is None."""
        service = AgentService()

        existing = [{"role": "user", "content": "Previous"}]
        updated = service.build_updated_history(
            existing_history=existing, user_prompt="New question", final_response="Answer"
        )

        assert len(updated) == 3
        assert updated[0] == {"role": "user", "content": "Previous"}
        assert updated[1] == {"role": "user", "content": "New question"}
        assert updated[2] == {"role": "assistant", "content": "Answer"}

    def test_build_history_preserves_thinking_blocks(self):
        """Test that thinking_blocks are preserved in lean history for extended thinking continuity."""
        service = AgentService()

        memory = AgentMemory()
        memory.add_task("Analyze this document")
        memory.steps.append(
            MemoryStep(
                step_number=1,
                text="Let me analyze...",
                thinking_blocks=[
                    ThinkingBlockData(thinking="I need to consider...", signature="sig123"),
                    ThinkingBlockData(thinking="Also important...", signature="sig456"),
                ],
                tool_calls=[ToolCall(id="tc1", name="get_doc", arguments={})],
                tool_results=[ToolResult(tool_call_id="tc1", name="get_doc", content="doc content")],
            )
        )

        updated = service.build_updated_history(
            existing_history=[], user_prompt="ignored", final_response="ignored", memory=memory
        )

        assert len(updated) == 2
        assert updated[1]["type"] == "memory_step"
        assert updated[1]["text"] == "Let me analyze..."
        assert updated[1]["tool_calls"] == [{"id": "tc1", "name": "get_doc", "arguments": {}}]
        assert updated[1]["tool_results"] == [
            {"tool_call_id": "tc1", "name": "get_doc", "content": "doc content", "is_error": False}
        ]
        assert len(updated[1]["thinking_blocks"]) == 2
        assert updated[1]["thinking_blocks"][0]["thinking"] == "I need to consider..."
        assert updated[1]["thinking_blocks"][0]["signature"] == "sig123"

    def test_build_history_includes_step_with_only_thinking_blocks(self):
        """Test that memory steps with only thinking_blocks (no text) are preserved."""
        service = AgentService()

        memory = AgentMemory()
        memory.add_task("Process request")
        memory.steps.append(
            MemoryStep(
                step_number=1,
                text=None,
                thinking_blocks=[ThinkingBlockData(thinking="Internal reasoning", signature="sig789")],
                tool_calls=[ToolCall(id="tc1", name="tool", arguments={})],
            )
        )

        updated = service.build_updated_history(
            existing_history=[], user_prompt="ignored", final_response="ignored", memory=memory
        )

        assert len(updated) == 2
        assert updated[1]["type"] == "memory_step"
        assert updated[1]["text"] is None
        assert len(updated[1]["thinking_blocks"]) == 1
        assert updated[1]["thinking_blocks"][0]["signature"] == "sig789"


class TestAgentServiceRunAgent:
    """Tests for run_agent method."""

    @pytest.mark.asyncio
    async def test_run_agent_yields_events(self, tmp_path):
        """Test that run_agent yields step events."""
        from rossum_agent.api.models.schemas import StreamDoneEvent, TokenUsageBreakdown

        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens.total_input = 100
        mock_agent.tokens.total_output = 50
        mock_agent.tokens.last_main_input = 80
        mock_agent.get_token_usage_breakdown.return_value = TokenUsageBreakdown.from_raw_counts(
            total_input=100, total_output=50, main_input=100, main_output=50, sub_input=0, sub_output=0, sub_by_tool={}
        )

        async def mock_run(prompt):
            yield ThinkingStep(step_number=1, thinking="Processing...")
            yield FinalAnswerStep(step_number=1, final_answer="Done!")

        mock_agent.run = mock_run

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
            patch.object(AgentService, "_try_create_config_commit", return_value=None),
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            events = []
            async for event in service.run_agent(
                chat_id="test-chat",
                prompt="Test prompt",
                conversation_history=[],
                rossum_api_token="test_token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                events.append(event)

            assert len(events) == 3
            assert isinstance(events[0], ThinkingStep)
            assert isinstance(events[1], FinalAnswerStep)
            assert isinstance(events[2], StreamDoneEvent)
            done_event = events[2]
            assert done_event.max_input_tokens == 1_000_000
            assert done_event.context_usage_fraction == 80 / 1_000_000

    @pytest.mark.asyncio
    async def test_run_agent_handles_error(self, tmp_path):
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
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
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

            events = []
            async for event in service.run_agent(
                chat_id="test-chat",
                prompt="Test prompt",
                conversation_history=[],
                rossum_api_token="test_token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                events.append(event)

            assert len(events) == 1
            assert isinstance(events[0], ErrorStep)
            assert "Agent failed" in events[0].error

    @pytest.mark.asyncio
    async def test_run_agent_restores_history(self, tmp_path):
        """Test that run_agent restores conversation history."""
        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens.total_input = 0
        mock_agent.tokens.total_output = 0
        mock_agent.tokens.last_main_input = 0

        async def mock_run(prompt):
            yield FinalAnswerStep(step_number=1, final_answer="Done")

        mock_agent.run = mock_run

        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
            patch.object(service, "_restore_conversation_history") as mock_restore,
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

            async for _ in service.run_agent(
                chat_id="test-chat",
                prompt="Test",
                conversation_history=history,
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                pass

            mock_restore.assert_called_once_with(mock_agent, history)

    @pytest.mark.asyncio
    async def test_run_agent_creates_output_dir(self, tmp_path):
        """Test that run_agent creates and sets session output directory."""
        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens.total_input = 0
        mock_agent.tokens.total_output = 0
        mock_agent.tokens.total_cache_creation = 0
        mock_agent.tokens.total_cache_read = 0
        mock_agent.tokens.last_main_input = 0
        mock_agent.get_token_usage_breakdown.return_value = {}
        mock_agent.log_token_usage_summary = MagicMock()
        mock_agent.memory = MagicMock()

        async def mock_run(prompt):
            yield FinalAnswerStep(step_number=1, final_answer="Done")

        mock_agent.run = mock_run

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch(
                "rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path
            ) as mock_create_dir,
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

            async for _ in service.run_agent(
                chat_id="test-chat",
                prompt="Test",
                conversation_history=[],
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                pass

            mock_create_dir.assert_called_once()
            assert service.get_output_dir("test-chat") == tmp_path

    @pytest.mark.asyncio
    async def test_run_agent_memory_available_after_run_for_pop(self, tmp_path):
        """Test that run memory remains available until consumed by pop_last_memory."""
        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens.total_input = 0
        mock_agent.tokens.total_output = 0
        mock_agent.tokens.total_cache_creation = 0
        mock_agent.tokens.total_cache_read = 0
        mock_agent.tokens.last_main_input = 0
        mock_agent.get_token_usage_breakdown.return_value = {}
        mock_agent.log_token_usage_summary = MagicMock()

        memory = AgentMemory()
        memory.add_task("Test")
        mock_agent.memory = memory

        async def mock_run(prompt):
            yield FinalAnswerStep(step_number=1, final_answer="Done")

        mock_agent.run = mock_run

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
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

            async for _ in service.run_agent(
                chat_id="test-chat",
                prompt="Test",
                conversation_history=[],
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                pass

            assert service.pop_last_memory("test-chat") is memory
            assert service.pop_last_memory("test-chat") is None

    @pytest.mark.asyncio
    async def test_run_agent_seeds_last_main_input_from_previous_turn(self, tmp_path):
        """Test that last_main_input is carried forward across turns."""
        from rossum_agent.api.models.schemas import StreamDoneEvent, TokenUsageBreakdown

        service = AgentService()

        # Simulate a previous turn that ended with last_main_input = 50_000
        state = service._get_chat_run_state("test-chat")
        state.last_main_input_tokens = 50_000

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens = MagicMock()
        mock_agent.tokens.total_input = 60_000
        mock_agent.tokens.total_output = 1_000
        mock_agent.tokens.last_main_input = 60_000
        mock_agent.tokens.total_cache_creation = 0
        mock_agent.tokens.total_cache_read = 0
        mock_agent.get_token_usage_breakdown.return_value = TokenUsageBreakdown.from_raw_counts(
            total_input=60_000,
            total_output=1_000,
            main_input=60_000,
            main_output=1_000,
            sub_input=0,
            sub_output=0,
            sub_by_tool={},
        )
        mock_agent.log_token_usage_summary = MagicMock()
        mock_agent.memory = MagicMock()

        seeded_value = None

        async def mock_run(prompt):
            nonlocal seeded_value
            # Capture the seeded value before the agent's first API call overwrites it
            seeded_value = mock_agent.tokens.last_main_input
            # Simulate the agent updating last_main_input after API call
            mock_agent.tokens.last_main_input = 60_000
            yield FinalAnswerStep(step_number=1, final_answer="Done")

        mock_agent.run = mock_run

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
            patch.object(AgentService, "_try_create_config_commit", return_value=None),
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            events = []
            async for event in service.run_agent(
                chat_id="test-chat",
                prompt="Test",
                conversation_history=[],
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                events.append(event)

            # Verify seeded value was set before agent.run()
            assert seeded_value == 50_000

            # Verify last_main_input_tokens is updated after the run
            assert state.last_main_input_tokens == 60_000

            # Verify the done event carries the final context_usage_fraction
            done_event = next(e for e in events if isinstance(e, StreamDoneEvent))
            assert done_event.context_usage_fraction == 60_000 / 1_000_000

    @pytest.mark.asyncio
    async def test_register_run_clears_stale_memory(self):
        """Test that stale memory is cleared at start of a new run."""
        service = AgentService()
        state = service._get_chat_run_state("test-chat")
        state.last_memory = AgentMemory()

        run_id = await service._register_run("test-chat")
        assert state.last_memory is None

        await service._clear_run("test-chat", run_id)

    def test_output_dir_initially_none(self):
        """Test that output_dir is None before running agent."""
        service = AgentService()
        assert service.get_output_dir("test-chat") is None

    def test_get_last_memory_returns_none_for_unknown_chat(self):
        """Test that get_last_memory returns None for a chat with no run state."""
        service = AgentService()
        assert service.get_last_memory("unknown-chat") is None

    def test_get_last_memory_returns_memory_without_clearing(self):
        """Test that get_last_memory returns memory but does not clear it."""
        service = AgentService()
        state = service._get_chat_run_state("test-chat")
        memory = AgentMemory()
        state.last_memory = memory

        assert service.get_last_memory("test-chat") is memory
        # Memory is still available after get (unlike pop)
        assert service.get_last_memory("test-chat") is memory

    @pytest.mark.asyncio
    async def test_run_agent_memory_updated_after_each_completed_step(self, tmp_path):
        """Test that last_memory is updated after each completed step during streaming."""
        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens.total_input = 0
        mock_agent.tokens.total_output = 0
        mock_agent.tokens.total_cache_creation = 0
        mock_agent.tokens.total_cache_read = 0
        mock_agent.tokens.last_main_input = 0
        mock_agent.get_token_usage_breakdown.return_value = {}
        mock_agent.log_token_usage_summary = MagicMock()

        memory = AgentMemory()
        mock_agent.memory = memory

        async def mock_run(prompt):
            yield ToolResultStep(
                step_number=1,
                tool_calls=[ToolCall(id="tc_1", name="list_queues", arguments={})],
                tool_results=[ToolResult(tool_call_id="tc_1", name="list_queues", content="[queue1]")],
            )
            yield FinalAnswerStep(step_number=2, final_answer="Done")

        mock_agent.run = mock_run

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
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

            memories_seen = []
            async for _ in service.run_agent(
                chat_id="test-chat",
                prompt="Test",
                conversation_history=[],
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                # Capture memory state after each yielded event
                mem = service.get_last_memory("test-chat")
                memories_seen.append(mem)

            # Memory should have been set during streaming (at least once non-None)
            assert any(m is memory for m in memories_seen)


class TestAgentServiceBuildUserContent:
    """Tests for AgentService._build_user_content method."""

    def test_text_only_returns_string(self):
        """Test that text-only prompt returns a plain string."""
        service = AgentService()
        result = service._build_user_content("Hello, agent!", None)
        assert result == "Hello, agent!"
        assert isinstance(result, str)

    def test_with_images_returns_list(self):
        """Test that prompt with images returns a content list."""
        service = AgentService()
        images = [ImageContent(media_type="image/png", data="aGVsbG8=")]
        result = service._build_user_content("Analyze this", images)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["type"] == "image"
        assert result[0]["source"]["type"] == "base64"
        assert result[0]["source"]["media_type"] == "image/png"
        assert result[0]["source"]["data"] == "aGVsbG8="
        assert result[1]["type"] == "text"
        assert result[1]["text"] == "Analyze this"

    def test_with_multiple_images(self):
        """Test that multiple images are included in correct order."""
        service = AgentService()
        images = [
            ImageContent(media_type="image/png", data="aW1hZ2Ux"),
            ImageContent(media_type="image/jpeg", data="aW1hZ2Uy"),
        ]
        result = service._build_user_content("Compare these images", images)

        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0]["source"]["data"] == "aW1hZ2Ux"
        assert result[1]["source"]["data"] == "aW1hZ2Uy"
        assert result[2]["text"] == "Compare these images"

    def test_empty_images_list_returns_string(self):
        """Test that empty images list returns plain string."""
        service = AgentService()
        result = service._build_user_content("Hello", [])
        assert result == "Hello"
        assert isinstance(result, str)

    def test_with_text_file_paths_returns_list(self):
        """Test that text file paths produce a content list with workspace note."""
        service = AgentService()
        paths = [Path("/mock/output/readme.md"), Path("/mock/output/data.json")]
        result = service._build_user_content("Analyze these", None, text_file_paths=paths)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["type"] == "text"
        assert "readable via open()" in result[0]["text"]
        assert "/mock/output/readme.md" in result[0]["text"]
        assert "/mock/output/data.json" in result[0]["text"]
        assert result[1]["text"] == "Analyze these"

    def test_with_empty_text_file_paths_returns_string(self):
        """Test that empty text_file_paths returns plain string."""
        service = AgentService()
        result = service._build_user_content("Hello", None, text_file_paths=[])
        assert result == "Hello"
        assert isinstance(result, str)

    def test_with_documents_and_text_file_paths(self):
        """Test that both documents and text files produce separate notes."""
        from rossum_agent.api.models.schemas import DocumentContent

        service = AgentService()
        docs = [DocumentContent(media_type="application/pdf", data="aGVsbG8=", filename="invoice.pdf")]
        text_paths = [Path("/mock/output/notes.md")]
        result = service._build_user_content(
            "Process all", None, documents=docs, output_dir=Path("/mock/output"), text_file_paths=text_paths
        )

        assert isinstance(result, list)
        assert len(result) == 3
        assert "Uploaded documents" in result[0]["text"]
        assert "Text files saved to workspace" in result[1]["text"]
        assert result[2]["text"] == "Process all"

    def test_text_documents_inlined_in_context(self):
        """Test that text/plain and text/markdown documents are inlined, not just path-referenced."""
        from rossum_agent.api.models.schemas import DocumentContent

        service = AgentService()
        docs = [
            DocumentContent(
                media_type="text/markdown",
                data=base64.b64encode(b"# Hello\nWorld").decode(),
                filename="readme.md",
            ),
            DocumentContent(
                media_type="text/plain",
                data=base64.b64encode(b"plain text content").decode(),
                filename="notes.txt",
            ),
        ]
        result = service._build_user_content("Read these", None, documents=docs, output_dir=Path("/mock/output"))

        assert isinstance(result, list)
        assert len(result) == 2  # inlined block + prompt
        inlined = result[0]["text"]
        assert '<file_content path="readme.md">' in inlined
        assert "# Hello\nWorld" in inlined
        assert '<file_content path="notes.txt">' in inlined
        assert "plain text content" in inlined
        assert "Uploaded documents" not in inlined
        assert result[1]["text"] == "Read these"

    def test_mixed_text_and_binary_documents(self):
        """Test that text documents are inlined while binary documents are path-referenced."""
        from rossum_agent.api.models.schemas import DocumentContent

        service = AgentService()
        docs = [
            DocumentContent(
                media_type="text/markdown",
                data=base64.b64encode(b"# Markdown").decode(),
                filename="doc.md",
            ),
            DocumentContent(
                media_type="application/pdf",
                data="aGVsbG8=",
                filename="invoice.pdf",
            ),
        ]
        result = service._build_user_content("Process all", None, documents=docs, output_dir=Path("/mock/output"))

        assert isinstance(result, list)
        assert len(result) == 3  # inlined text + doc reference + prompt
        assert '<file_content path="doc.md">' in result[0]["text"]
        assert "# Markdown" in result[0]["text"]
        assert "Uploaded documents" in result[1]["text"]
        assert "invoice.pdf" in result[1]["text"]
        assert result[2]["text"] == "Process all"


class TestAgentServiceBuildUpdatedHistoryWithImages:
    """Tests for build_updated_history with images."""

    def test_build_history_with_images(self):
        """Test building history with images included."""
        service = AgentService()

        existing = [{"role": "user", "content": "Previous message"}]
        images = [ImageContent(media_type="image/png", data="aGVsbG8=")]

        updated = service.build_updated_history(
            existing_history=existing,
            user_prompt="Analyze this image",
            final_response="Analysis complete",
            images=images,
        )

        assert len(updated) == 3
        assert updated[0] == {"role": "user", "content": "Previous message"}
        assert isinstance(updated[1]["content"], list)
        assert len(updated[1]["content"]) == 2
        assert updated[1]["content"][0]["type"] == "image"
        assert updated[1]["content"][0]["source"]["data"] == "aGVsbG8="
        assert updated[1]["content"][1]["type"] == "text"
        assert updated[1]["content"][1]["text"] == "Analyze this image"
        assert updated[2] == {"role": "assistant", "content": "Analysis complete"}

    def test_build_history_without_images(self):
        """Test building history without images returns text-only content."""
        service = AgentService()

        existing = []

        updated = service.build_updated_history(
            existing_history=existing, user_prompt="Text only", final_response="Response", images=None
        )

        assert len(updated) == 2
        assert updated[0] == {"role": "user", "content": "Text only"}


class TestAgentServiceParseStoredContent:
    """Tests for _parse_stored_content method."""

    def test_parse_string_content(self):
        """Test parsing string content returns string."""
        service = AgentService()
        result = service._parse_stored_content("Hello, world!")
        assert result == "Hello, world!"

    def test_parse_multimodal_content(self):
        """Test parsing multimodal content with images and text."""
        service = AgentService()
        stored_content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": "aGVsbG8=",
                },
            },
            {"type": "text", "text": "Analyze this"},
        ]

        result = service._parse_stored_content(stored_content)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["type"] == "image"
        assert result[0]["source"]["type"] == "base64"
        assert result[0]["source"]["media_type"] == "image/png"
        assert result[0]["source"]["data"] == "aGVsbG8="
        assert result[1]["type"] == "text"
        assert result[1]["text"] == "Analyze this"

    def test_parse_empty_list_returns_empty_string(self):
        """Test parsing empty list returns empty string."""
        service = AgentService()
        result = service._parse_stored_content([])
        assert result == ""

    def test_parse_unknown_block_types_ignored(self):
        """Test that unknown block types are ignored."""
        service = AgentService()
        stored_content = [
            {"type": "unknown", "data": "something"},
            {"type": "text", "text": "Valid text"},
        ]

        result = service._parse_stored_content(stored_content)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["type"] == "text"


class TestAgentServiceRestoreConversationHistoryWithImages:
    """Tests for _restore_conversation_history with multimodal content."""

    def test_restore_multimodal_user_message(self):
        """Test restoring user messages with images."""
        service = AgentService()
        mock_agent = MagicMock()

        history = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": "aGVsbG8="},
                    },
                    {"type": "text", "text": "What's in this image?"},
                ],
            },
            {"role": "assistant", "content": "I see a document."},
        ]

        service._restore_conversation_history(mock_agent, history)

        mock_agent.add_user_message.assert_called_once()
        call_args = mock_agent.add_user_message.call_args[0][0]
        assert isinstance(call_args, list)
        assert len(call_args) == 2
        assert call_args[0]["type"] == "image"
        assert call_args[1]["type"] == "text"
        mock_agent.add_assistant_message.assert_called_once_with("I see a document.")

    def test_restore_mixed_text_and_multimodal_messages(self):
        """Test restoring a mix of text-only and multimodal messages."""
        service = AgentService()
        mock_agent = MagicMock()

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "img1"}},
                    {"type": "text", "text": "What's this?"},
                ],
            },
            {"role": "assistant", "content": "That's a chart."},
        ]

        service._restore_conversation_history(mock_agent, history)

        assert mock_agent.add_user_message.call_count == 2
        assert mock_agent.add_assistant_message.call_count == 2

        first_call = mock_agent.add_user_message.call_args_list[0][0][0]
        assert first_call == "Hello"

        second_call = mock_agent.add_user_message.call_args_list[1][0][0]
        assert isinstance(second_call, list)
        assert len(second_call) == 2


class TestAgentServiceSubAgentCallbacks:
    """Tests for sub-agent callback handling.

    Callbacks use call_soon_threadsafe to marshal events onto the event loop,
    so tests must be async and allow time for the scheduled callback to run.
    """

    async def test_on_task_snapshot_with_queue(self):
        """Test _on_task_snapshot puts TaskSnapshotEvent on queue."""
        from rossum_agent.api.services.agent_service import _request_context, _RequestContext

        service = AgentService()
        ctx = _RequestContext()
        ctx.event_queue = asyncio.Queue(maxsize=100)
        ctx.event_loop = asyncio.get_running_loop()
        _request_context.set(ctx)

        snapshot = [{"id": "1", "subject": "Deploy", "status": "completed"}]
        service._on_task_snapshot(snapshot)
        await asyncio.sleep(0)

        assert ctx.event_queue.qsize() == 1
        event = ctx.event_queue.get_nowait()
        assert isinstance(event, TaskSnapshotPart)
        assert len(event.tasks) == 1
        assert event.tasks[0].id == "1"

    def test_on_task_snapshot_without_queue(self):
        """Test _on_task_snapshot does nothing when queue is None."""
        from rossum_agent.api.services.agent_service import _request_context, _RequestContext

        service = AgentService()
        ctx = _RequestContext()
        ctx.event_queue = None
        _request_context.set(ctx)

        service._on_task_snapshot([{"id": "1", "subject": "Task", "status": "pending"}])

    async def test_on_task_snapshot_queue_full(self, caplog):
        """Test _on_task_snapshot logs warning when queue is full."""

        from rossum_agent.api.services.agent_service import _request_context, _RequestContext

        service = AgentService()
        ctx = _RequestContext()
        ctx.event_queue = asyncio.Queue(maxsize=1)
        ctx.event_loop = asyncio.get_running_loop()
        _request_context.set(ctx)

        ctx.event_queue.put_nowait(TaskSnapshotPart(tasks=[]))

        with caplog.at_level(logging.WARNING):
            service._on_task_snapshot([{"id": "1", "subject": "Task", "status": "pending"}])
            await asyncio.sleep(0)

        assert "queue full" in caplog.text.lower()


class TestAgentServiceRunAgentWithImages:
    """Tests for run_agent with images parameter."""

    @pytest.mark.asyncio
    async def test_run_agent_logs_image_count(self, tmp_path, caplog):
        """Test that run_agent logs the number of images."""

        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens.total_input = 0
        mock_agent.tokens.total_output = 0
        mock_agent.tokens.last_main_input = 0

        async def mock_run(prompt):
            yield FinalAnswerStep(step_number=1, final_answer="Done")

        mock_agent.run = mock_run

        images = [
            ImageContent(media_type="image/png", data="aW1hZ2Ux"),
            ImageContent(media_type="image/jpeg", data="aW1hZ2Uy"),
        ]

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
            patch.object(
                AgentService,
                "_setup_change_tracking",
                new_callable=AsyncMock,
                return_value=(None, None, "https://api.rossum.ai"),
            ),
            caplog.at_level(logging.INFO),
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            async for _ in service.run_agent(
                chat_id="test-chat",
                prompt="Test",
                conversation_history=[],
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
                images=images,
            ):
                pass

        assert "2 images" in caplog.text


class TestAgentServiceUrlContext:
    """Tests for URL context handling in run_agent."""

    @pytest.mark.asyncio
    async def test_run_agent_with_url_context(self, tmp_path):
        """Test that run_agent appends URL context to system prompt."""
        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens.total_input = 0
        mock_agent.tokens.total_output = 0
        mock_agent.tokens.last_main_input = 0

        async def mock_run(prompt):
            yield FinalAnswerStep(step_number=1, final_answer="Done")

        mock_agent.run = mock_run

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
            patch("rossum_agent.api.services.agent_service.get_system_prompt", return_value="Base prompt"),
            patch("rossum_agent.api.services.agent_service.extract_url_context") as mock_extract,
            patch("rossum_agent.api.services.agent_service.format_context_for_prompt", return_value="URL context"),
            patch.object(
                AgentService,
                "_setup_change_tracking",
                new_callable=AsyncMock,
                return_value=(None, None, "https://api.rossum.ai"),
            ),
        ):
            mock_url_context = MagicMock()
            mock_url_context.is_empty.return_value = False
            mock_extract.return_value = mock_url_context

            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            async for _ in service.run_agent(
                chat_id="test-chat",
                prompt="Test",
                conversation_history=[],
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
                rossum_url="https://elis.rossum.ai/annotations/123",
            ):
                pass

            call_kwargs = mock_create_agent.call_args
            assert "URL context" in call_kwargs.kwargs["system_prompt"]


class TestAfterLoopHook:
    """Tests for the log_commit hook invocation."""

    @pytest.mark.asyncio
    async def test_log_commit_hook_no_changes(self):
        commit = ConfigCommit(
            hash="deadbeef1234",
            chat_id="test",
            timestamp=datetime.now(),
            message="Updated queue settings",
            user_request="Update settings",
            environment="https://api.rossum.ai",
            changes=[],
        )
        result = await _log_commit_hook(commit)
        assert result == "✓ deadbeef — Updated queue settings"

    async def test_log_commit_hook_with_changes(self):
        commit = ConfigCommit(
            hash="cafebabe5678",
            chat_id="test",
            timestamp=datetime.now(),
            message="Configured schema",
            user_request="Configure",
            environment="https://api.rossum.ai",
            changes=[
                EntityChange(
                    entity_type="queue",
                    entity_id="1",
                    entity_name="Main Queue",
                    operation="update",
                    before={},
                    after={},
                ),
                EntityChange(
                    entity_type="schema",
                    entity_id="2",
                    entity_name="Invoice",
                    operation="create",
                    before=None,
                    after={},
                ),
                EntityChange(
                    entity_type="hook",
                    entity_id="3",
                    entity_name="Old Hook",
                    operation="delete",
                    before={},
                    after=None,
                ),
            ],
        )
        result = await _log_commit_hook(commit)
        assert result is not None
        lines = result.splitlines()
        assert lines[0] == "✓ cafebabe — Configured schema"
        assert lines[1] == '  [~] queue "Main Queue"'
        assert lines[2] == '  [+] schema "Invoice"'
        assert lines[3] == '  [-] hook "Old Hook"'

    @pytest.mark.asyncio
    async def test_run_agent_calls_hook_on_commit(self, tmp_path):
        """Test that the log_commit hook is called when a commit is created."""
        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens.total_input = 0
        mock_agent.tokens.total_output = 0
        mock_agent.tokens.total_cache_creation = 0
        mock_agent.tokens.total_cache_read = 0
        mock_agent.tokens.last_main_input = 0
        mock_agent.get_token_usage_breakdown.return_value = {}
        mock_agent.log_token_usage_summary = MagicMock()
        mock_agent.memory = MagicMock()

        async def mock_run(prompt):
            yield FinalAnswerStep(step_number=1, final_answer="Done")

        mock_agent.run = mock_run

        fake_commit = ConfigCommit(
            hash="abc123",
            chat_id="test-chat",
            timestamp=datetime.now(),
            message="Updated schema",
            user_request="Update schema",
            environment="https://api.rossum.ai",
            changes=[],
        )

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
            patch.object(AgentService, "_try_create_config_commit", return_value=fake_commit),
            patch.object(
                AgentService,
                "_setup_change_tracking",
                new_callable=AsyncMock,
                return_value=(MagicMock(), MagicMock(), "https://api.rossum.ai"),
            ),
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            events = []
            async for event in service.run_agent(
                chat_id="test-chat",
                prompt="Test",
                conversation_history=[],
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                events.append(event)

        # Hook output is yielded as a FinalAnswerStep before StreamDoneEvent
        hook_events = [e for e in events if isinstance(e, FinalAnswerStep) and e.is_hook_output]
        assert len(hook_events) == 1
        assert "abc123" in hook_events[0].final_answer

    @pytest.mark.asyncio
    async def test_run_agent_skips_hook_when_no_commit(self, tmp_path):
        """Test that hook output is not emitted when no commit is created."""
        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens.total_input = 0
        mock_agent.tokens.total_output = 0
        mock_agent.tokens.total_cache_creation = 0
        mock_agent.tokens.total_cache_read = 0
        mock_agent.tokens.last_main_input = 0
        mock_agent.get_token_usage_breakdown.return_value = {}
        mock_agent.log_token_usage_summary = MagicMock()
        mock_agent.memory = MagicMock()

        async def mock_run(prompt):
            yield FinalAnswerStep(step_number=1, final_answer="Done")

        mock_agent.run = mock_run

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
            patch.object(AgentService, "_try_create_config_commit", return_value=None),
            patch.object(
                AgentService,
                "_setup_change_tracking",
                new_callable=AsyncMock,
                return_value=(MagicMock(), MagicMock(), "https://api.rossum.ai"),
            ),
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            events = []
            async for event in service.run_agent(
                chat_id="test-chat",
                prompt="Test",
                conversation_history=[],
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                events.append(event)

        hook_events = [e for e in events if isinstance(e, FinalAnswerStep) and e.is_hook_output]
        assert len(hook_events) == 0


class TestResolveCautiousPreapprovals:
    """Test AgentService._resolve_cautious_preapprovals."""

    def test_empty_pending_returns_empty(self):
        result = AgentService._resolve_cautious_preapprovals(set(), "Yes, proceed")
        assert result == set()

    def test_approval_returns_pending_copy(self):
        pending = {"update_queue", "delete_workspace"}
        result = AgentService._resolve_cautious_preapprovals(pending, "1. Do you want?\nYes, proceed")
        assert result == pending
        assert result is not pending  # must be a copy

    def test_no_answer_returns_empty(self):
        pending = {"update_queue"}
        result = AgentService._resolve_cautious_preapprovals(pending, "1. Do you want?\nNo, cancel")
        assert result == set()

    def test_chat_answer_returns_empty(self):
        pending = {"update_queue"}
        result = AgentService._resolve_cautious_preapprovals(pending, "1. Do you want?\nLet me provide context")
        assert result == set()

    def test_freeform_answer_returns_empty(self):
        pending = {"update_queue"}
        result = AgentService._resolve_cautious_preapprovals(pending, "I'd rather not do this right now")
        assert result == set()

    def test_unconsumed_preapprovals_carried_forward(self):
        """Unconsumed pre-approvals from previous turns are always included."""
        unconsumed = {"update_queue"}
        result = AgentService._resolve_cautious_preapprovals(set(), "some answer", unconsumed)
        assert result == {"update_queue"}

    def test_unconsumed_merged_with_new_approvals(self):
        """Unconsumed pre-approvals merge with newly approved tools."""
        pending = {"create_hook"}
        unconsumed = {"update_queue"}
        result = AgentService._resolve_cautious_preapprovals(pending, "Yes, proceed", unconsumed)
        assert result == {"update_queue", "create_hook"}

    def test_unconsumed_alone_without_approval_label(self):
        """Unconsumed pre-approvals carry forward even when pending are rejected."""
        pending = {"create_hook"}
        unconsumed = {"update_queue"}
        result = AgentService._resolve_cautious_preapprovals(pending, "No, cancel", unconsumed)
        assert result == {"update_queue"}

    def test_empty_unconsumed_no_effect(self):
        """Empty unconsumed set has no effect."""
        pending = {"update_queue"}
        result = AgentService._resolve_cautious_preapprovals(pending, "Yes, proceed", set())
        assert result == {"update_queue"}

    def test_lifetime_approved_tools_always_included(self):
        """Lifetime-approved tools are included regardless of prompt content."""
        approved = {"patch_schema"}
        result = AgentService._resolve_cautious_preapprovals(set(), "some unrelated message", approved=approved)
        assert result == {"patch_schema"}

    def test_lifetime_approved_merged_with_new_approvals(self):
        """Lifetime approvals merge with newly approved pending tools."""
        pending = {"create_hook"}
        approved = {"patch_schema"}
        result = AgentService._resolve_cautious_preapprovals(pending, "Yes, proceed", approved=approved)
        assert result == {"patch_schema", "create_hook"}

    def test_lifetime_approved_merged_with_unconsumed(self):
        """All three sources merge: lifetime approved + unconsumed + newly approved."""
        pending = {"create_hook"}
        unconsumed = {"update_queue"}
        approved = {"patch_schema"}
        result = AgentService._resolve_cautious_preapprovals(pending, "Yes, proceed", unconsumed, approved)
        assert result == {"patch_schema", "update_queue", "create_hook"}

    def test_lifetime_approved_survives_rejection(self):
        """Lifetime approvals persist even when pending tools are rejected."""
        pending = {"create_hook"}
        approved = {"patch_schema"}
        result = AgentService._resolve_cautious_preapprovals(pending, "No, cancel", approved=approved)
        assert result == {"patch_schema"}


class TestInjectPreapprovalIntoSystemPrompt:
    """Test AgentService._inject_preapproval_into_system_prompt."""

    def test_no_preapprovals_returns_unchanged(self):
        result = AgentService._inject_preapproval_into_system_prompt("You are an agent.", set())
        assert result == "You are an agent."

    def test_appends_preapproval_section(self):
        result = AgentService._inject_preapproval_into_system_prompt("You are an agent.", {"update_queue"})
        assert "update_queue" in result
        assert "already approved" in result
        assert "without asking for confirmation" in result
        assert "ask_user_question" in result
        assert result.startswith("You are an agent.")

    def test_multiple_preapprovals_sorted(self):
        result = AgentService._inject_preapproval_into_system_prompt(
            "You are an agent.", {"create_hook", "update_queue"}
        )
        assert "create_hook, update_queue" in result
