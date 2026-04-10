"""Engine models and enums."""

from __future__ import annotations

from enum import StrEnum


class EngineType(StrEnum):
    EXTRACTOR = "extractor"
    SPLITTER = "splitter"
