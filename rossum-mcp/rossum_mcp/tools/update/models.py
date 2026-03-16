from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, TypedDict

from rossum_mcp.tools.models import (  # noqa: TC001 - needed at runtime for FastMCP TypedDict resolution
    AutomationLevel,
    QueueLocale,
)

DatapointType = Literal["string", "number", "date", "enum", "button"]


@dataclass
class SchemaNodeUpdate:
    """Partial update for an existing schema node.

    Only include fields you want to update - all fields are optional.
    """

    label: str | None = None
    type: DatapointType | None = None
    score_threshold: float | None = None
    hidden: bool | None = None
    disable_prediction: bool | None = None
    can_export: bool | None = None
    default_value: str | None = None
    rir_field_names: list[str] | None = None
    constraints: dict | None = None
    options: list[dict] | None = None
    ui_configuration: dict | None = None
    formula: str | None = None
    prompt: str | None = None
    context: list[str] | None = None
    matching: dict | None = None
    enum_value_type: str | None = None
    width: int | None = None
    stretch: bool | None = None
    min_occurrences: int | None = None
    max_occurrences: int | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


class QueueUpdateData(TypedDict, total=False):
    name: str
    automation_enabled: bool
    automation_level: AutomationLevel
    locale: QueueLocale
    metadata: dict[str, Any]
    settings: dict[str, Any]
    engine: str
    dedicated_engine: str
    training_enabled: bool
    webhooks: list[str]
    hooks: list[str]
    default_score_threshold: float
    session_timeout: str
    document_lifetime: str | None
    delete_after: str | None
    schema: str
    workspace: str
    connector: str | None
    inbox: str | None


class EngineUpdateData(TypedDict, total=False):
    name: str
    description: str
    learning_enabled: bool
    training_queues: list[str]
