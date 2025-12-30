"""Tests for rossum_mcp.logging_config module."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
import redis
from rossum_mcp.logging_config import RedisHandler, setup_logging


class TestRedisHandler:
    """Test RedisHandler class."""

    @pytest.fixture
    def redis_client(self):
        """Create a Redis client for testing."""
        client = redis.Redis(host="localhost", port=6379, decode_responses=True)
        yield client
        client.close()

    @pytest.fixture
    def test_key_prefix(self):
        """Return a unique key prefix for tests."""
        return f"test_logs_{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"

    @pytest.fixture
    def cleanup_keys(self, redis_client, test_key_prefix):
        """Cleanup Redis keys after test."""
        yield
        pattern = f"{test_key_prefix}:*"
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)

    def test_redis_handler_init(self):
        """Test RedisHandler initialization with various parameters."""
        handler = RedisHandler(
            host="localhost", port=6379, key_prefix="custom_prefix", additional_fields={"app": "test"}
        )

        assert handler.key_prefix == "custom_prefix"
        assert handler.additional_fields == {"app": "test"}
        assert handler.client is not None

    def test_redis_handler_init_defaults(self):
        """Test RedisHandler initialization with default parameters."""
        handler = RedisHandler(host="localhost")

        assert handler.key_prefix == "logs"
        assert handler.additional_fields == {}

    def test_redis_handler_emit_basic(self, redis_client, test_key_prefix, cleanup_keys):
        """Test emitting a basic log record to Redis."""
        handler = RedisHandler(host="localhost", port=6379, key_prefix=test_key_prefix)

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test_file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        handler.emit(record)

        key = f"{test_key_prefix}:{datetime.now(UTC).strftime('%Y-%m-%d')}"
        logs = redis_client.lrange(key, 0, -1)
        assert len(logs) == 1

        log_entry = json.loads(logs[0])
        assert log_entry["level"] == "INFO"
        assert log_entry["logger"] == "test.logger"
        assert log_entry["message"] == "Test message"
        assert log_entry["line"] == 42
        assert "@timestamp" in log_entry

    def test_redis_handler_emit_with_additional_fields(self, redis_client, test_key_prefix, cleanup_keys):
        """Test that additional_fields are included in log entries."""
        additional = {"application": "my-app", "environment": "test", "version": "1.0.0"}
        handler = RedisHandler(host="localhost", port=6379, key_prefix=test_key_prefix, additional_fields=additional)

        record = logging.LogRecord(
            name="test.logger",
            level=logging.WARNING,
            pathname="test.py",
            lineno=10,
            msg="Warning message",
            args=(),
            exc_info=None,
        )

        handler.emit(record)

        key = f"{test_key_prefix}:{datetime.now(UTC).strftime('%Y-%m-%d')}"
        logs = redis_client.lrange(key, 0, -1)
        log_entry = json.loads(logs[0])

        assert log_entry["application"] == "my-app"
        assert log_entry["environment"] == "test"
        assert log_entry["version"] == "1.0.0"

    def test_redis_handler_emit_with_custom_attributes(self, redis_client, test_key_prefix, cleanup_keys):
        """Test that custom record attributes are included in log entries."""
        handler = RedisHandler(host="localhost", port=6379, key_prefix=test_key_prefix)

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=5,
            msg="Custom attrs",
            args=(),
            exc_info=None,
        )
        record.user_id = "user123"
        record.request_id = "req-abc-456"
        record.custom_data = {"key": "value"}

        handler.emit(record)

        key = f"{test_key_prefix}:{datetime.now(UTC).strftime('%Y-%m-%d')}"
        logs = redis_client.lrange(key, 0, -1)
        log_entry = json.loads(logs[0])

        assert log_entry["user_id"] == "user123"
        assert log_entry["request_id"] == "req-abc-456"
        assert log_entry["custom_data"] == {"key": "value"}

    def test_redis_handler_emit_with_exception(self, redis_client, test_key_prefix, cleanup_keys):
        """Test that exception info is captured in log entries."""
        handler = RedisHandler(host="localhost", port=6379, key_prefix=test_key_prefix)
        handler.setFormatter(logging.Formatter("%(message)s"))

        try:
            raise ValueError("Test exception message")
        except ValueError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=100,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        handler.emit(record)

        key = f"{test_key_prefix}:{datetime.now(UTC).strftime('%Y-%m-%d')}"
        logs = redis_client.lrange(key, 0, -1)
        log_entry = json.loads(logs[0])

        assert "exception" in log_entry
        assert "ValueError" in log_entry["exception"]
        assert "Test exception message" in log_entry["exception"]

    def test_redis_handler_skips_redis_logger(self, redis_client, test_key_prefix, cleanup_keys):
        """Test that logs from redis.* loggers are skipped to prevent recursion."""
        handler = RedisHandler(host="localhost", port=6379, key_prefix=test_key_prefix)

        redis_record = logging.LogRecord(
            name="redis.connection",
            level=logging.DEBUG,
            pathname="redis.py",
            lineno=1,
            msg="Redis internal",
            args=(),
            exc_info=None,
        )

        handler.emit(redis_record)

        key = f"{test_key_prefix}:{datetime.now(UTC).strftime('%Y-%m-%d')}"
        logs = redis_client.lrange(key, 0, -1)
        assert len(logs) == 0

    def test_redis_handler_skips_redis_sublogger(self, redis_client, test_key_prefix, cleanup_keys):
        """Test that logs from nested redis loggers are also skipped."""
        handler = RedisHandler(host="localhost", port=6379, key_prefix=test_key_prefix)

        for logger_name in ["redis", "redis.client", "redis.connection.pool"]:
            record = logging.LogRecord(
                name=logger_name,
                level=logging.INFO,
                pathname="redis.py",
                lineno=1,
                msg="Should be skipped",
                args=(),
                exc_info=None,
            )
            handler.emit(record)

        key = f"{test_key_prefix}:{datetime.now(UTC).strftime('%Y-%m-%d')}"
        logs = redis_client.lrange(key, 0, -1)
        assert len(logs) == 0

    def test_redis_handler_emit_error_handling(self):
        """Test that handleError is called on Redis errors."""
        handler = RedisHandler(host="localhost", port=6379, key_prefix="test")
        handler.client = MagicMock()
        handler.client.rpush.side_effect = redis.ConnectionError("Connection lost")

        with patch.object(handler, "handleError") as mock_handle_error:
            record = logging.LogRecord(
                name="test.logger",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="Test",
                args=(),
                exc_info=None,
            )
            handler.emit(record)

            mock_handle_error.assert_called_once()
            assert mock_handle_error.call_args[0][0] == record

    def test_redis_handler_sets_key_expiry(self, redis_client, test_key_prefix, cleanup_keys):
        """Test that Redis keys have TTL set (7 days = 604800 seconds)."""
        handler = RedisHandler(host="localhost", port=6379, key_prefix=test_key_prefix)

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="TTL test",
            args=(),
            exc_info=None,
        )

        handler.emit(record)

        key = f"{test_key_prefix}:{datetime.now(UTC).strftime('%Y-%m-%d')}"
        ttl = redis_client.ttl(key)
        assert ttl > 0
        assert ttl <= 604800


class TestSetupLoggingWithRedis:
    """Test setup_logging with real Redis connection."""

    @pytest.fixture
    def redis_client(self):
        """Create a Redis client for testing."""
        client = redis.Redis(host="localhost", port=6379, decode_responses=True)
        yield client
        client.close()

    def teardown_method(self):
        """Clean up handlers after each test."""
        root_logger = logging.getLogger()
        handlers_to_remove = [
            h
            for h in root_logger.handlers
            if not isinstance(h, logging.NullHandler) and h.__class__.__name__ != "LogCaptureHandler"
        ]
        for handler in handlers_to_remove:
            root_logger.removeHandler(handler)
        root_logger.setLevel(logging.WARNING)

    def test_setup_logging_with_redis_success(self, redis_client):
        """Test successful Redis handler setup with real Redis."""
        logger = setup_logging(app_name="test-redis-app", redis_host="localhost", redis_port=6379, use_console=False)

        redis_handlers = [h for h in logger.handlers if isinstance(h, RedisHandler)]
        assert len(redis_handlers) == 1

        handler = redis_handlers[0]
        assert handler.additional_fields["application"] == "test-redis-app"


class TestSetupLogging:
    """Test setup_logging function."""

    def teardown_method(self):
        """Clean up handlers after each test."""
        root_logger = logging.getLogger()
        # Only remove our handlers, not pytest's
        handlers_to_remove = [
            h
            for h in root_logger.handlers
            if not isinstance(h, logging.NullHandler) and h.__class__.__name__ != "LogCaptureHandler"
        ]
        for handler in handlers_to_remove:
            root_logger.removeHandler(handler)
        root_logger.setLevel(logging.WARNING)

    def test_configures_basic_logging(self):
        """Test basic logging configuration."""
        logger = setup_logging(app_name="test-app", log_level="INFO", use_console=True)

        assert logger.level == logging.INFO
        console_handlers = [
            h
            for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
            and h.__class__.__name__ != "LogCaptureHandler"
        ]
        assert len(console_handlers) >= 1

    def test_respects_log_level_parameter(self):
        """Test that log level is set correctly."""
        logger = setup_logging(app_name="test-app", log_level="WARNING")

        assert logger.level == logging.WARNING

    def test_adds_console_handler_when_enabled(self):
        """Test that console handler is added when use_console=True."""
        logger = setup_logging(app_name="test-app", use_console=True)

        console_handlers = [
            h
            for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
            and h.__class__.__name__ != "LogCaptureHandler"
        ]
        assert len(console_handlers) >= 1

    def test_no_console_handler_when_disabled(self):
        """Test that no console handler is added when use_console=False."""
        logger = setup_logging(app_name="test-app", use_console=False)

        console_handlers = [
            h
            for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
            and h.__class__.__name__ != "LogCaptureHandler"
        ]
        assert len(console_handlers) == 0

    def test_no_redis_handler_without_host(self):
        """Test that no Redis handler is added without host config."""
        logger = setup_logging(app_name="test-app", use_console=False)

        non_test_handlers = [h for h in logger.handlers if h.__class__.__name__ != "LogCaptureHandler"]
        assert len(non_test_handlers) == 0

    def test_handles_redis_connection_failure(self):
        """Test graceful handling when Redis is unreachable."""
        with patch("redis.Redis") as mock_redis_class:
            mock_redis_class.side_effect = Exception("Connection refused")

            logger = setup_logging(app_name="test-app", redis_host="localhost", use_console=False)

            redis_handlers = [h for h in logger.handlers if isinstance(h, RedisHandler)]
            assert len(redis_handlers) == 0

    def test_returns_root_logger(self):
        """Test that setup_logging returns the root logger."""
        logger = setup_logging(app_name="test-app")

        assert logger == logging.getLogger()

    def test_multiple_calls_clear_previous_handlers(self):
        """Test that calling setup_logging multiple times doesn't accumulate handlers."""
        # First call
        logger1 = setup_logging(app_name="test-app", use_console=True)
        handler_count_1 = len([h for h in logger1.handlers if h.__class__.__name__ != "LogCaptureHandler"])

        # Second call
        logger2 = setup_logging(app_name="test-app", use_console=True)
        handler_count_2 = len([h for h in logger2.handlers if h.__class__.__name__ != "LogCaptureHandler"])

        # Should have the same number of handlers
        assert handler_count_1 == handler_count_2

    def test_log_level_case_insensitive(self):
        """Test that log level parameter is case insensitive."""
        logger1 = setup_logging(app_name="test-app", log_level="debug")
        assert logger1.level == logging.DEBUG

        logger2 = setup_logging(app_name="test-app", log_level="DEBUG")
        assert logger2.level == logging.DEBUG

        logger3 = setup_logging(app_name="test-app", log_level="Debug")
        assert logger3.level == logging.DEBUG

    def test_default_parameters(self):
        """Test that default parameters work correctly."""
        logger = setup_logging()

        # Should use defaults
        assert logger.level == logging.DEBUG  # Default log_level
        # Should have at least console handler
        console_handlers = [
            h
            for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
            and h.__class__.__name__ != "LogCaptureHandler"
        ]
        assert len(console_handlers) >= 1
