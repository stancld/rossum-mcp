from __future__ import annotations

import logging

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from rossum_api import AsyncRossumAPIClient
from rossum_api.models.hook import Hook, HookAction, HookEvent, HookEventAndAction

from rossum_mcp.models.hook import (
    HookSideload,  # noqa: TC001 - needed at runtime for FastMCP parameter serialization
)
from rossum_mcp.tools.base import extract_id_from_url
from rossum_mcp.tools.validation import validate_hook_events

logger = logging.getLogger(__name__)


async def _update_hook(
    client: AsyncRossumAPIClient,
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
    logger.debug(f"Updating hook: hook_id={hook_id}")

    existing_hook: Hook = await client.retrieve_hook(hook_id)
    hook_data: dict = {
        "name": existing_hook.name,
        "queues": existing_hook.queues,
        "events": list(existing_hook.events),
        "config": dict(existing_hook.config) if existing_hook.config else {},
    }

    if name is not None:
        hook_data["name"] = name
    if queues is not None:
        hook_data["queues"] = queues
    if events is not None:
        hook_data["events"] = validate_hook_events(events)
    if config is not None:
        hook_data["config"] = config
    if settings is not None:
        hook_data["settings"] = settings
    if active is not None:
        hook_data["active"] = active
    if secrets is not None:
        hook_data["secrets"] = secrets
    if token_owner is not None:
        hook_data["token_owner"] = token_owner
    if run_after is not None:
        hook_data["run_after"] = run_after
    if sideload is not None:
        hook_data["sideload"] = sideload

    updated_hook: Hook = await client.update_part_hook(hook_id, hook_data)
    return updated_hook


async def _test_hook(
    client: AsyncRossumAPIClient,
    hook_id: int,
    event: HookEvent,
    action: HookAction,
    annotation: str | None = None,
    status: str | None = None,
    previous_status: str | None = None,
    config: dict | None = None,
) -> dict:
    payload = await _generate_hook_payload(client, hook_id, event, action, annotation, status, previous_status)
    body: dict = {"payload": payload}
    if config is not None:
        body["config"] = config
    return await client._http_client.request_json("POST", f"hooks/{hook_id}/test", json=body)


_ANNOTATION_EVENTS = {"annotation_content", "annotation_status"}
_DEFAULT_STATUS = "to_review"
_DEFAULT_PREVIOUS_STATUS = "importing"


async def _resolve_annotation_for_hook(client: AsyncRossumAPIClient, hook_id: int) -> str | None:
    hook = await client.retrieve_hook(hook_id)
    for queue_url in hook.queues or []:
        queue_id = extract_id_from_url(str(queue_url))
        params: dict = {"queue": queue_id, "page_size": 1, "status": "to_review,confirmed,exported,importing"}
        async for annotation in client.list_annotations(**params):
            return str(annotation.url)
    return None


async def _generate_hook_payload(
    client: AsyncRossumAPIClient,
    hook_id: int,
    event: HookEvent,
    action: HookAction,
    annotation: str | None = None,
    status: str | None = None,
    previous_status: str | None = None,
) -> dict:
    if event in _ANNOTATION_EVENTS:
        if annotation is None:
            annotation = await _resolve_annotation_for_hook(client, hook_id)
            if annotation is None:
                raise ToolError(
                    f"Event '{event}' requires an annotation but no annotations found on the hook's queues. "
                    "Either upload a document to one of the hook's queues first, "
                    "or pass an annotation URL from another queue explicitly via the 'annotation' parameter."
                )
        if status is None:
            status = _DEFAULT_STATUS
        if previous_status is None:
            previous_status = _DEFAULT_PREVIOUS_STATUS

    body: dict = {"event": event, "action": action}
    if annotation is not None:
        body["annotation"] = annotation
    if status is not None:
        body["status"] = status
    if previous_status is not None:
        body["previous_status"] = previous_status
    return await client._http_client.request_json("POST", f"hooks/{hook_id}/generate_payload", json=body)


def register_hook_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
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
