"""Shared logging configuration for Rossum MCP/Agent with Elasticsearch integration."""

from __future__ import annotations

import logging
import os
import sys
from datetime import UTC, datetime
from logging import LogRecord


class ElasticsearchHandler(logging.Handler):
    """Custom logging handler that sends logs to Elasticsearch."""

    def __init__(self, hosts: list[str], index_name: str = "logstash", additional_fields: dict | None = None):
        """Initialize Elasticsearch handler.

        Args:
            hosts: List of Elasticsearch hosts (e.g., ["http://localhost:9200"])
            index_name: Base name for the index
            additional_fields: Additional fields to add to every log record
        """
        super().__init__()

        from elasticsearch import Elasticsearch  # noqa: PLC0415

        self.client = Elasticsearch(hosts)
        self.index_name = index_name
        self.additional_fields = additional_fields or {}

    def emit(self, record: LogRecord) -> None:
        """Emit a log record to Elasticsearch."""
        # Prevent infinite loop from elasticsearch/elastic_transport logging
        if record.name.startswith(("elasticsearch", "elastic_transport")):
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

            # Add any extra fields from logger.info(..., extra={...})
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

            index = f"{self.index_name}-{datetime.now(UTC).strftime('%Y.%m.%d')}"
            self.client.index(index=index, document=log_entry)
        except Exception:
            self.handleError(record)


def setup_logging(
    app_name: str = "rossum-app",
    log_level: str = "DEBUG",
    log_file: str | None = None,
    use_console: bool = True,
    elasticsearch_host: str | None = None,
    elasticsearch_port: int | None = None,
) -> logging.Logger:
    """Configure logging with console, file, and optional Elasticsearch handlers.

    Args:
        app_name: Application name
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for file handler
        use_console: Whether to add console handler (default: True)
        elasticsearch_host: Elasticsearch host (default: from ELASTICSEARCH_HOST env var)
        elasticsearch_port: Elasticsearch port (default: 9200)

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

    es_host = elasticsearch_host or os.getenv("ELASTICSEARCH_HOST")
    es_port = elasticsearch_port or int(os.getenv("ELASTICSEARCH_PORT", "9200"))

    if es_host:
        try:
            from elasticsearch import Elasticsearch  # noqa: PLC0415

            # Create Elasticsearch client with connection pooling
            es_client = Elasticsearch([f"http://{es_host}:{es_port}"], request_timeout=2)
            # Verify Elasticsearch is reachable
            es_client.info()

            es_handler = ElasticsearchHandler(
                hosts=[f"http://{es_host}:{es_port}"],
                index_name="logs",
                additional_fields={"application": app_name, "environment": os.getenv("ENVIRONMENT", "develop")},
            )
            # Reuse the verified client instead of creating a new one
            es_handler.client = es_client
            es_handler.setLevel(logging.INFO)
            root_logger.addHandler(es_handler)
            root_logger.info(f"Elasticsearch logging enabled: {es_host}:{es_port}")
        except Exception as e:
            root_logger.warning(f"Elasticsearch logging disabled: {e}")

    return root_logger
