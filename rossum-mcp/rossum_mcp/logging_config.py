"""Structured logging configuration.

Uses structlog with stdlib integration so that existing ``logging.getLogger(__name__)``
calls throughout the codebase are automatically enriched with correlation context
(session_id, request_id) bound via ``structlog.contextvars``.
"""

from __future__ import annotations

import json
import logging
import sys
from enum import StrEnum

import structlog

# Key ordering for JSON output — correlation fields first for easy log parsing.
STRUCTLOG_KEY_JSON_ORDER = ["timestamp", "session_id", "request_id", "tool_name", "level", "logger", "event"]

# Third-party libraries that produce too many log records at INFO level.
VERBOSE_LOGGERS = ("httpx", "httpcore", "asyncio", "urllib3", "hpack")


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(StrEnum):
    JSON = "json"
    CONSOLE = "console"


def setup_logging(
    log_level: LogLevel = LogLevel.INFO,
    log_format: LogFormat = LogFormat.CONSOLE,
) -> logging.Logger:
    """Configure structlog + stdlib logging.

    All stdlib loggers (including third-party) flow through structlog's
    ``ProcessorFormatter``, picking up any bound contextvars automatically.
    """
    root_logger = logging.getLogger()
    level = logging.getLevelNamesMapping()[log_level]
    root_logger.setLevel(level)

    # Clear existing handlers to avoid duplicates on repeated calls.
    root_logger.handlers.clear()

    formatter = structlog.stdlib.ProcessorFormatter(processors=_get_processors(log_format))
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    for logger_name in VERBOSE_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Configure structlog so that structlog-native loggers also work.
    structlog.configure(
        processors=[
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

    return root_logger


def _get_processors(log_format: LogFormat) -> list:
    common = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.StackInfoRenderer(),
        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
    ]

    if log_format == LogFormat.CONSOLE:
        return [
            *common,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(),
        ]

    return [
        *common,
        structlog.processors.ExceptionRenderer(structlog.tracebacks.ExceptionDictTransformer(show_locals=False)),
        structlog.processors.JSONRenderer(serializer=_json_dump_ordered),
    ]


def _json_dump_ordered(event_dict: dict[str, object], **_kwargs: object) -> str:
    """Serialize structlog entry to JSON with predefined key ordering."""
    ordered: dict[str, object] = {}
    for key in STRUCTLOG_KEY_JSON_ORDER:
        if key in event_dict:
            ordered[key] = event_dict.pop(key)
    for key in sorted(event_dict):
        ordered[key] = event_dict[key]
    return json.dumps(ordered, default=str)
