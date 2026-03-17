"""Tests for ChatService."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from rossum_agent.api.services.chat_service import ChatService
from rossum_agent.storage import ChatData, ChatMetadata


class TestChatServiceInit:
    """Tests for ChatService initialization."""

    def test_init_with_provided_storage(self):
        """Test init with provided storage."""
        mock_storage = MagicMock()
        service = ChatService(storage=mock_storage)

        assert service.storage is mock_storage


class TestChatServiceIsConnected:
    """Tests for is_connected method."""

    def test_is_connected_delegates_to_storage(self):
        """Test is_connected delegates to storage."""
        mock_storage = MagicMock()
        mock_storage.is_connected.return_value = True

        service = ChatService(storage=mock_storage)
        result = service.is_connected()

        assert result is True
        mock_storage.is_connected.assert_called_once()


class TestChatServiceCreateChat:
    """Tests for create_chat method."""

    def test_create_chat_returns_response(self):
        """Test create_chat returns valid response."""
        mock_storage = MagicMock()
        mock_storage.save_chat.return_value = True

        service = ChatService(storage=mock_storage)
        response = service.create_chat(user_id="user_123", mcp_mode="read-only")

        assert response.chat_id.startswith("chat_")
        assert response.created_at is not None
        mock_storage.save_chat.assert_called_once()

    def test_create_chat_for_shared_user(self):
        """Test create_chat with None user_id."""
        mock_storage = MagicMock()
        mock_storage.save_chat.return_value = True

        service = ChatService(storage=mock_storage)
        response = service.create_chat(user_id=None)

        assert response.chat_id.startswith("chat_")
        mock_storage.save_chat.assert_called_once()
        call_args = mock_storage.save_chat.call_args[0]
        assert call_args[0] is None

    def test_create_chat_generates_unique_ids(self):
        """Test that create_chat generates unique chat IDs."""
        mock_storage = MagicMock()
        mock_storage.save_chat.return_value = True

        service = ChatService(storage=mock_storage)

        response1 = service.create_chat(user_id="user_123")
        response2 = service.create_chat(user_id="user_123")

        assert response1.chat_id != response2.chat_id

    def test_create_chat_persists_persona(self):
        """Test create_chat stores persona in metadata."""
        mock_storage = MagicMock()
        mock_storage.save_chat.return_value = True

        service = ChatService(storage=mock_storage)
        service.create_chat(user_id="user_123", persona="cautious")

        call_kwargs = mock_storage.save_chat.call_args.kwargs
        metadata = call_kwargs["metadata"]
        assert metadata.persona == "cautious"


class TestChatServiceListChats:
    """Tests for list_chats method."""

    def test_list_chats_empty(self):
        """Test list_chats with empty result."""
        mock_storage = MagicMock()
        mock_storage.list_all_chats.return_value = []

        service = ChatService(storage=mock_storage)
        response = service.list_chats(user_id="user_123")

        assert response.chats == []
        assert response.total == 0
        assert response.limit == 50
        assert response.offset == 0

    def test_list_chats_with_results(self):
        """Test list_chats with chats."""
        mock_storage = MagicMock()
        mock_storage.list_all_chats.return_value = [
            {
                "chat_id": "chat_1",
                "timestamp": 1702132252,
                "message_count": 5,
                "first_message": "Hello",
                "preview": "User request preview",
            },
            {"chat_id": "chat_2", "timestamp": 1702132253, "message_count": 10, "first_message": "World"},
        ]

        service = ChatService(storage=mock_storage)
        response = service.list_chats(user_id="user_123", limit=50, offset=0)

        assert len(response.chats) == 2
        assert response.total == 2
        assert response.chats[0].chat_id == "chat_1"
        assert response.chats[0].preview == "User request preview"
        assert response.chats[1].chat_id == "chat_2"
        assert response.chats[1].preview is None

    def test_list_chats_pagination(self):
        """Test list_chats with pagination."""
        mock_storage = MagicMock()
        mock_storage.list_all_chats.return_value = [
            {"chat_id": f"chat_{i}", "timestamp": 1702132252 + i, "message_count": i, "first_message": f"Message {i}"}
            for i in range(10)
        ]

        service = ChatService(storage=mock_storage)
        response = service.list_chats(user_id="user_123", limit=3, offset=2)

        assert len(response.chats) == 3
        assert response.total == 10
        assert response.limit == 3
        assert response.offset == 2
        assert response.chats[0].chat_id == "chat_2"

    def test_list_chats_with_multimodal_content(self):
        """Test list_chats handles multimodal content blocks in first_message and preview."""
        mock_storage = MagicMock()
        multimodal_content = [
            {"type": "image", "source": {"type": "base64", "data": "abc123"}},
            {"type": "text", "text": "What is this?"},
        ]
        mock_storage.list_all_chats.return_value = [
            {
                "chat_id": "chat_multimodal",
                "timestamp": 1702132252,
                "message_count": 3,
                "first_message": multimodal_content,
                "preview": multimodal_content,
            },
        ]

        service = ChatService(storage=mock_storage)
        response = service.list_chats(user_id="user_123")

        assert len(response.chats) == 1
        assert response.chats[0].first_message == "What is this?"
        assert response.chats[0].preview == "What is this?"


class TestChatServiceGetChat:
    """Tests for get_chat method."""

    def test_get_chat_not_found(self):
        """Test get_chat when chat doesn't exist."""
        mock_storage = MagicMock()
        mock_storage.load_chat.return_value = None

        service = ChatService(storage=mock_storage)
        result = service.get_chat(user_id="user_123", chat_id="chat_nonexistent")

        assert result is None

    def test_get_chat_success(self):
        """Test get_chat with existing chat."""
        output_dir = str(Path(tempfile.gettempdir()) / "output")
        mock_storage = MagicMock()
        mock_storage.load_chat.return_value = ChatData(
            messages=[{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there!"}],
            output_dir=output_dir,
            metadata=ChatMetadata(),
        )
        mock_storage.list_files.return_value = [
            {"filename": "chart.html", "size": 12345, "timestamp": "2024-12-09T14:35:00Z"},
        ]

        service = ChatService(storage=mock_storage)
        result = service.get_chat(user_id="user_123", chat_id="chat_20241209143052_abc123")

        assert result is not None
        assert result.chat_id == "chat_20241209143052_abc123"
        assert len(result.messages) == 2
        assert result.messages[0].role == "user"
        assert len(result.files) == 1

    def test_get_chat_filters_non_user_assistant_messages(self):
        """Test get_chat filters out system messages."""
        mock_storage = MagicMock()
        mock_storage.load_chat.return_value = ChatData(
            messages=[
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
                {"role": "tool", "content": "Tool output"},
            ],
            output_dir=None,
            metadata=ChatMetadata(),
        )
        mock_storage.list_files.return_value = []

        service = ChatService(storage=mock_storage)
        result = service.get_chat(user_id="user_123", chat_id="chat_20241209143052_abc123")

        assert result is not None
        assert len(result.messages) == 2

    def test_get_chat_handles_multimodal_task_step(self):
        """Test get_chat normalizes Anthropic image blocks in task_step messages."""
        mock_storage = MagicMock()
        mock_storage.load_chat.return_value = ChatData(
            messages=[
                {
                    "type": "task_step",
                    "task": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": "iVBOR"},
                        },
                        {"type": "text", "text": "What is this?"},
                    ],
                },
            ],
            output_dir=None,
            metadata=ChatMetadata(),
        )
        mock_storage.list_files.return_value = []

        service = ChatService(storage=mock_storage)
        result = service.get_chat(user_id="user_123", chat_id="chat_20241209143052_abc123")

        assert result is not None
        assert len(result.messages) == 1
        msg = result.messages[0]
        assert msg.role == "user"
        assert isinstance(msg.content, list)
        assert len(msg.content) == 2
        assert msg.content[0].type == "image"
        assert msg.content[0].media_type == "image/png"
        assert msg.content[0].data == "iVBOR"
        assert msg.content[1].type == "text"
        assert msg.content[1].text == "What is this?"

    def test_get_chat_handles_multimodal_user_message(self):
        """Test get_chat normalizes Anthropic image blocks in regular user messages."""
        mock_storage = MagicMock()
        mock_storage.load_chat.return_value = ChatData(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/jpeg", "data": "/9j/4A"},
                        },
                        {"type": "text", "text": "Describe this"},
                    ],
                },
            ],
            output_dir=None,
            metadata=ChatMetadata(),
        )
        mock_storage.list_files.return_value = []

        service = ChatService(storage=mock_storage)
        result = service.get_chat(user_id="user_123", chat_id="chat_20241209143052_abc123")

        assert result is not None
        msg = result.messages[0]
        assert isinstance(msg.content, list)
        assert msg.content[0].type == "image"
        assert msg.content[0].media_type == "image/jpeg"

    def test_get_chat_handles_memory_format(self):
        """Test get_chat handles task_step and memory_step formats from agent memory."""
        mock_storage = MagicMock()
        mock_storage.load_chat.return_value = ChatData(
            messages=[
                {"type": "task_step", "task": "What is 2+2?"},
                {
                    "type": "memory_step",
                    "step_number": 1,
                    "text": "The answer is 4.",
                    "tool_calls": [],
                    "tool_results": [],
                },
                {"type": "task_step", "task": "And 3+3?"},
                {
                    "type": "memory_step",
                    "step_number": 2,
                    "text": "The answer is 6.",
                    "tool_calls": [],
                    "tool_results": [],
                },
                {"type": "memory_step", "step_number": 3, "text": None, "tool_calls": [], "tool_results": []},
            ],
            output_dir=None,
            metadata=ChatMetadata(),
        )
        mock_storage.list_files.return_value = []

        service = ChatService(storage=mock_storage)
        result = service.get_chat(user_id="user_123", chat_id="chat_20241209143052_abc123")

        assert result is not None
        assert len(result.messages) == 4
        assert result.messages[0].role == "user"
        assert result.messages[0].content == "What is 2+2?"
        assert result.messages[1].role == "assistant"
        assert result.messages[1].content == "The answer is 4."
        assert result.messages[2].role == "user"
        assert result.messages[2].content == "And 3+3?"
        assert result.messages[3].role == "assistant"
        assert result.messages[3].content == "The answer is 6."


class TestChatServiceDeleteChat:
    """Tests for delete_chat method."""

    def test_delete_chat_success(self):
        """Test successful chat deletion."""
        mock_storage = MagicMock()
        mock_storage.delete_all_files.return_value = None
        mock_storage.delete_chat.return_value = True

        service = ChatService(storage=mock_storage)
        result = service.delete_chat(user_id="user_123", chat_id="chat_123")

        assert result is True
        mock_storage.delete_all_files.assert_called_once_with("chat_123")
        mock_storage.delete_chat.assert_called_once_with("user_123", "chat_123")

    def test_delete_chat_failure(self):
        """Test failed chat deletion."""
        mock_storage = MagicMock()
        mock_storage.delete_all_files.return_value = None
        mock_storage.delete_chat.return_value = False

        service = ChatService(storage=mock_storage)
        result = service.delete_chat(user_id="user_123", chat_id="chat_nonexistent")

        assert result is False


class TestChatServiceChatExists:
    """Tests for chat_exists method."""

    def test_chat_exists_true(self):
        """Test chat_exists returns True."""
        mock_storage = MagicMock()
        mock_storage.chat_exists.return_value = True

        service = ChatService(storage=mock_storage)
        result = service.chat_exists(user_id="user_123", chat_id="chat_123")

        assert result is True

    def test_chat_exists_false(self):
        """Test chat_exists returns False."""
        mock_storage = MagicMock()
        mock_storage.chat_exists.return_value = False

        service = ChatService(storage=mock_storage)
        result = service.chat_exists(user_id="user_123", chat_id="chat_nonexistent")

        assert result is False


class TestChatServiceGetMessages:
    """Tests for get_messages method."""

    def test_get_messages_not_found(self):
        """Test get_messages when chat doesn't exist."""
        mock_storage = MagicMock()
        mock_storage.load_chat.return_value = None

        service = ChatService(storage=mock_storage)
        result = service.get_messages(user_id="user_123", chat_id="chat_nonexistent")

        assert result is None

    def test_get_messages_success(self):
        """Test get_messages returns raw messages."""
        output_dir = str(Path(tempfile.gettempdir()) / "output")
        mock_storage = MagicMock()
        messages = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}]
        mock_storage.load_chat.return_value = ChatData(
            messages=messages, output_dir=output_dir, metadata=ChatMetadata()
        )

        service = ChatService(storage=mock_storage)
        result = service.get_messages(user_id="user_123", chat_id="chat_123")

        assert result == messages


class TestChatServiceSaveMessages:
    """Tests for save_messages method."""

    def test_save_messages_success(self):
        """Test save_messages success."""
        mock_storage = MagicMock()
        mock_storage.save_chat.return_value = True

        service = ChatService(storage=mock_storage)
        messages = [{"role": "user", "content": "Hello"}]
        result = service.save_messages(user_id="user_123", chat_id="chat_123", messages=messages)

        assert result is True
        mock_storage.save_chat.assert_called_once_with("user_123", "chat_123", messages, None, None)

    def test_save_messages_with_output_dir(self):
        """Test save_messages with output directory."""
        mock_storage = MagicMock()
        mock_storage.save_chat.return_value = True

        service = ChatService(storage=mock_storage)
        messages = [{"role": "user", "content": "Hello"}]
        output_dir = Path(tempfile.gettempdir()) / "output"
        result = service.save_messages(
            user_id="user_123", chat_id="chat_123", messages=messages, output_dir=output_dir
        )

        assert result is True
        mock_storage.save_chat.assert_called_once_with("user_123", "chat_123", messages, output_dir, None)

    def test_save_messages_with_metadata(self):
        """Test save_messages with metadata."""
        mock_storage = MagicMock()
        mock_storage.save_chat.return_value = True

        service = ChatService(storage=mock_storage)
        messages = [{"role": "user", "content": "Hello"}]
        metadata = ChatMetadata(
            commit_sha="abc123",
            total_input_tokens=100,
            total_output_tokens=50,
            total_tool_calls=3,
            total_steps=2,
        )
        result = service.save_messages(user_id="user_123", chat_id="chat_123", messages=messages, metadata=metadata)

        assert result is True
        mock_storage.save_chat.assert_called_once_with("user_123", "chat_123", messages, None, metadata)


class TestChatServiceFeedback:
    """Tests for feedback methods."""

    def test_save_feedback_delegates_to_storage(self):
        mock_storage = MagicMock()
        mock_storage.save_feedback.return_value = True

        service = ChatService(storage=mock_storage)
        result = service.save_feedback(user_id="user_123", chat_id="chat_123", turn_index=2, is_positive=True)

        assert result is True
        mock_storage.save_feedback.assert_called_once_with("user_123", "chat_123", 2, True)

    def test_get_feedback_delegates_to_storage(self):
        mock_storage = MagicMock()
        mock_storage.get_feedback.return_value = {0: True, 2: False}

        service = ChatService(storage=mock_storage)
        result = service.get_feedback(user_id="user_123", chat_id="chat_123")

        assert result == {0: True, 2: False}
        mock_storage.get_feedback.assert_called_once_with("user_123", "chat_123")

    def test_delete_feedback_delegates_to_storage(self):
        mock_storage = MagicMock()
        mock_storage.delete_feedback.return_value = True

        service = ChatService(storage=mock_storage)
        result = service.delete_feedback(user_id="user_123", chat_id="chat_123", turn_index=2)

        assert result is True
        mock_storage.delete_feedback.assert_called_once_with("user_123", "chat_123", 2)
