"""Tests for rossum_mcp.logging_config module."""

from __future__ import annotations

import io
import json
import logging

import pytest
import structlog
from rossum_mcp.logging_config import LogFormat, LogLevel, setup_logging


class TestSetupLogging:
    def teardown_method(self):
        root_logger = logging.getLogger()
        handlers_to_remove = [
            h
            for h in root_logger.handlers
            if not isinstance(h, logging.NullHandler) and h.__class__.__name__ != "LogCaptureHandler"
        ]
        for handler in handlers_to_remove:
            root_logger.removeHandler(handler)
        root_logger.setLevel(logging.WARNING)
        structlog.contextvars.clear_contextvars()

    def test_configures_basic_logging(self):
        logger = setup_logging(log_level=LogLevel.INFO)

        assert logger.level == logging.INFO
        handler = self._get_stream_handler(logger)
        assert handler is not None
        assert isinstance(handler.formatter, structlog.stdlib.ProcessorFormatter)

    def test_respects_log_level_parameter(self):
        logger = setup_logging(log_level=LogLevel.WARNING)
        assert logger.level == logging.WARNING

    def test_returns_root_logger(self):
        logger = setup_logging()
        assert logger == logging.getLogger()

    def test_multiple_calls_clear_previous_handlers(self):
        setup_logging()
        count_1 = len(self._get_all_stream_handlers(logging.getLogger()))

        setup_logging()
        count_2 = len(self._get_all_stream_handlers(logging.getLogger()))

        assert count_1 == count_2

    def test_default_parameters(self):
        logger = setup_logging()
        assert logger.level == logging.INFO

    def test_invalid_log_level_raises(self):
        with pytest.raises(KeyError):
            setup_logging(log_level="BOGUS")  # type: ignore[arg-type]

    def test_json_format_produces_json_output(self):
        setup_logging(log_level=LogLevel.INFO, log_format=LogFormat.JSON)
        buf = self._add_capture_handler()
        logging.getLogger("test.json").info("hello json")

        parsed = json.loads(buf.getvalue().strip())
        assert parsed["event"] == "hello json"
        assert parsed["level"] == "info"
        assert "timestamp" in parsed
        assert "logger" in parsed

    def test_json_key_ordering(self):
        setup_logging(log_level=LogLevel.INFO, log_format=LogFormat.JSON)
        buf = self._add_capture_handler()
        structlog.contextvars.bind_contextvars(session_id="sess-1", request_id="req-1")
        logging.getLogger("test.order").info("ordered")

        keys = list(json.loads(buf.getvalue().strip()).keys())
        assert keys.index("timestamp") < keys.index("event")
        assert keys.index("session_id") < keys.index("event")
        assert keys.index("request_id") < keys.index("event")

    def test_console_format_does_not_produce_json(self):
        setup_logging(log_level=LogLevel.INFO, log_format=LogFormat.CONSOLE)
        buf = self._add_capture_handler()
        logging.getLogger("test.console").info("hello console")

        with pytest.raises(json.JSONDecodeError):
            json.loads(buf.getvalue().strip())

    def test_contextvars_appear_in_json_output(self):
        setup_logging(log_level=LogLevel.INFO, log_format=LogFormat.JSON)
        buf = self._add_capture_handler()
        structlog.contextvars.bind_contextvars(session_id="sess-abc", request_id="req-123")
        logging.getLogger("test.ctx").info("with context")

        parsed = json.loads(buf.getvalue().strip())
        assert parsed["session_id"] == "sess-abc"
        assert parsed["request_id"] == "req-123"

    def test_verbose_loggers_suppressed(self):
        setup_logging(log_level=LogLevel.INFO)
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING

    @staticmethod
    def _get_stream_handler(logger: logging.Logger) -> logging.StreamHandler | None:
        for h in logger.handlers:
            if (
                isinstance(h, logging.StreamHandler)
                and not isinstance(h, logging.FileHandler)
                and h.__class__.__name__ != "LogCaptureHandler"
            ):
                return h
        return None

    @staticmethod
    def _get_all_stream_handlers(logger: logging.Logger) -> list[logging.StreamHandler]:
        return [
            h
            for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
            and h.__class__.__name__ != "LogCaptureHandler"
        ]

    @staticmethod
    def _add_capture_handler() -> io.StringIO:
        """Add a StringIO handler that shares the ProcessorFormatter with the root handler."""
        buf = io.StringIO()
        root = logging.getLogger()
        formatter = root.handlers[0].formatter
        handler = logging.StreamHandler(buf)
        handler.setFormatter(formatter)
        root.addHandler(handler)
        return buf
