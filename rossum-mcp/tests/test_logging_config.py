"""Tests for rossum_mcp.logging_config module."""

from __future__ import annotations

import logging
from unittest.mock import patch

from rossum_mcp.logging_config import setup_logging


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

    def test_adds_file_handler_when_log_file_specified(self, tmp_path):
        """Test that file handler is added when log_file is specified."""
        log_file = tmp_path / "test.log"

        logger = setup_logging(app_name="test-app", log_file=str(log_file), use_console=False)

        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 1
        assert log_file.exists()

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

            from rossum_mcp.logging_config import RedisHandler

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
