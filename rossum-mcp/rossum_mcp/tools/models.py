"""Shared domain models used across operation layers (create, update, search)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Literal, TypedDict

from rossum_api.models.hook import Hook as RossumHook
from rossum_api.models.rule import Rule as RossumRule
from rossum_api.models.schema import Schema as RossumSchema

from rossum_mcp.tools.base import RossumResourceWithResolvedWorkspaces


@dataclass
class Schema(RossumResourceWithResolvedWorkspaces[RossumSchema], RossumSchema):
    """Enriched Schema with resolved workspace URLs."""


@dataclass
class Hook(RossumResourceWithResolvedWorkspaces[RossumHook], RossumHook):
    """Enriched Hook with resolved workspace URLs."""


@dataclass
class Rule(RossumResourceWithResolvedWorkspaces[RossumRule], RossumRule):
    """Enriched Rule with resolved workspace URLs."""


class AutomationLevel(StrEnum):
    NEVER = "never"
    ALWAYS = "always"
    CONFIDENT = "confident"


class QueueLocale(StrEnum):
    AUTO = "auto"
    EN_US = "en_US"
    EN_GB = "en_GB"
    DE_DE = "de_DE"
    DE_AT = "de_AT"
    DE_CH = "de_CH"
    FR_FR = "fr_FR"
    FR_BE = "fr_BE"
    FR_CH = "fr_CH"
    CS_CZ = "cs_CZ"
    SK_SK = "sk_SK"
    ES_ES = "es_ES"
    IT_IT = "it_IT"
    PT_PT = "pt_PT"
    PT_BR = "pt_BR"
    NL_NL = "nl_NL"
    NL_BE = "nl_BE"
    PL_PL = "pl_PL"
    HU_HU = "hu_HU"
    RO_RO = "ro_RO"
    JA_JP = "ja_JP"
    ZH_CN = "zh_CN"
    KO_KR = "ko_KR"
    DA_DK = "da_DK"
    FI_FI = "fi_FI"
    SV_SE = "sv_SE"
    NB_NO = "nb_NO"


class EmailRecipient(TypedDict):
    type: Literal["annotator", "constant", "datapoint"]
    value: str


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
    format: str | None = None
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


class QueueTemplateName(StrEnum):
    EU_DEMO = "EU Demo Template"
    APR_EU_DEMO = "AP&R EU Demo Template"
    TAX_INVOICE_EU_DEMO = "Tax Invoice EU Demo Template"
    US_DEMO = "US Demo Template"
    APR_US_DEMO = "AP&R US Demo Template"
    TAX_INVOICE_US_DEMO = "Tax Invoice US Demo Template"
    UK_DEMO = "UK Demo Template"
    APR_UK_DEMO = "AP&R UK Demo Template"
    TAX_INVOICE_UK_DEMO = "Tax Invoice UK Demo Template"
    CZ_DEMO = "CZ Demo Template"
    EMPTY_ORGANIZATION = "Empty Organization Template"
    DELIVERY_NOTES_DEMO = "Delivery Notes Demo Template"
    DELIVERY_NOTE_DEMO = "Delivery Note Demo Template"
    CHINESE_INVOICES_FAPIAO_DEMO = "Chinese Invoices (Fapiao) Demo Template"
    TAX_INVOICE_CN_DEMO = "Tax Invoice CN Demo Template"
    CERTIFICATES_OF_ANALYSIS_DEMO = "Certificates of Analysis Demo Template"
    PURCHASE_ORDER_DEMO = "Purchase Order Demo Template"
    CREDIT_NOTE_DEMO = "Credit Note Demo Template"
    DEBIT_NOTE_DEMO = "Debit Note Demo Template"
    PROFORMA_INVOICE_DEMO = "Proforma Invoice Demo Template"


QUEUE_TEMPLATE_NAMES = tuple(QueueTemplateName)


class EmailTemplateType(StrEnum):
    REJECTION = "rejection"
    REJECTION_DEFAULT = "rejection_default"
    EMAIL_WITH_NO_PROCESSABLE_ATTACHMENTS = "email_with_no_processable_attachments"
    CUSTOM = "custom"


class HookSideload(StrEnum):
    QUEUES = "queues"
    MODIFIERS = "modifiers"
    SCHEMAS = "schemas"
    EMAILS = "emails"
    RELATED_EMAILS = "related_emails"
    RELATIONS = "relations"
    CHILD_RELATION = "child_relation"
    NOTES = "notes"
    SUGGESTED_EDITS = "suggested_edits"
    ASSIGNEES = "assignees"
    PAGES = "pages"
    LABELS = "labels"
    AUTOMATION_BLOCKERS = "automation_blockers"


class EngineType(StrEnum):
    EXTRACTOR = "extractor"
    SPLITTER = "splitter"


class LogLevel(StrEnum):
    INFO = "INFO"
    ERROR = "ERROR"
    WARNING = "WARNING"
