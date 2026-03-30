"""Pydantic search query models for the unified search layer.

Each entity type has specific filter fields. The discriminated union on `entity`
produces a JSON Schema oneOf, so the LLM sees valid filters per entity type.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from rossum_mcp.tools.models import EmailTemplateType, EngineType, LogLevel


class QueueSearch(BaseModel):
    entity: Literal["queue"] = "queue"
    workspace_id: int | None = None
    name: str | None = None
    use_regex: bool = False


class SchemaSearch(BaseModel):
    entity: Literal["schema"] = "schema"
    name: str | None = None
    queue_id: int | None = None
    workspace_id: int | None = None
    use_regex: bool = False


class HookSearch(BaseModel):
    entity: Literal["hook"] = "hook"
    queue_id: int | None = None
    workspace_id: int | None = None
    active: bool | None = None


class EngineSearch(BaseModel):
    entity: Literal["engine"] = "engine"
    engine_type: EngineType | None = None
    agenda_id: str | None = None


class RuleSearch(BaseModel):
    entity: Literal["rule"] = "rule"
    queue_id: int | None = None
    workspace_id: int | None = None
    organization_id: int | None = None
    enabled: bool | None = None


class UserSearch(BaseModel):
    entity: Literal["user"] = "user"
    username: str | None = None
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool | None = None
    is_organization_group_admin: bool | None = None


class WorkspaceSearch(BaseModel):
    entity: Literal["workspace"] = "workspace"
    organization_id: int | None = None
    name: str | None = None
    use_regex: bool = False


class EmailTemplateSearch(BaseModel):
    entity: Literal["email_template"] = "email_template"
    queue_id: int | None = None
    type: EmailTemplateType | None = None
    name: str | None = None
    use_regex: bool = False


class OrganizationGroupSearch(BaseModel):
    entity: Literal["organization_group"] = "organization_group"
    name: str | None = None
    use_regex: bool = False


class AnnotationSearch(BaseModel):
    entity: Literal["annotation"] = "annotation"
    queue_id: int
    status: str | None = "importing,to_review,confirmed,exported"
    ordering: Sequence[str] | None = None


class RelationSearch(BaseModel):
    entity: Literal["relation"] = "relation"
    type: str | None = None
    parent: int | None = None
    key: str | None = None
    annotation: int | None = None


class DocumentRelationSearch(BaseModel):
    entity: Literal["document_relation"] = "document_relation"
    type: str | None = None
    annotation: int | None = None
    key: str | None = None
    documents: int | None = None


class HookLogSearch(BaseModel):
    entity: Literal["hook_log"] = "hook_log"
    hook_id: int | None = None
    queue_id: int | None = None
    annotation_id: int | None = None
    email_id: int | None = None
    log_level: list[LogLevel] | LogLevel | None = None
    status: str | None = None
    status_code: int | None = None
    request_id: str | None = None
    timestamp_before: str | None = None
    timestamp_after: str | None = None
    start_before: str | None = None
    start_after: str | None = None
    end_before: str | None = None
    end_after: str | None = None
    search: str | None = None
    page_size: int | None = None


class HookTemplateSearch(BaseModel):
    entity: Literal["hook_template"] = "hook_template"


class UserRoleSearch(BaseModel):
    entity: Literal["user_role"] = "user_role"


class QueueTemplateNameSearch(BaseModel):
    entity: Literal["queue_template_name"] = "queue_template_name"


SearchQuery = Annotated[
    QueueSearch
    | SchemaSearch
    | HookSearch
    | EngineSearch
    | RuleSearch
    | UserSearch
    | WorkspaceSearch
    | EmailTemplateSearch
    | OrganizationGroupSearch
    | AnnotationSearch
    | RelationSearch
    | DocumentRelationSearch
    | HookLogSearch
    | HookTemplateSearch
    | UserRoleSearch
    | QueueTemplateNameSearch,
    Field(discriminator="entity"),
]


@dataclass
class QueueListItem:
    """Queue summary for list responses (settings omitted to save context)."""

    id: int
    name: str
    url: str
    workspace: str | None = None
    schema: str | None = None
    inbox: str | None = None
    connector: str | None = None
    automation_enabled: bool = False
    automation_level: str = "never"
    status: str | None = None
    counts: dict[str, int] | None = None
    settings: str = "<omitted>"


@dataclass
class SchemaListItem:
    """Schema summary for list responses (content omitted to save context)."""

    id: int
    name: str | None = None
    queues: list[str] | None = None
    workspaces: list[str] | None = None
    url: str | None = None
    content: str = "<omitted>"
    metadata: dict | None = None
    modified_by: str | None = None
    modified_at: str | None = None
