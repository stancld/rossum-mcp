"""Tests for rossum_agent.redis_storage module."""

from __future__ import annotations

import base64
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from rossum_agent.redis_storage import (
    ChatData,
    ChatMetadata,
    RedisStorage,
    extract_text_from_content,
    get_commit_sha,
)


class TestExtractTextFromContent:
    """Test extract_text_from_content function."""

    def test_extract_from_none(self):
        """Test extracting from None returns empty string."""
        assert extract_text_from_content(None) == ""

    def test_extract_from_string(self):
        """Test extracting from string returns the string."""
        assert extract_text_from_content("Hello world") == "Hello world"

    def test_extract_from_list_with_text_blocks(self):
        """Test extracting from list of content blocks."""
        content = [
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "world"},
        ]
        assert extract_text_from_content(content) == "Hello world"

    def test_extract_from_list_with_mixed_blocks(self):
        """Test extracting from list with non-text blocks."""
        content = [
            {"type": "text", "text": "Hello"},
            {"type": "image", "url": "http://example.com/img.png"},
            {"type": "text", "text": "world"},
        ]
        assert extract_text_from_content(content) == "Hello world"

    def test_extract_from_list_with_missing_text(self):
        """Test extracting from list with missing text field."""
        content = [
            {"type": "text"},
            {"type": "text", "text": "world"},
        ]
        assert extract_text_from_content(content) == " world"

    def test_extract_from_empty_list(self):
        """Test extracting from empty list."""
        assert extract_text_from_content([]) == ""

    def test_extract_from_list_with_non_dict_items(self):
        """Test extracting from list with non-dict items."""
        content = [
            "not a dict",
            {"type": "text", "text": "hello"},
        ]
        assert extract_text_from_content(content) == "hello"

    def test_extract_from_unsupported_type(self):
        """Test extracting from unsupported type returns empty string."""
        assert extract_text_from_content(123) == ""


class TestGetCommitSha:
    """Test get_commit_sha function."""

    @patch("rossum_agent.redis_storage.shutil.which", return_value="/usr/bin/git")
    @patch("rossum_agent.redis_storage.subprocess.run")
    def test_get_commit_sha_success(self, mock_run, mock_which):
        """Test successful git commit SHA retrieval."""
        mock_run.return_value = MagicMock(returncode=0, stdout="abc1234\n")
        result = get_commit_sha()
        assert result == "abc1234"
        mock_which.assert_called_once_with("git")
        mock_run.assert_called_once_with(
            ["/usr/bin/git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

    @patch("rossum_agent.redis_storage.subprocess.run")
    def test_get_commit_sha_not_git_repo(self, mock_run):
        """Test returns None when not in git repo."""
        mock_run.return_value = MagicMock(returncode=128, stdout="")
        result = get_commit_sha()
        assert result is None

    @patch("rossum_agent.redis_storage.subprocess.run")
    def test_get_commit_sha_subprocess_error(self, mock_run):
        """Test returns None on subprocess error."""
        mock_run.side_effect = subprocess.SubprocessError("Git not found")
        result = get_commit_sha()
        assert result is None

    @patch("rossum_agent.redis_storage.subprocess.run")
    def test_get_commit_sha_file_not_found(self, mock_run):
        """Test returns None when git not installed."""
        mock_run.side_effect = FileNotFoundError("git command not found")
        result = get_commit_sha()
        assert result is None

    @patch("rossum_agent.redis_storage.subprocess.run")
    def test_get_commit_sha_os_error(self, mock_run):
        """Test returns None on OS error."""
        mock_run.side_effect = OSError("OS error")
        result = get_commit_sha()
        assert result is None


class TestChatMetadata:
    """Test ChatMetadata dataclass."""

    def test_default_values(self):
        """Test default values."""
        metadata = ChatMetadata()
        assert metadata.commit_sha is None
        assert metadata.total_input_tokens == 0
        assert metadata.total_output_tokens == 0
        assert metadata.total_tool_calls == 0
        assert metadata.total_steps == 0

    def test_custom_values(self):
        """Test custom values."""
        metadata = ChatMetadata(
            commit_sha="abc123",
            total_input_tokens=100,
            total_output_tokens=50,
            total_tool_calls=5,
            total_steps=3,
        )
        assert metadata.commit_sha == "abc123"
        assert metadata.total_input_tokens == 100
        assert metadata.total_output_tokens == 50
        assert metadata.total_tool_calls == 5
        assert metadata.total_steps == 3

    def test_to_dict(self):
        """Test to_dict method."""
        metadata = ChatMetadata(
            commit_sha="abc123",
            total_input_tokens=100,
            total_output_tokens=50,
            total_tool_calls=5,
            total_steps=3,
        )
        result = metadata.to_dict()
        assert result == {
            "commit_sha": "abc123",
            "total_input_tokens": 100,
            "total_output_tokens": 50,
            "total_tool_calls": 5,
            "total_steps": 3,
            "mcp_mode": "read-only",
        }

    def test_from_dict(self):
        """Test from_dict class method."""
        data = {
            "commit_sha": "def456",
            "total_input_tokens": 200,
            "total_output_tokens": 100,
            "total_tool_calls": 10,
            "total_steps": 5,
        }
        metadata = ChatMetadata.from_dict(data)
        assert metadata.commit_sha == "def456"
        assert metadata.total_input_tokens == 200
        assert metadata.total_output_tokens == 100
        assert metadata.total_tool_calls == 10
        assert metadata.total_steps == 5

    def test_from_dict_with_missing_keys(self):
        """Test from_dict with partial data."""
        data = {"commit_sha": "abc123"}
        metadata = ChatMetadata.from_dict(data)
        assert metadata.commit_sha == "abc123"
        assert metadata.total_input_tokens == 0
        assert metadata.total_output_tokens == 0
        assert metadata.total_tool_calls == 0
        assert metadata.total_steps == 0

    def test_from_dict_empty(self):
        """Test from_dict with empty dict."""
        metadata = ChatMetadata.from_dict({})
        assert metadata.commit_sha is None
        assert metadata.total_input_tokens == 0


class TestChatData:
    """Test ChatData dataclass."""

    def test_default_values(self):
        """Test default values."""
        data = ChatData()
        assert data.messages == []
        assert data.output_dir is None
        assert isinstance(data.metadata, ChatMetadata)

    def test_custom_values(self):
        """Test custom values."""
        messages = [{"role": "user", "content": "Hello"}]
        metadata = ChatMetadata(commit_sha="abc")
        output_dir = str(Path(tempfile.gettempdir()) / "output")
        data = ChatData(messages=messages, output_dir=output_dir, metadata=metadata)
        assert data.messages == messages
        assert data.output_dir == output_dir
        assert data.metadata.commit_sha == "abc"


class TestRedisStorage:
    """Test RedisStorage class."""

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_init_default_values(self, mock_redis):
        """Test initialization with default values."""
        storage = RedisStorage()

        assert storage.host == "localhost"
        assert storage.port == 6379
        assert storage.ttl.days == 30

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_init_custom_values(self, mock_redis):
        """Test initialization with custom values."""
        storage = RedisStorage(host="custom-host", port=6380, ttl_days=7)

        assert storage.host == "custom-host"
        assert storage.port == 6380
        assert storage.ttl.days == 7

    @patch.dict("os.environ", {"REDIS_HOST": "env-host", "REDIS_PORT": "6381"})
    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_init_from_env_vars(self, mock_redis):
        """Test initialization from environment variables."""
        storage = RedisStorage()

        assert storage.host == "env-host"
        assert storage.port == 6381

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_client_property_creates_connection(self, mock_redis):
        """Test that client property creates Redis connection."""
        storage = RedisStorage()
        client = storage.client

        mock_redis.assert_called_once_with(
            host="localhost",
            port=6379,
            decode_responses=False,
            socket_connect_timeout=5,
        )
        assert client is not None

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_client_property_reuses_connection(self, mock_redis):
        """Test that client property reuses existing connection."""
        storage = RedisStorage()
        client1 = storage.client
        client2 = storage.client

        mock_redis.assert_called_once()
        assert client1 is client2

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_save_chat_success(self, mock_redis):
        """Test successful chat save."""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        messages = [{"role": "user", "content": "Hello"}]

        result = storage.save_chat(None, "chat_123", messages)

        assert result is True
        mock_client.setex.assert_called_once()
        call_args = mock_client.setex.call_args[0]
        assert call_args[0] == "chat:chat_123"

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_save_chat_with_user_id(self, mock_redis):
        """Test chat save with user_id."""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        messages = [{"role": "user", "content": "Hello"}]

        result = storage.save_chat("user123", "chat_123", messages)

        assert result is True
        call_args = mock_client.setex.call_args[0]
        assert call_args[0] == "user:user123:chat:chat_123"

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_save_chat_with_metadata(self, mock_redis):
        """Test chat save with metadata."""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        messages = [{"role": "user", "content": "Hello"}]
        metadata = ChatMetadata(commit_sha="abc123", total_input_tokens=100)

        result = storage.save_chat(None, "chat_123", messages, metadata=metadata)

        assert result is True

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_save_chat_with_output_dir_path(self, mock_redis, tmp_path):
        """Test chat save with Path output_dir."""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        messages = [{"role": "user", "content": "Hello"}]

        result = storage.save_chat(None, "chat_123", messages, output_dir=tmp_path)

        assert result is True

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_save_chat_failure(self, mock_redis):
        """Test chat save failure handling."""
        mock_client = MagicMock()
        mock_client.setex.side_effect = Exception("Connection error")
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        messages = [{"role": "user", "content": "Hello"}]

        result = storage.save_chat(None, "chat_123", messages)

        assert result is False

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_load_chat_success(self, mock_redis):
        """Test successful chat load."""
        output_dir = str(Path(tempfile.gettempdir()) / "output")
        mock_client = MagicMock()
        mock_client.get.return_value = json.dumps(
            {
                "messages": [{"role": "user", "content": "Hello"}],
                "output_dir": output_dir,
                "metadata": {
                    "commit_sha": "abc123",
                    "total_input_tokens": 100,
                    "total_output_tokens": 50,
                    "total_tool_calls": 3,
                    "total_steps": 2,
                },
            }
        ).encode()
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        chat_data = storage.load_chat(None, "chat_123")

        assert chat_data is not None
        assert len(chat_data.messages) == 1
        assert chat_data.messages[0]["role"] == "user"
        assert chat_data.messages[0]["content"] == "Hello"
        assert chat_data.output_dir == output_dir
        assert chat_data.metadata.commit_sha == "abc123"
        assert chat_data.metadata.total_input_tokens == 100
        assert chat_data.metadata.total_output_tokens == 50
        assert chat_data.metadata.total_tool_calls == 3
        assert chat_data.metadata.total_steps == 2
        mock_client.get.assert_called_once_with("chat:chat_123")

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_load_chat_with_user_id(self, mock_redis):
        """Test chat load with user_id."""
        mock_client = MagicMock()
        mock_client.get.return_value = b'{"messages": [], "output_dir": null, "metadata": {}}'
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        storage.load_chat("user123", "chat_123")

        mock_client.get.assert_called_once_with("user:user123:chat:chat_123")

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_load_chat_legacy_format(self, mock_redis):
        """Test loading chat with legacy list format."""
        mock_client = MagicMock()
        mock_client.get.return_value = b'[{"role": "user", "content": "Hello"}]'
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        chat_data = storage.load_chat(None, "chat_123")

        assert chat_data is not None
        assert len(chat_data.messages) == 1
        assert chat_data.output_dir is None
        assert chat_data.metadata.commit_sha is None

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_load_chat_with_output_dir(self, mock_redis, tmp_path):
        """Test loading chat with output_dir triggers file restoration."""
        mock_client = MagicMock()
        mock_client.get.return_value = b'{"messages": [{"role": "user", "content": "Hello"}], "output_dir": "/original/path", "metadata": {"commit_sha": "abc123"}}'
        mock_client.keys.return_value = []
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        chat_data = storage.load_chat(None, "chat_123", output_dir=tmp_path)

        assert chat_data is not None
        assert len(chat_data.messages) == 1
        assert chat_data.output_dir == "/original/path"
        assert chat_data.metadata.commit_sha == "abc123"
        mock_client.keys.assert_called_once_with(b"file:chat_123:*")

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_load_chat_not_found(self, mock_redis):
        """Test loading non-existent chat."""
        mock_client = MagicMock()
        mock_client.get.return_value = None
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        result = storage.load_chat(None, "chat_nonexistent")

        assert result is None

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_load_chat_failure(self, mock_redis):
        """Test chat load failure handling."""
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Connection error")
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        result = storage.load_chat(None, "chat_123")

        assert result is None

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_delete_chat_success(self, mock_redis):
        """Test successful chat deletion."""
        mock_client = MagicMock()
        mock_client.delete.return_value = 1
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        result = storage.delete_chat(None, "chat_123")

        assert result is True
        mock_client.delete.assert_called_once_with("chat:chat_123")

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_delete_chat_with_user_id(self, mock_redis):
        """Test chat deletion with user_id."""
        mock_client = MagicMock()
        mock_client.delete.return_value = 1
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        result = storage.delete_chat("user123", "chat_123")

        assert result is True
        mock_client.delete.assert_called_once_with("user:user123:chat:chat_123")

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_delete_chat_not_found(self, mock_redis):
        """Test deleting non-existent chat."""
        mock_client = MagicMock()
        mock_client.delete.return_value = 0
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        result = storage.delete_chat(None, "chat_nonexistent")

        assert result is False

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_delete_chat_failure(self, mock_redis):
        """Test chat deletion failure handling."""
        mock_client = MagicMock()
        mock_client.delete.side_effect = Exception("Connection error")
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        result = storage.delete_chat(None, "chat_123")

        assert result is False

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_chat_exists_true(self, mock_redis):
        """Test chat exists check returns True."""
        mock_client = MagicMock()
        mock_client.exists.return_value = 1
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        exists = storage.chat_exists(None, "chat_123")

        assert exists is True
        mock_client.exists.assert_called_once_with("chat:chat_123")

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_chat_exists_false(self, mock_redis):
        """Test chat exists check returns False."""
        mock_client = MagicMock()
        mock_client.exists.return_value = 0
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        exists = storage.chat_exists(None, "chat_123")

        assert exists is False

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_chat_exists_failure(self, mock_redis):
        """Test chat exists failure returns False."""
        mock_client = MagicMock()
        mock_client.exists.side_effect = Exception("Connection error")
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        exists = storage.chat_exists(None, "chat_123")

        assert exists is False

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_is_connected_true(self, mock_redis):
        """Test connection check returns True."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        connected = storage.is_connected()

        assert connected is True
        mock_client.ping.assert_called_once()

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_is_connected_false(self, mock_redis):
        """Test connection check returns False on error."""
        mock_client = MagicMock()
        mock_client.ping.side_effect = Exception("Connection error")
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        connected = storage.is_connected()

        assert connected is False

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_get_chat_key_without_user_id(self, mock_redis):
        """Test _get_chat_key without user_id."""
        storage = RedisStorage()
        key = storage._get_chat_key(None, "chat_123")
        assert key == "chat:chat_123"

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_get_chat_key_with_user_id(self, mock_redis):
        """Test _get_chat_key with user_id."""
        storage = RedisStorage()
        key = storage._get_chat_key("user456", "chat_123")
        assert key == "user:user456:chat:chat_123"

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_get_chat_pattern_without_user_id(self, mock_redis):
        """Test _get_chat_pattern without user_id."""
        storage = RedisStorage()
        pattern = storage._get_chat_pattern(None)
        assert pattern == "chat:*"

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_get_chat_pattern_with_user_id(self, mock_redis):
        """Test _get_chat_pattern with user_id."""
        storage = RedisStorage()
        pattern = storage._get_chat_pattern("user456")
        assert pattern == "user:user456:chat:*"

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_list_all_chats_success(self, mock_redis):
        """Test listing all chats."""
        mock_client = MagicMock()
        mock_client.keys.return_value = [b"chat:test_20240115120000"]
        mock_client.get.return_value = (
            b'{"messages": [{"role": "user", "content": "Hello"}], '
            b'"output_dir": null, "metadata": {"commit_sha": "abc123"}}'
        )
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        chats = storage.list_all_chats()

        assert len(chats) == 1
        assert chats[0]["chat_id"] == "test_20240115120000"
        assert chats[0]["message_count"] == 1
        assert chats[0]["commit_sha"] == "abc123"

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_list_all_chats_with_user_id(self, mock_redis):
        """Test listing all chats with user_id."""
        mock_client = MagicMock()
        mock_client.keys.return_value = [b"user:user123:chat:test_20240115120000"]
        mock_client.get.return_value = (
            b'{"messages": [{"role": "user", "content": "Hello user"}], "output_dir": null, "metadata": {}}'
        )
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        chats = storage.list_all_chats(user_id="user123")

        assert len(chats) == 1
        mock_client.keys.assert_called_once_with(b"user:user123:chat:*")

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_list_all_chats_empty(self, mock_redis):
        """Test listing chats when none exist."""
        mock_client = MagicMock()
        mock_client.keys.return_value = []
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        chats = storage.list_all_chats()

        assert chats == []

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_list_all_chats_failure(self, mock_redis):
        """Test list chats failure handling."""
        mock_client = MagicMock()
        mock_client.keys.side_effect = Exception("Connection error")
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        chats = storage.list_all_chats()

        assert chats == []

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_list_all_chats_with_multimodal_content(self, mock_redis):
        """Test listing chats with multimodal content."""
        mock_client = MagicMock()
        mock_client.keys.return_value = [b"chat:test_20240115120000"]
        mock_client.get.return_value = (
            b'{"messages": [{"role": "user", "content": [{"type": "text", "text": "Hello multimodal"}]}], '
            b'"output_dir": null, "metadata": {}}'
        )
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        chats = storage.list_all_chats()

        assert len(chats) == 1
        assert chats[0]["preview"] == "Hello multimodal"

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_list_all_chats_empty_messages(self, mock_redis):
        """Test listing chats with empty messages."""
        mock_client = MagicMock()
        mock_client.keys.return_value = [b"chat:test_20240115120000"]
        mock_client.get.return_value = b'{"messages": [], "output_dir": null, "metadata": {}}'
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        chats = storage.list_all_chats()

        assert len(chats) == 1
        assert chats[0]["message_count"] == 0
        assert chats[0]["preview"] is None

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_close_connection(self, mock_redis):
        """Test closing Redis connection."""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        _ = storage.client
        storage.close()

        mock_client.close.assert_called_once()
        assert storage._client is None

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_close_without_connection(self, mock_redis):
        """Test closing when no connection exists."""
        storage = RedisStorage()
        storage.close()
        mock_redis.return_value.close.assert_not_called()


class TestRedisStorageFileOperations:
    """Test RedisStorage file operations."""

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_save_file_with_content(self, mock_redis):
        """Test saving file with provided content."""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        result = storage.save_file("chat_123", "test.txt", content=b"Hello World")

        assert result is True
        mock_client.setex.assert_called_once()
        call_args = mock_client.setex.call_args[0]
        assert call_args[0] == "file:chat_123:test.txt"

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_save_file_from_path(self, mock_redis, tmp_path):
        """Test saving file from path."""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"File content")

        storage = RedisStorage()
        result = storage.save_file("chat_123", test_file)

        assert result is True

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_save_file_from_string_path(self, mock_redis, tmp_path):
        """Test saving file from string path."""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"File content")

        storage = RedisStorage()
        result = storage.save_file("chat_123", str(test_file))

        assert result is True

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_save_file_not_found(self, mock_redis):
        """Test saving non-existent file."""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        result = storage.save_file("chat_123", Path("/nonexistent/file.txt"))

        assert result is False

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_save_file_failure(self, mock_redis):
        """Test save file failure handling."""
        mock_client = MagicMock()
        mock_client.setex.side_effect = Exception("Redis error")
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        result = storage.save_file("chat_123", "test.txt", content=b"content")

        assert result is False

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_load_file_success(self, mock_redis):
        """Test loading file successfully."""
        mock_client = MagicMock()
        content = b"Hello World"
        metadata = {
            "filename": "test.txt",
            "size": len(content),
            "timestamp": "2024-01-15T12:00:00",
            "content": base64.b64encode(content).decode("utf-8"),
        }
        mock_client.get.return_value = json.dumps(metadata).encode("utf-8")
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        result = storage.load_file("chat_123", "test.txt")

        assert result == b"Hello World"

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_load_file_not_found(self, mock_redis):
        """Test loading non-existent file."""
        mock_client = MagicMock()
        mock_client.get.return_value = None
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        result = storage.load_file("chat_123", "nonexistent.txt")

        assert result is None

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_load_file_failure(self, mock_redis):
        """Test load file failure handling."""
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Redis error")
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        result = storage.load_file("chat_123", "test.txt")

        assert result is None

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_list_files_success(self, mock_redis):
        """Test listing files."""
        mock_client = MagicMock()
        mock_client.keys.return_value = [
            b"file:chat_123:test1.txt",
            b"file:chat_123:test2.txt",
        ]
        mock_client.get.side_effect = [
            b'{"filename": "test1.txt", "size": 100, "timestamp": "2024-01-15T12:00:00"}',
            b'{"filename": "test2.txt", "size": 200, "timestamp": "2024-01-15T12:01:00"}',
        ]
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        files = storage.list_files("chat_123")

        assert len(files) == 2
        assert files[0]["filename"] == "test1.txt"
        assert files[0]["size"] == 100
        assert files[1]["filename"] == "test2.txt"

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_list_files_empty(self, mock_redis):
        """Test listing files when none exist."""
        mock_client = MagicMock()
        mock_client.keys.return_value = []
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        files = storage.list_files("chat_123")

        assert files == []

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_list_files_failure(self, mock_redis):
        """Test list files failure handling."""
        mock_client = MagicMock()
        mock_client.keys.side_effect = Exception("Redis error")
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        files = storage.list_files("chat_123")

        assert files == []

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_delete_file_success(self, mock_redis):
        """Test deleting file successfully."""
        mock_client = MagicMock()
        mock_client.delete.return_value = 1
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        result = storage.delete_file("chat_123", "test.txt")

        assert result is True
        mock_client.delete.assert_called_once_with("file:chat_123:test.txt")

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_delete_file_not_found(self, mock_redis):
        """Test deleting non-existent file."""
        mock_client = MagicMock()
        mock_client.delete.return_value = 0
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        result = storage.delete_file("chat_123", "nonexistent.txt")

        assert result is False

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_delete_file_failure(self, mock_redis):
        """Test delete file failure handling."""
        mock_client = MagicMock()
        mock_client.delete.side_effect = Exception("Redis error")
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        result = storage.delete_file("chat_123", "test.txt")

        assert result is False

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_delete_all_files_success(self, mock_redis):
        """Test deleting all files."""
        mock_client = MagicMock()
        mock_client.keys.return_value = [
            b"file:chat_123:test1.txt",
            b"file:chat_123:test2.txt",
        ]
        mock_client.delete.return_value = 2
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        count = storage.delete_all_files("chat_123")

        assert count == 2

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_delete_all_files_empty(self, mock_redis):
        """Test deleting all files when none exist."""
        mock_client = MagicMock()
        mock_client.keys.return_value = []
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        count = storage.delete_all_files("chat_123")

        assert count == 0

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_delete_all_files_failure(self, mock_redis):
        """Test delete all files failure handling."""
        mock_client = MagicMock()
        mock_client.keys.side_effect = Exception("Redis error")
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        count = storage.delete_all_files("chat_123")

        assert count == 0

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_save_all_files_success(self, mock_redis, tmp_path):
        """Test saving all files from directory."""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        (tmp_path / "file1.txt").write_bytes(b"content1")
        (tmp_path / "file2.txt").write_bytes(b"content2")
        (tmp_path / "subdir").mkdir()

        storage = RedisStorage()
        count = storage.save_all_files("chat_123", tmp_path)

        assert count == 2
        assert mock_client.setex.call_count == 2

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_save_all_files_nonexistent_dir(self, mock_redis):
        """Test saving files from non-existent directory."""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        count = storage.save_all_files("chat_123", Path("/nonexistent/dir"))

        assert count == 0

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_save_all_files_empty_dir(self, mock_redis, tmp_path):
        """Test saving files from empty directory."""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        count = storage.save_all_files("chat_123", tmp_path)

        assert count == 0

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_save_all_files_failure(self, mock_redis, tmp_path):
        """Test save all files with partial failure."""
        mock_client = MagicMock()
        mock_client.setex.side_effect = Exception("Redis error")
        mock_redis.return_value = mock_client

        (tmp_path / "file1.txt").write_bytes(b"content1")

        storage = RedisStorage()
        count = storage.save_all_files("chat_123", tmp_path)

        assert count == 0

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_load_all_files_success(self, mock_redis, tmp_path):
        """Test loading all files to directory."""
        mock_client = MagicMock()
        mock_client.keys.return_value = [b"file:chat_123:test.txt"]
        content = b"Hello World"
        metadata = {
            "filename": "test.txt",
            "size": len(content),
            "timestamp": "2024-01-15T12:00:00",
            "content": base64.b64encode(content).decode("utf-8"),
        }
        mock_client.get.side_effect = [
            b'{"filename": "test.txt", "size": 11, "timestamp": "2024-01-15T12:00:00"}',
            json.dumps(metadata).encode("utf-8"),
        ]
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        count = storage.load_all_files("chat_123", tmp_path)

        assert count == 1
        assert (tmp_path / "test.txt").read_bytes() == b"Hello World"

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_load_all_files_empty(self, mock_redis, tmp_path):
        """Test loading files when none exist."""
        mock_client = MagicMock()
        mock_client.keys.return_value = []
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        count = storage.load_all_files("chat_123", tmp_path)

        assert count == 0

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_load_all_files_failure(self, mock_redis, tmp_path):
        """Test load all files failure handling."""
        mock_client = MagicMock()
        mock_client.keys.side_effect = Exception("Redis error")
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        count = storage.load_all_files("chat_123", tmp_path)

        assert count == 0

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_load_all_files_creates_directory(self, mock_redis, tmp_path):
        """Test that load_all_files creates output directory."""
        mock_client = MagicMock()
        mock_client.keys.return_value = []
        mock_redis.return_value = mock_client

        new_dir = tmp_path / "new_dir" / "nested"
        storage = RedisStorage()
        storage.load_all_files("chat_123", new_dir)

        assert new_dir.exists()

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_load_all_files_with_missing_content(self, mock_redis, tmp_path):
        """Test loading files when file content is missing."""
        mock_client = MagicMock()
        mock_client.keys.return_value = [b"file:chat_123:test.txt"]
        mock_client.get.side_effect = [
            b'{"filename": "test.txt", "size": 11, "timestamp": "2024-01-15T12:00:00"}',
            None,
        ]
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        count = storage.load_all_files("chat_123", tmp_path)

        assert count == 0

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_save_all_files_exception_during_iteration(self, mock_redis, tmp_path):
        """Test save_all_files handles exception during file iteration."""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        (tmp_path / "file1.txt").write_bytes(b"content1")

        storage = RedisStorage()

        with patch.object(storage, "save_file") as mock_save:
            mock_save.side_effect = Exception("Unexpected error during iteration")
            count = storage.save_all_files("chat_123", tmp_path)

        assert count == 0

    @patch("rossum_agent.redis_storage.redis.Redis")
    def test_load_all_files_exception_during_write(self, mock_redis, tmp_path):
        """Test load_all_files handles exception during file write."""
        mock_client = MagicMock()
        mock_client.keys.return_value = [b"file:chat_123:test.txt"]
        content = b"Hello World"
        metadata = {
            "filename": "test.txt",
            "size": len(content),
            "timestamp": "2024-01-15T12:00:00",
            "content": base64.b64encode(content).decode("utf-8"),
        }
        mock_client.get.side_effect = [
            b'{"filename": "test.txt", "size": 11, "timestamp": "2024-01-15T12:00:00"}',
            json.dumps(metadata).encode("utf-8"),
        ]
        mock_redis.return_value = mock_client

        storage = RedisStorage()

        with patch.object(Path, "write_bytes", side_effect=OSError("Permission denied")):
            count = storage.load_all_files("chat_123", tmp_path)

        assert count == 0
