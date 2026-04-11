"""Schema models and node dataclasses for schema patch operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Literal  # noqa: TC003 - needed at runtime for Pydantic schema resolution

from rossum_api.models.schema import Schema as RossumSchema

from rossum_mcp.models.base import RossumResourceWithResolvedWorkspaces


class DatapointType(StrEnum):
    STRING = "string"
    NUMBER = "number"
    DATE = "date"
    ENUM = "enum"
    BUTTON = "button"


@dataclass
class SchemaDatapoint:
    """A datapoint node for schema patch operations.

    Use for adding/updating fields that capture or display values.
    When used inside a tuple (table), id is required.
    """

    label: str
    id: str | None = None
    category: Literal["datapoint"] = "datapoint"
    type: DatapointType | None = None
    description: str | None = None
    rir_field_names: list[str] | None = None
    default_value: str | None = None
    score_threshold: float | None = None
    hidden: bool = False
    disable_prediction: bool = False
    can_export: bool = True
    can_collapse: bool = False
    constraints: dict | None = None
    options: list[dict] | None = None
    ui_configuration: dict | None = None
    formula: str | None = None
    prompt: str | None = None
    context: list[str] | None = None
    matching: dict | None = None
    enum_value_type: str | None = None
    format: str | None = None
    width: int | None = None
    stretch: bool | None = None
    aggregations: dict | None = None

    def to_dict(self) -> dict:
        """Convert to dict, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class SchemaTuple:
    """A tuple node for schema patch operations.

    Use within multivalue to define table row structure with multiple columns.
    """

    id: str
    label: str
    children: list[SchemaDatapoint]
    category: Literal["tuple"] = "tuple"
    hidden: bool = False
    disable_prediction: bool = False
    rir_field_names: list[str] | None = None

    def to_dict(self) -> dict:
        """Convert to dict, excluding None values."""
        result: dict = {"id": self.id, "category": self.category, "label": self.label}
        if self.hidden:
            result["hidden"] = self.hidden
        if self.disable_prediction:
            result["disable_prediction"] = self.disable_prediction
        if self.rir_field_names:
            result["rir_field_names"] = self.rir_field_names
        result["children"] = [child.to_dict() for child in self.children]
        return result


@dataclass
class SchemaMultivalue:
    """A multivalue node for schema patch operations.

    Use for repeating fields or tables. Children is a single Tuple or Datapoint (NOT a list).
    The id is optional here since it gets set from node_id in patch_schema.
    """

    label: str
    children: SchemaTuple | SchemaDatapoint
    id: str | None = None
    category: Literal["multivalue"] = "multivalue"
    rir_field_names: list[str] | None = None
    min_occurrences: int | None = None
    max_occurrences: int | None = None
    hidden: bool = False
    disable_prediction: bool = False
    grid: dict | None = None
    show_grid_by_default: bool = False

    def to_dict(self) -> dict:
        """Convert to dict, excluding None values."""
        result: dict = {"label": self.label, "category": self.category}
        if self.id:
            result["id"] = self.id
        if self.rir_field_names:
            result["rir_field_names"] = self.rir_field_names
        if self.min_occurrences is not None:
            result["min_occurrences"] = self.min_occurrences
        if self.max_occurrences is not None:
            result["max_occurrences"] = self.max_occurrences
        if self.hidden:
            result["hidden"] = self.hidden
        if self.disable_prediction:
            result["disable_prediction"] = self.disable_prediction
        if self.grid is not None:
            result["grid"] = self.grid
        if self.show_grid_by_default:
            result["show_grid_by_default"] = self.show_grid_by_default
        result["children"] = self.children.to_dict()
        return result


SchemaNode = SchemaDatapoint | SchemaMultivalue | SchemaTuple


@dataclass
class Schema(RossumResourceWithResolvedWorkspaces[RossumSchema], RossumSchema):
    """Enriched Schema with resolved workspace URLs."""
