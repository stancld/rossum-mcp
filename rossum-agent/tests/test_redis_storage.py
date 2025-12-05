"""Tests for rossum_agent.redis_storage module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from rossum_agent.redis_storage import RedisStorage


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
    def test_save_chat_success(self, mock_redis):
        """Test successful chat save."""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        messages = [{"role": "user", "content": "Hello"}]

        result = storage.save_chat(None, "chat_123", messages, "/tmp/output")

        assert result is True
        mock_client.setex.assert_called_once()
        call_args = mock_client.setex.call_args[0]
        assert call_args[0] == "chat:chat_123"

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
        mock_client = MagicMock()
        mock_client.get.return_value = (
            b'{"messages": [{"role": "user", "content": "Hello"}], "output_dir": "/tmp/output"}'
        )
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        result = storage.load_chat(None, "chat_123")

        assert result is not None
        messages, output_dir = result
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        assert output_dir == "/tmp/output"
        mock_client.get.assert_called_once_with("chat:chat_123")

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
    def test_close_connection(self, mock_redis):
        """Test closing Redis connection."""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        storage = RedisStorage()
        _ = storage.client
        storage.close()

        mock_client.close.assert_called_once()
        assert storage._client is None
