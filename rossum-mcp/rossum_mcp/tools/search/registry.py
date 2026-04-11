from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_mcp.tools.search.annotations import _list_annotations
from rossum_mcp.tools.search.email_templates import _list_email_templates
from rossum_mcp.tools.search.engines import _list_engines
from rossum_mcp.tools.search.hooks import _list_hook_logs, _list_hook_templates, _list_hooks
from rossum_mcp.tools.search.models import SearchQuery  # noqa: TC001 - needed at runtime for extract_search_kwargs
from rossum_mcp.tools.search.organization_groups import _list_organization_groups
from rossum_mcp.tools.search.queue_templates import _list_queue_template_names
from rossum_mcp.tools.search.queues import _list_queues
from rossum_mcp.tools.search.relations import _list_document_relations, _list_relations
from rossum_mcp.tools.search.rules import _list_rules
from rossum_mcp.tools.search.schemas import _list_schemas
from rossum_mcp.tools.search.users import _list_user_roles, _list_users
from rossum_mcp.tools.search.workspaces import _list_workspaces

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from rossum_api import AsyncRossumAPIClient


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
        "hook_template": lambda **kw: _list_hook_templates(client, max_items=kw.get("max_items")),
        "user_role": lambda **kw: _list_user_roles(client, max_items=kw.get("max_items")),
        "queue_template_name": lambda **kw: _list_queue_template_names(max_items=kw.get("max_items")),
    }


def extract_search_kwargs(query: SearchQuery) -> dict[str, object]:
    """Extract filter kwargs from a search query model, dropping the `entity` discriminator."""
    data = query.model_dump(exclude_none=True)
    data.pop("entity", None)
    return data
