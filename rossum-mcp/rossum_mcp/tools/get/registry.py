"""Entity fetch functions and config registry.

Maps entity names to retrieve callables (EntityConfig). Consumed by handler.py to
wire up the get MCP tool.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from fastmcp.exceptions import ToolError
from rossum_api import APIClientError
from rossum_api.domain_logic.resources import Resource
from rossum_api.models.document_relation import DocumentRelation
from rossum_api.models.engine import Engine
from rossum_api.models.organization_group import OrganizationGroup
from rossum_api.models.organization_limit import OrganizationLimit
from rossum_api.models.queue import Queue
from rossum_api.models.user import User
from rossum_api.models.workspace import Workspace

from rossum_mcp.models.annotation import Annotation
from rossum_mcp.models.email_template import EmailTemplate
from rossum_mcp.models.hook import Hook
from rossum_mcp.models.rule import Rule
from rossum_mcp.models.schema import Schema
from rossum_mcp.tools.base import (
    resolve_queue_workspaces,
    resolve_workspace_from_queue,
    resolve_workspaces_from_queues,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from rossum_api import AsyncRossumAPIClient
    from rossum_api.models.relation import Relation

logger = logging.getLogger(__name__)


@dataclass
class EntityConfig:
    retrieve_fn: Callable[..., Awaitable[object]]


async def _get_annotation(client: AsyncRossumAPIClient, annotation_id: int) -> Annotation:
    logger.debug(f"Retrieving annotation: annotation_id={annotation_id}")
    base_annotation = await client.retrieve_annotation(annotation_id)
    queue_urls = {base_annotation.queue} if base_annotation.queue else set()
    queue_workspace_map = await resolve_queue_workspaces(client, queue_urls)
    workspace = resolve_workspace_from_queue(base_annotation.queue, queue_workspace_map)
    return Annotation.from_base(base_annotation, workspaces=[workspace] if workspace else [])


async def _get_queue(client: AsyncRossumAPIClient, queue_id: int) -> Queue:
    logger.debug(f"Retrieving queue: queue_id={queue_id}")
    return await client.retrieve_queue(queue_id)


async def _get_schema(client: AsyncRossumAPIClient, schema_id: int) -> Schema:
    try:
        base_schema = await client.retrieve_schema(schema_id)
    except APIClientError as e:
        if e.status_code == 404:
            raise ToolError(f"Schema {schema_id} not found") from e
        raise
    queue_workspace_map = await resolve_queue_workspaces(client, set(base_schema.queues))
    return Schema.from_base(
        base_schema, workspaces=resolve_workspaces_from_queues(base_schema.queues, queue_workspace_map)
    )


async def _get_hook(client: AsyncRossumAPIClient, hook_id: int) -> Hook:
    base_hook = await client.retrieve_hook(hook_id)
    queue_workspace_map = await resolve_queue_workspaces(client, set(base_hook.queues))
    return Hook.from_base(base_hook, workspaces=resolve_workspaces_from_queues(base_hook.queues, queue_workspace_map))


async def _get_engine(client: AsyncRossumAPIClient, engine_id: int) -> Engine:
    logger.debug(f"Retrieving engine: engine_id={engine_id}")
    return await client.retrieve_engine(engine_id)


async def _get_rule(client: AsyncRossumAPIClient, rule_id: int) -> Rule:
    logger.debug(f"Retrieving rule: rule_id={rule_id}")
    base_rule = await client.retrieve_rule(rule_id)
    queue_workspace_map = await resolve_queue_workspaces(client, set(base_rule.queues))
    return Rule.from_base(base_rule, workspaces=resolve_workspaces_from_queues(base_rule.queues, queue_workspace_map))


async def _get_user(client: AsyncRossumAPIClient, user_id: int) -> User:
    return await client.retrieve_user(user_id)


async def _get_workspace(client: AsyncRossumAPIClient, workspace_id: int) -> Workspace:
    logger.debug(f"Retrieving workspace: workspace_id={workspace_id}")
    return await client.retrieve_workspace(workspace_id)


async def _get_email_template(client: AsyncRossumAPIClient, email_template_id: int) -> EmailTemplate:
    base_template = await client.retrieve_email_template(email_template_id)
    queue_workspace_map = await resolve_queue_workspaces(client, {base_template.queue})
    workspace = resolve_workspace_from_queue(base_template.queue, queue_workspace_map)
    return EmailTemplate.from_base(base_template, workspaces=[workspace] if workspace else [])


async def _get_organization_group(client: AsyncRossumAPIClient, organization_group_id: int) -> OrganizationGroup:
    logger.debug(f"Retrieving organization group: organization_group_id={organization_group_id}")
    return await client.retrieve_organization_group(organization_group_id)


async def _get_organization_limit(client: AsyncRossumAPIClient, organization_id: int) -> OrganizationLimit:
    logger.debug(f"Retrieving organization limit: organization_id={organization_id}")
    return await client.retrieve_organization_limit(organization_id)


async def _get_relation(client: AsyncRossumAPIClient, relation_id: int) -> Relation:
    logger.debug(f"Retrieving relation: relation_id={relation_id}")
    relation_data = await client._http_client.fetch_one(Resource.Relation, relation_id)
    return cast("Relation", client._deserializer(Resource.Relation, relation_data))


async def _get_document_relation(client: AsyncRossumAPIClient, document_relation_id: int) -> DocumentRelation:
    logger.debug(f"Retrieving document relation: document_relation_id={document_relation_id}")
    return await client.retrieve_document_relation(document_relation_id)


async def _get_hook_secrets_keys(client: AsyncRossumAPIClient, hook_id: int) -> list[str]:
    result = await client._http_client.request_json("GET", f"hooks/{hook_id}/secrets_keys")
    return cast("list[str]", result)


def build_get_registry(client: AsyncRossumAPIClient) -> dict[str, EntityConfig]:
    """Build registry mapping entity names to their retrieve functions."""
    return {
        "queue": EntityConfig(retrieve_fn=lambda id: _get_queue(client, id)),
        "schema": EntityConfig(retrieve_fn=lambda id: _get_schema(client, id)),
        "hook": EntityConfig(retrieve_fn=lambda id: _get_hook(client, id)),
        "engine": EntityConfig(retrieve_fn=lambda id: _get_engine(client, id)),
        "rule": EntityConfig(retrieve_fn=lambda id: _get_rule(client, id)),
        "user": EntityConfig(retrieve_fn=lambda id: _get_user(client, id)),
        "workspace": EntityConfig(retrieve_fn=lambda id: _get_workspace(client, id)),
        "email_template": EntityConfig(retrieve_fn=lambda id: _get_email_template(client, id)),
        "organization_group": EntityConfig(retrieve_fn=lambda id: _get_organization_group(client, id)),
        "organization_limit": EntityConfig(retrieve_fn=lambda id: _get_organization_limit(client, id)),
        "annotation": EntityConfig(retrieve_fn=lambda id: _get_annotation(client, id)),
        "relation": EntityConfig(retrieve_fn=lambda id: _get_relation(client, id)),
        "document_relation": EntityConfig(retrieve_fn=lambda id: _get_document_relation(client, id)),
        "hook_secrets_keys": EntityConfig(retrieve_fn=lambda id: _get_hook_secrets_keys(client, id)),
    }
