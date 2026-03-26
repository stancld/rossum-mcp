from __future__ import annotations

from collections.abc import Sequence  # noqa: TC003 - needed at runtime for FastMCP
from typing import TYPE_CHECKING

from rossum_api.models.email_template import EmailTemplate
from rossum_api.models.engine import Engine, EngineField, EngineFieldType
from rossum_api.models.hook import Hook, HookEventAndAction, HookType
from rossum_api.models.queue import Queue
from rossum_api.models.rule import Rule, RuleAction
from rossum_api.models.user import User
from rossum_api.models.workspace import Workspace

from rossum_mcp.tools.create.annotations import _copy_annotations, _upload_document
from rossum_mcp.tools.create.email_templates import _create_email_template
from rossum_mcp.tools.create.engines import _create_engine, _create_engine_field
from rossum_mcp.tools.create.hooks import _create_hook, _create_hook_from_template
from rossum_mcp.tools.create.queues import _create_queue_from_template
from rossum_mcp.tools.create.rules import _create_rule
from rossum_mcp.tools.create.users import _create_user
from rossum_mcp.tools.create.workspaces import _create_workspace
from rossum_mcp.tools.models import (
    EmailRecipient,
    EmailTemplateType,
    EngineType,
    HookSideload,
    QueueTemplateName,
)

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient


def register_create_tools(mcp: FastMCP, client: AsyncRossumAPIClient, base_url: str) -> None:
    # --- Annotations ---
    @mcp.tool(
        description="Upload a document from a local file path (absolute path recommended). Use search(entity='annotation', queue_id=...) to find the created annotation.",
        tags={"annotations", "write"},
        annotations={"readOnlyHint": False},
    )
    async def upload_document(file_path: str, queue_id: int) -> dict:
        return await _upload_document(client, file_path, queue_id)

    @mcp.tool(
        description="Copy annotations to another queue. reimport=True re-extracts data in the target queue (use when moving/uploading documents between queues). reimport=False preserves original extracted data as-is.",
        tags={"annotations", "write"},
        annotations={"readOnlyHint": False},
    )
    async def copy_annotations(
        annotation_ids: Sequence[int],
        target_queue_id: int,
        target_status: str | None = None,
        reimport: bool = False,
    ) -> dict:
        return await _copy_annotations(client, base_url, annotation_ids, target_queue_id, target_status, reimport)

    # --- Queues ---
    @mcp.tool(
        description="Create a queue from a template (includes schema + engine defaults).",
        tags={"queues", "write"},
        annotations={"readOnlyHint": False},
    )
    async def create_queue_from_template(
        name: str,
        template_name: QueueTemplateName,
        workspace_id: int,
        include_documents: bool = False,
        engine_id: int | None = None,
    ) -> Queue | dict:
        return await _create_queue_from_template(
            client, base_url, name, template_name, workspace_id, include_documents, engine_id
        )

    # --- Engines ---
    @mcp.tool(
        description="Create an engine; create matching engine fields for the target schema immediately after.",
        tags={"engines", "write"},
        annotations={"readOnlyHint": False},
    )
    async def create_engine(name: str, organization_id: int, engine_type: EngineType) -> Engine | dict:
        return await _create_engine(client, base_url, name, organization_id, engine_type)

    @mcp.tool(
        description="Create an engine field corresponding to a schema field (used during engine+schema setup).",
        tags={"engines", "write"},
        annotations={"readOnlyHint": False},
    )
    async def create_engine_field(
        engine_id: int,
        name: str,
        label: str,
        field_type: EngineFieldType,
        schema_ids: list[int],
        tabular: bool = False,
        multiline: bool = False,
        subtype: str | None = None,
        pre_trained_field_id: str | None = None,
    ) -> EngineField | dict:
        return await _create_engine_field(
            client,
            base_url,
            engine_id,
            name,
            label,
            field_type,
            schema_ids,
            tabular,
            multiline,
            subtype,
            pre_trained_field_id,
        )

    # --- Hooks ---
    @mcp.tool(
        description="Create a hook. Function hooks: config.source auto-renamed to config.code, default runtime python3.12, timeout_s capped at 60. secrets is a dict of key-value env vars for serverless functions (write-only, values never returned). token_owner is a User URL for API token generation (cannot be organization_group_admin). run_after is a list of hook URLs that must execute before this hook. sideload controls which related objects are included in hook request payloads.",
        tags={"hooks", "write"},
        annotations={"readOnlyHint": False},
    )
    async def create_hook(
        name: str,
        type: HookType,
        queues: list[str] | None = None,
        events: list[HookEventAndAction] | None = None,
        config: dict | None = None,
        settings: dict | None = None,
        secrets: dict[str, str] | None = None,
        token_owner: str | None = None,
        run_after: list[str] | None = None,
        sideload: list[HookSideload] | None = None,
    ) -> Hook:
        return await _create_hook(
            client, name, type, queues, events, config, settings, secrets, token_owner, run_after, sideload
        )

    @mcp.tool(
        description="Create a hook from a template; events may override template defaults. If template requires use_token_owner, provide token_owner (not an organization_group_admin user).",
        tags={"hooks", "write"},
        annotations={"readOnlyHint": False},
    )
    async def create_hook_from_template(
        name: str,
        hook_template_id: int,
        queues: list[str],
        events: list[HookEventAndAction] | None = None,
        token_owner: str | None = None,
    ) -> Hook:
        return await _create_hook_from_template(client, name, hook_template_id, queues, events, token_owner)

    # --- Rules ---
    @mcp.tool(
        description="Create a rule: trigger is a TxScript condition; action includes id, type, event, payload. Scope with schema_id and/or queue_ids (at least one required).",
        tags={"rules", "write"},
        annotations={"readOnlyHint": False},
    )
    async def create_rule(
        name: str,
        trigger_condition: str,
        actions: list[RuleAction],
        enabled: bool = True,
        schema_id: int | None = None,
        queue_ids: list[int] | None = None,
    ) -> Rule | dict:
        return await _create_rule(client, base_url, name, trigger_condition, actions, enabled, schema_id, queue_ids)

    # --- Users ---
    @mcp.tool(
        description="Create a user (requires username + email). Use list_user_roles for role/group URLs; queue/group fields take full API URLs.",
        tags={"users", "write"},
        annotations={"readOnlyHint": False},
    )
    async def create_user(
        username: str,
        email: str,
        queues: list[str] | None = None,
        groups: list[str] | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        is_active: bool = True,
        metadata: dict | None = None,
        oidc_id: str | None = None,
        auth_type: str = "password",
    ) -> User | dict:
        return await _create_user(
            client, username, email, queues, groups, first_name, last_name, is_active, metadata, oidc_id, auth_type
        )

    # --- Workspaces ---
    @mcp.tool(
        description="Create a new workspace.",
        tags={"workspaces", "write"},
        annotations={"readOnlyHint": False},
    )
    async def create_workspace(name: str, organization_id: int, metadata: dict | None = None) -> Workspace | dict:
        return await _create_workspace(client, base_url, name, organization_id, metadata)

    # --- Email Templates ---
    @mcp.tool(
        description="Create an email template; set automate=true for automatic sending. to/cc/bcc are recipient objects {type: annotator|constant|datapoint, value: ...}.",
        tags={"email_templates", "write"},
        annotations={"readOnlyHint": False},
    )
    async def create_email_template(
        name: str,
        queue: int,
        subject: str,
        message: str,
        type: EmailTemplateType = EmailTemplateType.CUSTOM,
        automate: bool = False,
        to: list[EmailRecipient] | None = None,
        cc: list[EmailRecipient] | None = None,
        bcc: list[EmailRecipient] | None = None,
        triggers: list[str] | None = None,
    ) -> EmailTemplate | dict:
        return await _create_email_template(
            client, base_url, name, queue, subject, message, type, automate, to, cc, bcc, triggers
        )
