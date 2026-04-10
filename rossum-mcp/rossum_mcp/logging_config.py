from __future__ import annotations

import logging
import sys
from typing import Literal, get_args

LogLevel = Literal["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL"]

VALID_LOG_LEVELS: tuple[str, ...] = get_args(LogLevel)


def setup_logging(log_level: LogLevel = "INFO") -> logging.Logger:
    root_logger = logging.getLogger()

    level = logging.getLevelNamesMapping()[log_level]
    root_logger.setLevel(level)

    root_logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    root_logger.addHandler(console)

    return root_logger
