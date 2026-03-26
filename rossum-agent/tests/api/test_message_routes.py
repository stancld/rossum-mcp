"""Unit tests for message routes - event ordering."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest
from rossum_agent.api.models.schemas import (
    FileCreatedEvent,
    StepEvent,
    StreamDoneEvent,
    SubAgentProgressEvent,
    SubAgentTextEvent,
    TaskSnapshotEvent,
)
from rossum_agent.api.routes.messages import (
    SSE_KEEPALIVE_INTERVAL,
    ProcessedEvent,
    _format_sse_event,
    _generate_chat_summary,
    _process_agent_event,
    _with_sse_keepalive,
    _yield_file_events,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from unittest.mock import MagicMock as MagicMockType


async def mock_run_agent_standard(*args, **kwargs) -> AsyncGenerator[StepEvent | StreamDoneEvent, None]:
    """Standard mock run_agent that yields thinking, final_answer, and done events."""
    yield StepEvent(type="thinking", step_number=1, content="Processing...")
    yield StepEvent(type="final_answer", step_number=1, content="Done!", is_final=True)
    yield StreamDoneEvent(total_steps=1, input_tokens=100, output_tokens=50)


async def simulate_event_generator(
    agent_service: MagicMockType,
    chat_service: MagicMockType,
    credentials: MagicMockType,
) -> AsyncGenerator[str, None]:
    """Simulate the event generator logic from messages.py for testing."""
    final_response: str | None = None
    done_event: StreamDoneEvent | None = None

    async for event in agent_service.run_agent(
        chat_id="test-chat",
        prompt="Hello",
        conversation_history=[],
        rossum_api_token="token",
        rossum_api_base_url="https://api.rossum.ai",
        rossum_url=None,
    ):
        if isinstance(event, StreamDoneEvent):
            done_event = event
        elif isinstance(event, StepEvent):
            if event.type == "final_answer" and event.content:
                final_response = event.content
            yield f"event: step\ndata: {event.model_dump_json()}\n\n"

    output_dir = agent_service.get_output_dir("chat_123")

    updated_history = agent_service.build_updated_history(
        existing_history=[], user_prompt="Hello", final_response=final_response
    )
    chat_service.save_messages(
        user_id=credentials.user_id,
        chat_id="chat_123",
        messages=updated_history,
        output_dir=output_dir,
    )

    if output_dir and output_dir.exists():
        for file_path in output_dir.iterdir():
            if file_path.is_file():
                file_event = FileCreatedEvent(
                    filename=file_path.name, url=f"/api/v1/chats/chat_123/files/{file_path.name}"
                )
                yield f"event: file_created\ndata: {file_event.model_dump_json()}\n\n"

    if done_event:
        yield f"event: done\ndata: {done_event.model_dump_json()}\n\n"


class TestFormatSSEEvent:
    """Tests for _format_sse_event function."""

    def test_format_sse_event(self):
        """Test SSE event formatting."""
        result = _format_sse_event("step", '{"type": "thinking"}')
        assert result == 'event: step\ndata: {"type": "thinking"}\n\n'

    def test_format_sse_event_done(self):
        """Test SSE event formatting for done event."""
        result = _format_sse_event("done", '{"total_steps": 5}')
        assert result == 'event: done\ndata: {"total_steps": 5}\n\n'


class TestYieldFileEvents:
    """Tests for _yield_file_events function."""

    def test_yield_file_events_with_files(self, tmp_path):
        """Test yielding file events when files exist."""
        (tmp_path / "output.png").write_bytes(b"image data")
        (tmp_path / "data.csv").write_text("col1,col2\n1,2")

        events = list(_yield_file_events(tmp_path, "chat_123"))

        assert len(events) == 2
        assert all("event: file_created" in event for event in events)
        assert any("output.png" in event for event in events)
        assert any("data.csv" in event for event in events)

    def test_yield_file_events_with_none_output_dir(self):
        """Test yielding file events when output_dir is None."""
        events = list(_yield_file_events(None, "chat_123"))
        assert events == []

    def test_yield_file_events_with_nonexistent_dir(self, tmp_path):
        """Test yielding file events when directory doesn't exist."""
        nonexistent = tmp_path / "nonexistent"
        events = list(_yield_file_events(nonexistent, "chat_123"))
        assert events == []

    def test_yield_file_events_skips_directories(self, tmp_path):
        """Test that directories are skipped."""
        (tmp_path / "file.txt").write_text("content")
        (tmp_path / "subdir").mkdir()

        events = list(_yield_file_events(tmp_path, "chat_123"))

        assert len(events) == 1
        assert "file.txt" in events[0]


class TestEventGeneratorOrder:
    """Tests for event ordering in message streaming.

    These tests verify the logic that done_event is yielded after file_created events.
    We test the event generation logic directly rather than going through the route handler
    which has rate limiting decorators that complicate testing.
    """

    @pytest.mark.asyncio
    async def test_done_event_yielded_after_file_created_events(self, tmp_path):
        """Test that done_event is yielded after file_created events."""
        test_file = tmp_path / "test_output.png"
        test_file.write_text("test content")

        chat_service = MagicMock()
        chat_service.chat_exists.return_value = True
        chat_service.get_messages.return_value = []
        chat_service.save_messages.return_value = True

        agent_service = MagicMock()
        agent_service.get_output_dir.return_value = tmp_path
        agent_service.build_updated_history.return_value = []
        agent_service.run_agent = mock_run_agent_standard

        credentials = MagicMock()
        credentials.user_id = "test_user"

        events = []
        async for chunk in simulate_event_generator(agent_service, chat_service, credentials):
            events.append(chunk)

        full_content = "".join(events)

        assert "event: file_created" in full_content, "file_created event should be present"
        assert "event: done" in full_content, "done event should be present"

        file_created_pos = full_content.find("event: file_created")
        done_pos = full_content.find("event: done")
        assert file_created_pos < done_pos, "done_event should be yielded after file_created event"

    @pytest.mark.asyncio
    async def test_done_event_without_files(self):
        """Test that done_event is yielded even when no files are created."""
        chat_service = MagicMock()
        chat_service.save_messages.return_value = True

        agent_service = MagicMock()
        agent_service.get_output_dir.return_value = None
        agent_service.build_updated_history.return_value = []
        agent_service.run_agent = mock_run_agent_standard

        credentials = MagicMock()
        credentials.user_id = "test_user"

        events = []
        async for chunk in simulate_event_generator(agent_service, chat_service, credentials):
            events.append(chunk)

        full_content = "".join(events)

        assert "event: file_created" not in full_content
        assert "event: done" in full_content

    @pytest.mark.asyncio
    async def test_multiple_files_all_before_done(self, tmp_path):
        """Test that all file_created events come before done event."""
        (tmp_path / "file1.png").write_text("content1")
        (tmp_path / "file2.csv").write_text("content2")
        (tmp_path / "file3.json").write_text("content3")

        chat_service = MagicMock()
        chat_service.save_messages.return_value = True

        agent_service = MagicMock()
        agent_service.get_output_dir.return_value = tmp_path
        agent_service.build_updated_history.return_value = []

        async def mock_run_agent_minimal(*args, **kwargs):
            yield StepEvent(type="final_answer", step_number=1, content="Done!", is_final=True)
            yield StreamDoneEvent(total_steps=1, input_tokens=100, output_tokens=50)

        agent_service.run_agent = mock_run_agent_minimal

        credentials = MagicMock()
        credentials.user_id = "test_user"

        events = []
        async for chunk in simulate_event_generator(agent_service, chat_service, credentials):
            events.append(chunk)

        full_content = "".join(events)

        done_pos = full_content.find("event: done")
        file_created_count = full_content.count("event: file_created")

        assert file_created_count == 3, "Should have 3 file_created events"

        last_file_created_pos = full_content.rfind("event: file_created")
        assert last_file_created_pos < done_pos, "All file_created events should come before done event"


class TestProcessAgentEvent:
    """Tests for _process_agent_event function."""

    def test_process_stream_done_event(self):
        """Test processing StreamDoneEvent."""
        event = StreamDoneEvent(total_steps=5, input_tokens=100, output_tokens=50)

        result = _process_agent_event(event)

        assert isinstance(result, ProcessedEvent)
        assert result.done_event is event
        assert result.sse_event is None
        assert result.final_response_update is None

    def test_process_sub_agent_progress_event(self):
        """Test processing SubAgentProgressEvent."""
        event = SubAgentProgressEvent(
            tool_name="analyze_hook",
            iteration=2,
            max_iterations=5,
            tool_calls=["grep", "read_file"],
            status="running",
        )

        result = _process_agent_event(event)

        assert result.sse_event is not None
        assert "sub_agent_progress" in result.sse_event
        assert result.done_event is None
        assert result.final_response_update is None

    def test_process_sub_agent_text_event(self):
        """Test processing SubAgentTextEvent."""
        event = SubAgentTextEvent(tool_name="search_knowledge_base", text="Analyzing...", is_final=False)

        result = _process_agent_event(event)

        assert result.sse_event is not None
        assert "sub_agent_text" in result.sse_event
        assert result.done_event is None
        assert result.final_response_update is None

    def test_process_step_event_intermediate_streaming(self):
        """Test processing StepEvent with intermediate type and streaming."""
        event = StepEvent(type="intermediate", step_number=1, content="Hello", is_streaming=True)

        result = _process_agent_event(event)

        assert result.sse_event is not None
        assert "step" in result.sse_event
        assert result.final_response_update is None
        assert result.is_step_complete is False

    def test_process_step_event_final_answer(self):
        """Test processing StepEvent with final_answer type."""
        event = StepEvent(type="final_answer", step_number=2, content="Done!", is_final=True)

        result = _process_agent_event(event)

        assert result.sse_event is not None
        assert "step" in result.sse_event
        assert result.final_response_update == "Done!"
        assert result.is_step_complete is True

    def test_process_step_event_final_answer_streaming(self):
        """Test that a streaming final_answer is not marked as step complete."""
        event = StepEvent(type="final_answer", step_number=2, content="Partial...", is_streaming=True)

        result = _process_agent_event(event)

        assert result.is_step_complete is False

    def test_process_step_event_thinking(self):
        """Test processing StepEvent with thinking type."""
        event = StepEvent(type="thinking", step_number=1, content="Let me think...", is_streaming=True)

        result = _process_agent_event(event)

        assert result.sse_event is not None
        assert "step" in result.sse_event
        assert result.final_response_update is None
        assert result.is_step_complete is False

    def test_process_step_event_tool_start(self):
        """Test processing StepEvent with tool_start type."""
        event = StepEvent(type="tool_start", step_number=1, tool_name="list_annotations", tool_progress=(1, 3))

        result = _process_agent_event(event)

        assert result.sse_event is not None
        assert "step" in result.sse_event
        assert result.final_response_update is None
        assert result.is_step_complete is False

    def test_process_step_event_tool_result(self):
        """Test that a finalized tool_result is marked as step complete."""
        event = StepEvent(type="tool_result", step_number=1, tool_name="list_annotations", result="OK")

        result = _process_agent_event(event)

        assert result.is_step_complete is True

    def test_process_step_event_final_answer_with_none_content(self):
        """Test processing StepEvent with final_answer type but None content."""
        event = StepEvent(type="final_answer", step_number=2, content=None, is_final=True)

        result = _process_agent_event(event)

        assert result.sse_event is not None
        assert result.final_response_update is None

    def test_process_task_snapshot_event(self):
        """Test processing TaskSnapshotEvent."""
        event = TaskSnapshotEvent(tasks=[{"id": "1", "subject": "Deploy", "status": "completed"}])

        result = _process_agent_event(event)

        assert result.sse_event is not None
        assert "task_snapshot" in result.sse_event
        assert result.done_event is None
        assert result.final_response_update is None

    def test_process_step_event_error(self):
        """Test processing StepEvent with error type."""
        event = StepEvent(type="error", step_number=1, content="Something went wrong", is_final=True)

        result = _process_agent_event(event)

        assert result.sse_event is not None
        assert "step" in result.sse_event
        assert result.final_response_update is None
        assert result.is_step_complete is True

    def test_process_stream_done_event_not_step_complete(self):
        """Test that StreamDoneEvent is not marked as step complete."""
        event = StreamDoneEvent(total_steps=5, input_tokens=100, output_tokens=50)

        result = _process_agent_event(event)

        assert result.is_step_complete is False

    def test_process_non_step_event_not_step_complete(self):
        """Test that non-StepEvent types are not marked as step complete."""
        event = SubAgentProgressEvent(
            tool_name="analyze_hook", iteration=1, max_iterations=3, tool_calls=[], status="running"
        )

        result = _process_agent_event(event)

        assert result.is_step_complete is False


class TestWithSSEKeepalive:
    """Tests for _with_sse_keepalive wrapper."""

    @pytest.mark.asyncio
    async def test_forwards_events_without_delay(self):
        """Events yielded immediately are forwarded without keepalive interleaving."""

        async def fast_events():
            yield StepEvent(type="thinking", step_number=1, content="Thinking...")
            yield StepEvent(type="final_answer", step_number=2, content="Done!", is_final=True)

        results = []
        async for event, is_keepalive in _with_sse_keepalive(fast_events()):
            results.append((event, is_keepalive))

        real_events = [event for event, is_keepalive in results if not is_keepalive]
        assert len(real_events) == 2
        assert [e.type for e in real_events] == ["thinking", "final_answer"]

        keepalive_events = [event for event, is_keepalive in results if is_keepalive]
        assert len(keepalive_events) == 0

    @pytest.mark.asyncio
    async def test_emits_keepalive_during_pause(self):
        """A keepalive tick is emitted when no event arrives within the interval."""

        TEST_KEEPALIVE_INTERVAL = 0.05
        TEST_EVENTS_DELAY = 0.15

        async def slow_events():
            yield StepEvent(type="thinking", step_number=1, content="Thinking...")
            await asyncio.sleep(TEST_EVENTS_DELAY)
            yield StepEvent(type="final_answer", step_number=2, content="Done!", is_final=True)

        results = []
        async for event, is_keepalive in _with_sse_keepalive(slow_events(), interval=TEST_KEEPALIVE_INTERVAL):
            results.append((event, is_keepalive))

        real_events = [event for event, is_keepalive in results if not is_keepalive]
        assert len(real_events) == 2
        assert [e.type for e in real_events] == ["thinking", "final_answer"]

        keepalive_events = [event for event, is_keepalive in results if is_keepalive]
        assert len(keepalive_events) >= 1
        assert all(event is None for event in keepalive_events)

    @pytest.mark.asyncio
    async def test_empty_stream(self):
        """An empty async iterator yields nothing."""

        async def no_events():
            return
            yield

        results = []
        async for event, is_keepalive in _with_sse_keepalive(no_events()):
            results.append((event, is_keepalive))

        assert results == []

    @pytest.mark.asyncio
    async def test_keepalive_interval_is_reasonable(self):
        """The keepalive interval should be well below common proxy timeouts (60s)."""
        assert SSE_KEEPALIVE_INTERVAL < 60


class TestGenerateChatSummary:
    """Tests for _generate_chat_summary function."""

    @pytest.mark.asyncio
    async def test_returns_summary_on_success(self):
        """Returns stripped text from the first TextBlock in the response."""
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = "  User asked about deployments.  "
        mock_response.content = [mock_text_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("rossum_agent.api.routes.messages.create_async_bedrock_client", return_value=mock_client):
            result = await _generate_chat_summary("How do I deploy a queue?")

        assert result == "User asked about deployments."

    @pytest.mark.asyncio
    async def test_returns_none_when_no_text_block(self):
        """Returns None when the response contains no TextBlock."""
        mock_response = MagicMock()
        mock_response.content = []

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("rossum_agent.api.routes.messages.create_async_bedrock_client", return_value=mock_client):
            result = await _generate_chat_summary("What is Rossum?")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_api_error(self):
        """Returns None and logs a warning when the Anthropic call raises."""
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API unavailable"))

        with patch("rossum_agent.api.routes.messages.create_async_bedrock_client", return_value=mock_client):
            result = await _generate_chat_summary("Trigger an error")

        assert result is None

    @pytest.mark.asyncio
    async def test_includes_previous_summary_in_prompt(self):
        """When previous_summary is provided, the prompt includes it for context."""
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = "Schema deployment and hook configuration."
        mock_response.content = [mock_text_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("rossum_agent.api.routes.messages.create_async_bedrock_client", return_value=mock_client):
            result = await _generate_chat_summary("Now configure a hook", previous_summary="User deployed a schema")

        assert result == "Schema deployment and hook configuration."
        call_args = mock_client.messages.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        assert "User deployed a schema" in prompt
        assert "Now configure a hook" in prompt

    @pytest.mark.asyncio
    async def test_includes_url_context_in_prompt(self):
        """When url_context is provided, the prompt includes it."""
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = "Queue 123 schema help."
        mock_response.content = [mock_text_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("rossum_agent.api.routes.messages.create_async_bedrock_client", return_value=mock_client):
            result = await _generate_chat_summary(
                "Help me with this queue", url_context="Queue ID: 123, Page type: schema_settings"
            )

        assert result == "Queue 123 schema help."
        call_args = mock_client.messages.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        assert "Queue ID: 123" in prompt

    @pytest.mark.asyncio
    async def test_no_url_context_prefix_when_none(self):
        """When url_context is None, no context prefix is added."""
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = "General help."
        mock_response.content = [mock_text_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("rossum_agent.api.routes.messages.create_async_bedrock_client", return_value=mock_client):
            await _generate_chat_summary("Help me")

        call_args = mock_client.messages.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        assert not prompt.startswith("Context:")
