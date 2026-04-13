"""Root test configuration for rossum-agent tests."""

from __future__ import annotations

from rossum_mcp.logging_config import LogFormat, LogLevel, setup_logging

# Route structlog and stdlib loggers through the shared setup so tests see the
# same timestamps, level formatting, and contextvars as production.
setup_logging(log_level=LogLevel.INFO, log_format=LogFormat.CONSOLE)
