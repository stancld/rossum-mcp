from __future__ import annotations

from enum import StrEnum


class DeleteEntityType(StrEnum):
    QUEUE = "queue"
    SCHEMA = "schema"
    HOOK = "hook"
    RULE = "rule"
    WORKSPACE = "workspace"
    ANNOTATION = "annotation"
