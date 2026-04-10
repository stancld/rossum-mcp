from __future__ import annotations

import logging
import sys
from enum import StrEnum


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def setup_logging(log_level: LogLevel = LogLevel.INFO) -> logging.Logger:
    root_logger = logging.getLogger()

    level = logging.getLevelNamesMapping()[log_level]
    root_logger.setLevel(level)

    root_logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    root_logger.addHandler(console)

    return root_logger
