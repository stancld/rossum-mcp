from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING, Annotated, Literal

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.annotation import Annotation
from rossum_api.models.engine import Engine
from rossum_api.models.group import Group
from rossum_api.models.hook import Hook, HookRunData
from rossum_api.models.hook_template import HookTemplate
from rossum_api.models.organization_group import OrganizationGroup
from rossum_api.models.queue import Queue
from rossum_api.models.rule import Rule
from rossum_api.models.schema import Schema
from rossum_api.models.user import User
from rossum_api.models.workspace import Workspace

from rossum_mcp.tools.base import build_filters, filter_by_name_regex, graceful_list
from rossum_mcp.tools.models import QUEUE_TEMPLATE_NAMES
from rossum_mcp.tools.search.models import QueueListItem, SchemaListItem, SearchQuery

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from rossum_api import AsyncRossumAPIClient
    from rossum_api.models.email_template import EmailTemplate

type Timestamp = Annotated[str, "ISO 8601 timestamp (e.g., '2024-01-15T10:30:00Z')"]
logger = logging.getLogger(__name__)


def _queue_to_list_item(queue: Queue) -> QueueListItem:
    return QueueListItem(
        id=queue.id,
        name=queue.name,
        url=queue.url,
        workspace=queue.workspace,
        schema=queue.schema,
        inbox=queue.inbox,
        connector=queue.connector,
        automation_enabled=queue.automation_enabled,
        automation_level=queue.automation_level,
        status=queue.status,
        counts=queue.counts or None,
    )


async def _list_queues(
    client: AsyncRossumAPIClient,
    id: str | None = None,
    workspace_id: int | None = None,
    name: str | None = None,
    use_regex: bool = False,
) -> list[QueueListItem]:
    logger.debug(f"Listing queues: id={id}, workspace_id={workspace_id}, name={name}")
    filters = build_filters(id=id, workspace=workspace_id, name=None if use_regex else name)
    result = await graceful_list(client, Resource.Queue, "queue", **filters)
    items = [_queue_to_list_item(queue) for queue in result.items]
    return filter_by_name_regex(items, name, use_regex)


def _truncate_schema_for_list(schema: Schema) -> SchemaListItem:
    """Convert to SchemaListItem with content omitted."""
    return SchemaListItem(
        id=schema.id,
        name=schema.name,
        queues=schema.queues,
        url=schema.url,
        metadata=schema.metadata,
        modified_by=schema.modified_by,
        modified_at=schema.modified_at,
    )


async def _list_schemas(
    client: AsyncRossumAPIClient, name: str | None = None, queue_id: int | None = None, use_regex: bool = False
) -> list[SchemaListItem]:
    logger.debug(f"Listing schemas: name={name}, queue_id={queue_id}")
    filters = build_filters(name=None if use_regex else name, queue=queue_id)
    result = await graceful_list(client, Resource.Schema, "schema", **filters)
    items = [_truncate_schema_for_list(schema) for schema in result.items]
    return filter_by_name_regex(items, name, use_regex)


async def _list_hooks(
    client: AsyncRossumAPIClient,
    queue_id: int | None = None,
    active: bool | None = None,
    first_n: int | None = None,
) -> list[Hook]:
    logger.info(f"Listing hooks: queue_id={queue_id}, active={active}, first_n={first_n}")
    filters = build_filters(queue=queue_id, active=active)
    result = await graceful_list(client, Resource.Hook, "hook", max_items=first_n, **filters)
    return result.items


async def _list_hook_logs(
    client: AsyncRossumAPIClient,
    hook_id: int | None = None,
    queue_id: int | None = None,
    annotation_id: int | None = None,
    email_id: int | None = None,
    log_level: list[Literal["INFO", "ERROR", "WARNING"]] | Literal["INFO", "ERROR", "WARNING"] | None = None,
    status: str | None = None,
    status_code: int | None = None,
    request_id: str | None = None,
    timestamp_before: Timestamp | None = None,
    timestamp_after: Timestamp | None = None,
    start_before: Timestamp | None = None,
    start_after: Timestamp | None = None,
    end_before: Timestamp | None = None,
    end_after: Timestamp | None = None,
    search: str | None = None,
    page_size: int | None = None,
) -> list[HookRunData]:
    logger.info(
        f"Listing hook logs: hook_id={hook_id}, queue_id={queue_id}, annotation_id={annotation_id}, email_id={email_id}, log_level={log_level}, status={status}, status_code={status_code}, request_id={request_id}, timestamp_before={timestamp_before}, timestamp_after={timestamp_after}, start_before={start_before}, start_after={start_after}, end_before={end_before}, end_after={end_after}, search={search}, page_size={page_size}"
    )
    filters = build_filters(
        hook=hook_id,
        queue=queue_id,
        annotation=annotation_id,
        email=email_id,
        log_level=",".join(log_level) if isinstance(log_level, list) else log_level,
        status=status,
        status_code=status_code,
        request_id=request_id,
        timestamp_before=timestamp_before,
        timestamp_after=timestamp_after,
        start_before=start_before,
        start_after=start_after,
        end_before=end_before,
        end_after=end_after,
        search=search,
        page_size=page_size,
    )
    result = await graceful_list(client, Resource.HookRunData, "hook_log", **filters)
    return result.items


def _truncate_hook_template_for_list(template: HookTemplate) -> HookTemplate:
    """Keep only fields useful for browsing: id, name, url, type, events, description, use_token_owner."""
    return dataclasses.replace(
        template,
        sideload=[],
        metadata={},
        config={},
        test={},
        settings={},
        settings_schema=None,
        secrets_schema=None,
        guide=None,
        read_more_url=None,
        extension_image_url=None,
        settings_description=[],
        store_description=None,
        external_url=None,
    )


async def _list_hook_templates(client: AsyncRossumAPIClient) -> list[HookTemplate]:
    logger.info("Listing hook templates")
    result = await graceful_list(client, Resource.HookTemplate, "hook_template")
    return [_truncate_hook_template_for_list(t) for t in result.items]


async def _list_engines(
    client: AsyncRossumAPIClient,
    id: int | None = None,
    engine_type: Literal["extractor", "splitter"] | None = None,
    agenda_id: str | None = None,
) -> list[Engine]:
    logger.debug(f"Listing engines: id={id}, type={engine_type}, agenda_id={agenda_id}")
    filters = build_filters(id=id, type=engine_type, agenda_id=agenda_id)
    result = await graceful_list(client, Resource.Engine, "engine", **filters)
    return result.items


async def _list_rules(
    client: AsyncRossumAPIClient,
    schema_id: int | None = None,
    organization_id: int | None = None,
    enabled: bool | None = None,
) -> list[Rule]:
    logger.debug(f"Listing rules: schema_id={schema_id}, organization_id={organization_id}, enabled={enabled}")
    filters = build_filters(schema=schema_id, organization=organization_id, enabled=enabled)
    result = await graceful_list(client, Resource.Rule, "rule", **filters)
    return result.items


async def _list_users(
    client: AsyncRossumAPIClient,
    username: str | None = None,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    is_active: bool | None = None,
    is_organization_group_admin: bool | None = None,
) -> list[User]:
    logger.info(
        f"Listing users: username={username}, email={email}, first_name={first_name}, last_name={last_name}, is_active={is_active}, is_organization_group_admin={is_organization_group_admin}"
    )
    filters = build_filters(
        username=username, email=email, first_name=first_name, last_name=last_name, is_active=is_active
    )
    result = await graceful_list(client, Resource.User, "user", **filters)
    users_list = result.items

    if is_organization_group_admin is not None:
        roles_result = await graceful_list(client, Resource.Group, "user_role")
        org_admin_role_urls: set[str] = {
            group.url for group in roles_result.items if group.name == "organization_group_admin"
        }
        if is_organization_group_admin:
            users_list = [user for user in users_list if set(user.groups) & org_admin_role_urls]
        else:
            users_list = [user for user in users_list if not (set(user.groups) & org_admin_role_urls)]

    return users_list


async def _list_user_roles(client: AsyncRossumAPIClient) -> list[Group]:
    logger.info("Listing user roles")
    result = await graceful_list(client, Resource.Group, "user_role")
    return result.items


async def _list_workspaces(
    client: AsyncRossumAPIClient,
    organization_id: int | None = None,
    name: str | None = None,
    use_regex: bool = False,
) -> list[Workspace]:
    logger.debug(f"Listing workspaces: organization_id={organization_id}, name={name}")
    filters = build_filters(organization=organization_id, name=None if use_regex else name)
    items = (await graceful_list(client, Resource.Workspace, "workspace", **filters)).items
    return filter_by_name_regex(items, name, use_regex)


async def _list_email_templates(
    client: AsyncRossumAPIClient,
    queue_id: int | None = None,
    type: str | None = None,
    name: str | None = None,
    first_n: int | None = None,
    use_regex: bool = False,
) -> list[EmailTemplate]:
    logger.info(f"Listing email templates: queue_id={queue_id}, type={type}, name={name}, first_n={first_n}")
    filters = build_filters(queue=queue_id, type=type, name=None if use_regex else name)
    result = await graceful_list(client, Resource.EmailTemplate, "email_template", max_items=first_n, **filters)
    return filter_by_name_regex(result.items, name, use_regex)


async def _list_organization_groups(
    client: AsyncRossumAPIClient, name: str | None = None, use_regex: bool = False
) -> list[OrganizationGroup]:
    logger.debug(f"Listing organization groups: name={name}")
    filters = build_filters(name=None if use_regex else name)
    items = (await graceful_list(client, Resource.OrganizationGroup, "organization_group", **filters)).items
    return filter_by_name_regex(items, name, use_regex)


async def _list_annotations(
    client: AsyncRossumAPIClient,
    queue_id: int,
    status: str | None = "importing,to_review,confirmed,exported",
    ordering: Sequence[str] = (),
    first_n: int | None = None,
) -> list[Annotation]:
    logger.debug(f"Listing annotations: queue_id={queue_id}, status={status}, ordering={ordering}, first_n={first_n}")
    filters = build_filters(queue=queue_id, page_size=100, status=status, ordering=ordering or None)
    result = await graceful_list(client, Resource.Annotation, "annotation", max_items=first_n, **filters)
    return result.items


async def _list_relations(client: AsyncRossumAPIClient, **kwargs: object) -> list[object]:
    filters = build_filters(**kwargs)
    result = await graceful_list(client, Resource.Relation, "relation", **filters)
    return result.items


async def _list_document_relations(client: AsyncRossumAPIClient, **kwargs: object) -> list[object]:
    filters = build_filters(**kwargs)
    result = await graceful_list(client, Resource.DocumentRelation, "document_relation", **filters)
    return result.items


async def _list_queue_template_names() -> list[str]:
    return list(QUEUE_TEMPLATE_NAMES)


def build_search_registry(client: AsyncRossumAPIClient) -> dict[str, Callable[..., Awaitable[list]] | None]:
    """Build a flat dict of entity -> search function."""
    return {
        "queue": lambda **kw: _list_queues(client, **kw),
        "schema": lambda **kw: _list_schemas(client, **kw),
        "hook": lambda **kw: _list_hooks(client, **kw),
        "engine": lambda **kw: _list_engines(client, **kw),
        "rule": lambda **kw: _list_rules(client, **kw),
        "user": lambda **kw: _list_users(client, **kw),
        "workspace": lambda **kw: _list_workspaces(client, **kw),
        "email_template": lambda **kw: _list_email_templates(client, **kw),
        "organization_group": lambda **kw: _list_organization_groups(client, **kw),
        "annotation": lambda **kw: _list_annotations(client, **kw),
        "relation": lambda **kw: _list_relations(client, **kw),
        "document_relation": lambda **kw: _list_document_relations(client, **kw),
        "hook_log": lambda **kw: _list_hook_logs(client, **kw),
        "hook_template": lambda **_kw: _list_hook_templates(client),
        "user_role": lambda **_kw: _list_user_roles(client),
        "queue_template_name": lambda **_kw: _list_queue_template_names(),
    }


def extract_search_kwargs(query: SearchQuery) -> dict[str, object]:
    """Extract filter kwargs from a search query model, dropping the `entity` discriminator."""
    data = query.model_dump(exclude_none=True)
    data.pop("entity", None)
    return data
