"""Tests for AgentService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rossum_agent.agent.memory import AgentMemory, MemoryStep, TaskStep
from rossum_agent.agent.models import AgentStep, ToolCall, ToolResult
from rossum_agent.api.models.schemas import ImageContent, StepEvent
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
        """Test that build_updated_history uses _last_memory when available."""
        service = AgentService()

        memory = AgentMemory()
        memory.add_task("What is 2+2?")
        memory.steps.append(MemoryStep(step_number=1, text="The answer is 4."))
        service._last_memory = memory

        updated = service.build_updated_history(existing_history=[], user_prompt="ignored", final_response="ignored")

        assert len(updated) == 2
        assert updated[0]["type"] == "task_step"
        assert updated[0]["task"] == "What is 2+2?"
        assert updated[1]["type"] == "memory_step"
        assert updated[1]["text"] == "The answer is 4."

    def test_build_history_strips_tool_calls_for_lean_context(self):
        """Test that tool calls and results are stripped from history for lean context."""
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
        service._last_memory = memory

        updated = service.build_updated_history(existing_history=[], user_prompt="ignored", final_response="ignored")

        assert len(updated) == 3
        assert updated[0]["type"] == "task_step"
        assert updated[1]["type"] == "memory_step"
        assert updated[1]["text"] == "Let me check..."
        assert updated[1]["tool_calls"] == []
        assert updated[1]["tool_results"] == []
        assert updated[2]["text"] == "It's rainy in NYC."

    def test_build_history_skips_memory_steps_without_text(self):
        """Test that memory steps without text are skipped."""
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
        service._last_memory = memory

        updated = service.build_updated_history(existing_history=[], user_prompt="ignored", final_response="ignored")

        assert len(updated) == 2
        assert updated[0]["type"] == "task_step"
        assert updated[1]["type"] == "memory_step"
        assert updated[1]["text"] == "Final answer"

    def test_build_history_falls_back_when_no_memory(self):
        """Test fallback to legacy behavior when _last_memory is None."""
        service = AgentService()
        service._last_memory = None

        existing = [{"role": "user", "content": "Previous"}]
        updated = service.build_updated_history(
            existing_history=existing, user_prompt="New question", final_response="Answer"
        )

        assert len(updated) == 3
        assert updated[0] == {"role": "user", "content": "Previous"}
        assert updated[1] == {"role": "user", "content": "New question"}
        assert updated[2] == {"role": "assistant", "content": "Answer"}


class TestAgentServiceRunAgent:
    """Tests for run_agent method."""

    @pytest.mark.asyncio
    async def test_run_agent_yields_events(self, tmp_path):
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
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
            patch("rossum_agent.api.services.agent_service.set_session_output_dir"),
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
            patch("rossum_agent.api.services.agent_service.set_session_output_dir"),
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
    async def test_run_agent_restores_history(self, tmp_path):
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
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
            patch("rossum_agent.api.services.agent_service.set_session_output_dir"),
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

    @pytest.mark.asyncio
    async def test_run_agent_creates_output_dir(self, tmp_path):
        """Test that run_agent creates and sets session output directory."""
        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent._total_input_tokens = 0
        mock_agent._total_output_tokens = 0

        async def mock_run(prompt):
            yield AgentStep(step_number=1, final_answer="Done", is_final=True)

        mock_agent.run = mock_run

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch(
                "rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path
            ) as mock_create_dir,
            patch("rossum_agent.api.services.agent_service.set_session_output_dir") as mock_set_dir,
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            async for _ in service.run_agent(
                prompt="Test",
                conversation_history=[],
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                pass

            mock_create_dir.assert_called_once()
            mock_set_dir.assert_called_once_with(tmp_path)
            assert service.output_dir == tmp_path

    def test_output_dir_initially_none(self):
        """Test that output_dir is None before running agent."""
        service = AgentService()
        assert service.output_dir is None


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
