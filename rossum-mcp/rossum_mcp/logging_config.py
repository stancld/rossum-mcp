"""Shared logging configuration for Rossum MCP/Agent with Redis integration."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from logging import LogRecord

import redis


class RedisHandler(logging.Handler):
    """Custom logging handler that sends logs to Redis."""

    def __init__(self, host: str, port: int = 6379, key_prefix: str = "logs", additional_fields: dict | None = None):
        """Initialize Redis handler.

        Args:
            host: Redis host (e.g., "localhost")
            port: Redis port (default: 6379)
            key_prefix: Prefix for Redis keys
            additional_fields: Additional fields to add to every log record
        """
        super().__init__()

        self.client = redis.Redis(host=host, port=port, decode_responses=True)
        self.key_prefix = key_prefix
        self.additional_fields = additional_fields or {}

    def emit(self, record: LogRecord) -> None:
        """Emit a log record to Redis."""
        if record.name.startswith("redis"):
            return

        try:
            log_entry = {
                "@timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
                "thread": record.thread,
                "thread_name": record.threadName,
                **self.additional_fields,
            }

            for key, value in record.__dict__.items():
                if key not in {
                    "name",
                    "msg",
                    "args",
                    "created",
                    "filename",
                    "funcName",
                    "levelname",
                    "levelno",
                    "lineno",
                    "module",
                    "msecs",
                    "message",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "thread",
                    "threadName",
                    "exc_info",
                    "exc_text",
                    "stack_info",
                    "taskName",
                }:
                    log_entry[key] = value

            if record.exc_info:
                log_entry["exception"] = self.format(record)

            key = f"{self.key_prefix}:{datetime.now(UTC).strftime('%Y-%m-%d')}"
            self.client.rpush(key, json.dumps(log_entry))
            self.client.expire(key, 604800)  # 7 days
        except Exception:
            self.handleError(record)


def setup_logging(
    app_name: str = "rossum-app",
    log_level: str = "DEBUG",
    log_file: str | None = None,
    use_console: bool = True,
    redis_host: str | None = None,
    redis_port: int | None = None,
) -> logging.Logger:
    """Configure logging with console, file, and optional Redis handlers.

    Args:
        app_name: Application name
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for file handler
        use_console: Whether to add console handler (default: True)
        redis_host: Redis host (default: from REDIS_HOST env var)
        redis_port: Redis port (default: 6379)

    Returns:
        Configured root logger
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    if use_console:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        root_logger.addHandler(console)

    if log_file:
        file = logging.FileHandler(log_file)
        file.setFormatter(formatter)
        root_logger.addHandler(file)

    redis_host_val = redis_host or os.getenv("REDIS_HOST")
    redis_port_val = redis_port or int(os.getenv("REDIS_PORT", "6379"))

    if redis_host_val:
        try:
            redis_client = redis.Redis(host=redis_host_val, port=redis_port_val, socket_timeout=2)
            redis_client.ping()

            redis_handler = RedisHandler(
                host=redis_host_val,
                port=redis_port_val,
                key_prefix="logs",
                additional_fields={"application": app_name, "environment": os.getenv("ENVIRONMENT", "develop")},
            )
            redis_handler.client = redis_client
            redis_handler.setLevel(logging.INFO)
            root_logger.addHandler(redis_handler)
            root_logger.info(f"Redis logging enabled: {redis_host_val}:{redis_port_val}")
        except Exception as e:
            root_logger.warning(f"Redis logging disabled: {e}")

    return root_logger
