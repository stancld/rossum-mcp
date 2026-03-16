"""Shared domain models used across operation layers (create, update, search)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal, TypedDict, get_args

AutomationLevel = Literal["never", "always", "confident"]

QueueLocale = Literal[
    "auto",
    "en_US",
    "en_GB",
    "de_DE",
    "de_AT",
    "de_CH",
    "fr_FR",
    "fr_BE",
    "fr_CH",
    "cs_CZ",
    "sk_SK",
    "es_ES",
    "it_IT",
    "pt_PT",
    "pt_BR",
    "nl_NL",
    "nl_BE",
    "pl_PL",
    "hu_HU",
    "ro_RO",
    "ja_JP",
    "zh_CN",
    "ko_KR",
    "da_DK",
    "fi_FI",
    "sv_SE",
    "nb_NO",
]


class EmailRecipient(TypedDict):
    type: Literal["annotator", "constant", "datapoint"]
    value: str


DatapointType = Literal["string", "number", "date", "enum", "button"]
NodeCategory = Literal["datapoint", "multivalue", "tuple"]


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
    rir_field_names: list[str] | None = None
    default_value: str | None = None
    score_threshold: float | None = None
    hidden: bool = False
    disable_prediction: bool = False
    can_export: bool = True
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

    def to_dict(self) -> dict:
        """Convert to dict, excluding None values."""
        result: dict = {"id": self.id, "category": self.category, "label": self.label}
        if self.hidden:
            result["hidden"] = self.hidden
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
        result["children"] = self.children.to_dict()
        return result


SchemaNode = SchemaDatapoint | SchemaMultivalue | SchemaTuple


QueueTemplateName = Literal[
    "EU Demo Template",
    "AP&R EU Demo Template",
    "Tax Invoice EU Demo Template",
    "US Demo Template",
    "AP&R US Demo Template",
    "Tax Invoice US Demo Template",
    "UK Demo Template",
    "AP&R UK Demo Template",
    "Tax Invoice UK Demo Template",
    "CZ Demo Template",
    "Empty Organization Template",
    "Delivery Notes Demo Template",
    "Delivery Note Demo Template",
    "Chinese Invoices (Fapiao) Demo Template",
    "Tax Invoice CN Demo Template",
    "Certificates of Analysis Demo Template",
    "Purchase Order Demo Template",
    "Credit Note Demo Template",
    "Debit Note Demo Template",
    "Proforma Invoice Demo Template",
]
QUEUE_TEMPLATE_NAMES = get_args(QueueTemplateName)

EmailTemplateType = Literal["rejection", "rejection_default", "email_with_no_processable_attachments", "custom"]

HookSideload = Literal[
    "queues",
    "modifiers",
    "schemas",
    "emails",
    "related_emails",
    "relations",
    "child_relation",
    "notes",
    "suggested_edits",
    "assignees",
    "pages",
    "labels",
    "automation_blockers",
]

type EngineType = Literal["extractor", "splitter"]
