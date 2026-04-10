"""Tests for rossum_mcp.logging_config module."""

from __future__ import annotations

import logging

import pytest
from rossum_mcp.logging_config import LogLevel, setup_logging


class TestSetupLogging:
    """Test setup_logging function."""

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

    def test_configures_basic_logging(self):
        logger = setup_logging(log_level=LogLevel.INFO)

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
        logger = setup_logging(log_level=LogLevel.WARNING)

        assert logger.level == logging.WARNING

    def test_always_has_console_handler(self):
        logger = setup_logging()

        console_handlers = [
            h
            for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
            and h.__class__.__name__ != "LogCaptureHandler"
        ]
        assert len(console_handlers) >= 1

    def test_returns_root_logger(self):
        logger = setup_logging()

        assert logger == logging.getLogger()

    def test_multiple_calls_clear_previous_handlers(self):
        logger1 = setup_logging()
        handler_count_1 = len([h for h in logger1.handlers if h.__class__.__name__ != "LogCaptureHandler"])

        logger2 = setup_logging()
        handler_count_2 = len([h for h in logger2.handlers if h.__class__.__name__ != "LogCaptureHandler"])

        assert handler_count_1 == handler_count_2

    def test_default_parameters(self):
        logger = setup_logging()

        assert logger.level == logging.INFO
        console_handlers = [
            h
            for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
            and h.__class__.__name__ != "LogCaptureHandler"
        ]
        assert len(console_handlers) >= 1

    def test_invalid_log_level_raises(self):
        with pytest.raises(KeyError):
            setup_logging(log_level="BOGUS")  # type: ignore[arg-type]
