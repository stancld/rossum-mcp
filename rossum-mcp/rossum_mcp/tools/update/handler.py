from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_api.models.engine import Engine
from rossum_api.models.hook import Hook, HookAction, HookEvent, HookEventAndAction
from rossum_api.models.queue import Queue
from rossum_api.models.rule import Rule, RuleAction
from rossum_api.models.user import User

from rossum_mcp.tools.models import (
    HookSideload,  # noqa: TC001 - needed at runtime for FastMCP parameter serialization
    SchemaNode,  # noqa: TC001 - needed at runtime for FastMCP parameter serialization
)
from rossum_mcp.tools.update.annotations import _bulk_update_annotation_fields, _confirm_annotation, _start_annotation
from rossum_mcp.tools.update.engines import _update_engine
from rossum_mcp.tools.update.hooks import _test_hook, _update_hook
from rossum_mcp.tools.update.models import (  # noqa: TC001 - needed at runtime for FastMCP parameter serialization
    EngineUpdateData,
    QueueUpdateData,
    SchemaNodeUpdate,
)
from rossum_mcp.tools.update.queues import _update_queue
from rossum_mcp.tools.update.rules import _patch_rule
from rossum_mcp.tools.update.schemas.handler import _patch_schema, _prune_schema_fields
from rossum_mcp.tools.update.schemas.patching import (
    PatchOperation,  # noqa: TC001 - needed at runtime for FastMCP parameter serialization
)
from rossum_mcp.tools.update.users import _update_user

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient


def register_update_tools(mcp: FastMCP, client: AsyncRossumAPIClient, base_url: str) -> None:
    # --- Annotations ---
    @mcp.tool(
        description="Set annotation status to 'reviewing' (from 'to_review').",
        tags={"annotations", "write"},
        annotations={"readOnlyHint": False},
    )
    async def start_annotation(annotation_id: int) -> dict:
        return await _start_annotation(client, annotation_id)

    @mcp.tool(
        description="Bulk update extracted fields. Requires annotation in 'reviewing' status. Use datapoint IDs from content, not schema_id.",
        tags={"annotations", "write"},
        annotations={"readOnlyHint": False},
    )
    async def bulk_update_annotation_fields(annotation_id: int, operations: list[dict]) -> dict:
        return await _bulk_update_annotation_fields(client, annotation_id, operations)

    @mcp.tool(
        description="Set annotation status to 'confirmed' (typically after field updates).",
        tags={"annotations", "write"},
        annotations={"readOnlyHint": False},
    )
    async def confirm_annotation(annotation_id: int) -> dict:
        return await _confirm_annotation(client, annotation_id)

    # --- Queues ---
    @mcp.tool(
        description="Update queue settings.",
        tags={"queues", "write"},
        annotations={"readOnlyHint": False},
    )
    async def update_queue(queue_id: int, queue_data: QueueUpdateData) -> Queue | dict:
        return await _update_queue(client, queue_id, queue_data)

    # --- Schemas ---
    @mcp.tool(
        description="Patch schema nodes (add/update/remove). Prereq: load schema-patching skill. Ops: add (parent_id + node_data), update (node_id + node_data), remove (node_id only). Tuple datapoints require explicit id; section-level datapoints use the passed node_id.",
        tags={"schemas", "write"},
        annotations={"readOnlyHint": False},
    )
    async def patch_schema(
        schema_id: int,
        operation: PatchOperation,
        node_id: str,
        node_data: SchemaNode | SchemaNodeUpdate | None = None,
        parent_id: str | None = None,
        position: int | None = None,
    ) -> dict:
        return await _patch_schema(client, schema_id, operation, node_id, node_data, parent_id, position)

    @mcp.tool(
        description="Remove many fields at once. Provide fields_to_keep (keep only these leaf IDs; parent containers preserved automatically; list section IDs to preserve them as empty containers) or fields_to_remove (remove these leaf IDs). Returns {removed_fields, remaining_fields}.",
        tags={"schemas", "write"},
        annotations={"readOnlyHint": False},
    )
    async def prune_schema_fields(
        schema_id: int,
        fields_to_keep: list[str] | None = None,
        fields_to_remove: list[str] | None = None,
    ) -> dict:
        return await _prune_schema_fields(client, schema_id, fields_to_keep, fields_to_remove)

    # --- Engines ---
    @mcp.tool(
        description="Update engine settings.",
        tags={"engines", "write"},
        annotations={"readOnlyHint": False},
    )
    async def update_engine(engine_id: int, engine_data: EngineUpdateData) -> Engine | dict:
        return await _update_engine(client, engine_id, engine_data)

    # --- Hooks ---
    @mcp.tool(
        description="Patch a hook; only provided fields change. secrets is a dict of key-value env vars for serverless functions (write-only, values never returned). token_owner is a User URL for API token generation (cannot be organization_group_admin). run_after is a list of hook URLs that must execute before this hook. sideload controls which related objects are included in hook request payloads.",
        tags={"hooks", "write"},
        annotations={"readOnlyHint": False},
    )
    async def update_hook(
        hook_id: int,
        name: str | None = None,
        queues: list[str] | None = None,
        events: list[HookEventAndAction] | None = None,
        config: dict | None = None,
        settings: dict | None = None,
        active: bool | None = None,
        secrets: dict[str, str] | None = None,
        token_owner: str | None = None,
        run_after: list[str] | None = None,
        sideload: list[HookSideload] | None = None,
    ) -> Hook:
        return await _update_hook(
            client, hook_id, name, queues, events, config, settings, active, secrets, token_owner, run_after, sideload
        )

    @mcp.tool(
        description="Test a hook by auto-generating a realistic payload and executing it. For annotation_content/annotation_status events, annotation and status are auto-resolved from the hook's queues if not provided. If no annotations exist on the hook's queues, ask the user to upload a document first — never upload documents yourself.",
        tags={"hooks", "write"},
        annotations={"readOnlyHint": False},
    )
    async def test_hook(
        hook_id: int,
        event: HookEvent,
        action: HookAction,
        annotation: str | None = None,
        status: str | None = None,
        previous_status: str | None = None,
        config: dict | None = None,
    ) -> dict:
        return await _test_hook(client, hook_id, event, action, annotation, status, previous_status, config)

    # --- Rules ---
    @mcp.tool(
        description="Patch a rule (PATCH); only provided fields change. queue_ids=[] clears queue scoping.",
        tags={"rules", "write"},
        annotations={"readOnlyHint": False},
    )
    async def patch_rule(
        rule_id: int,
        name: str | None = None,
        trigger_condition: str | None = None,
        actions: list[RuleAction] | None = None,
        enabled: bool | None = None,
        queue_ids: list[int] | None = None,
    ) -> Rule | dict:
        return await _patch_rule(client, base_url, rule_id, name, trigger_condition, actions, enabled, queue_ids)

    # --- Users ---
    @mcp.tool(
        description="Patch a user; only provided fields change. Use list_user_roles for role/group URLs.",
        tags={"users", "write"},
        annotations={"readOnlyHint": False},
    )
    async def update_user(
        user_id: int,
        username: str | None = None,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        queues: list[str] | None = None,
        groups: list[str] | None = None,
        is_active: bool | None = None,
        metadata: dict | None = None,
        oidc_id: str | None = None,
        auth_type: str | None = None,
        ui_settings: dict | None = None,
    ) -> User | dict:
        return await _update_user(
            client,
            user_id,
            username,
            email,
            first_name,
            last_name,
            queues,
            groups,
            is_active,
            metadata,
            oidc_id,
            auth_type,
            ui_settings,
        )
