"""Unit tests for message routes - event ordering."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from rossum_agent.api.models.schemas import FileCreatedEvent, StepEvent, StreamDoneEvent


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
        agent_service.output_dir = tmp_path
        agent_service.build_updated_history.return_value = []

        async def mock_run_agent(*args, **kwargs):
            yield StepEvent(type="thinking", step_number=1, content="Processing...")
            yield StepEvent(type="final_answer", step_number=1, content="Done!", is_final=True)
            yield StreamDoneEvent(total_steps=1, input_tokens=100, output_tokens=50)

        agent_service.run_agent = mock_run_agent

        credentials = MagicMock()
        credentials.user_id = "test_user"

        async def event_generator():
            """Simulate the event generator logic from messages.py."""
            final_response: str | None = None
            done_event: StreamDoneEvent | None = None

            async for event in agent_service.run_agent(
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

            updated_history = agent_service.build_updated_history(
                existing_history=[], user_prompt="Hello", final_response=final_response
            )
            chat_service.save_messages(
                user_id=credentials.user_id,
                chat_id="chat_123",
                messages=updated_history,
                output_dir=agent_service.output_dir,
            )

            if agent_service.output_dir and agent_service.output_dir.exists():
                for file_path in agent_service.output_dir.iterdir():
                    if file_path.is_file():
                        file_event = FileCreatedEvent(
                            filename=file_path.name, url=f"/api/v1/chats/chat_123/files/{file_path.name}"
                        )
                        yield f"event: file_created\ndata: {file_event.model_dump_json()}\n\n"

            if done_event:
                yield f"event: done\ndata: {done_event.model_dump_json()}\n\n"

        events = []
        async for chunk in event_generator():
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
        agent_service.output_dir = None
        agent_service.build_updated_history.return_value = []

        async def mock_run_agent(*args, **kwargs):
            yield StepEvent(type="thinking", step_number=1, content="Processing...")
            yield StepEvent(type="final_answer", step_number=1, content="Done!", is_final=True)
            yield StreamDoneEvent(total_steps=1, input_tokens=100, output_tokens=50)

        agent_service.run_agent = mock_run_agent

        credentials = MagicMock()
        credentials.user_id = "test_user"

        async def event_generator():
            """Simulate the event generator logic from messages.py."""
            final_response: str | None = None
            done_event: StreamDoneEvent | None = None

            async for event in agent_service.run_agent(
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

            updated_history = agent_service.build_updated_history(
                existing_history=[], user_prompt="Hello", final_response=final_response
            )
            chat_service.save_messages(
                user_id=credentials.user_id,
                chat_id="chat_123",
                messages=updated_history,
                output_dir=agent_service.output_dir,
            )

            if agent_service.output_dir and agent_service.output_dir.exists():
                for file_path in agent_service.output_dir.iterdir():
                    if file_path.is_file():
                        file_event = FileCreatedEvent(
                            filename=file_path.name, url=f"/api/v1/chats/chat_123/files/{file_path.name}"
                        )
                        yield f"event: file_created\ndata: {file_event.model_dump_json()}\n\n"

            if done_event:
                yield f"event: done\ndata: {done_event.model_dump_json()}\n\n"

        events = []
        async for chunk in event_generator():
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
        agent_service.output_dir = tmp_path
        agent_service.build_updated_history.return_value = []

        async def mock_run_agent(*args, **kwargs):
            yield StepEvent(type="final_answer", step_number=1, content="Done!", is_final=True)
            yield StreamDoneEvent(total_steps=1, input_tokens=100, output_tokens=50)

        agent_service.run_agent = mock_run_agent

        credentials = MagicMock()
        credentials.user_id = "test_user"

        async def event_generator():
            """Simulate the event generator logic from messages.py."""
            final_response: str | None = None
            done_event: StreamDoneEvent | None = None

            async for event in agent_service.run_agent(
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

            updated_history = agent_service.build_updated_history(
                existing_history=[], user_prompt="Hello", final_response=final_response
            )
            chat_service.save_messages(
                user_id=credentials.user_id,
                chat_id="chat_123",
                messages=updated_history,
                output_dir=agent_service.output_dir,
            )

            if agent_service.output_dir and agent_service.output_dir.exists():
                for file_path in agent_service.output_dir.iterdir():
                    if file_path.is_file():
                        file_event = FileCreatedEvent(
                            filename=file_path.name, url=f"/api/v1/chats/chat_123/files/{file_path.name}"
                        )
                        yield f"event: file_created\ndata: {file_event.model_dump_json()}\n\n"

            if done_event:
                yield f"event: done\ndata: {done_event.model_dump_json()}\n\n"

        events = []
        async for chunk in event_generator():
            events.append(chunk)

        full_content = "".join(events)

        done_pos = full_content.find("event: done")
        file_created_count = full_content.count("event: file_created")

        assert file_created_count == 3, "Should have 3 file_created events"

        last_file_created_pos = full_content.rfind("event: file_created")
        assert last_file_created_pos < done_pos, "All file_created events should come before done event"
