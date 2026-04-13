"""Schema update operations: update, patch, prune."""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import asdict
from typing import TYPE_CHECKING

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from rossum_api import APIClientError, AsyncRossumAPIClient
from rossum_api.domain_logic.resources import Resource

from rossum_mcp.models.schema import (
    SchemaNode,  # noqa: TC001 - needed at runtime for FastMCP parameter serialization
)
from rossum_mcp.tools.update.models import (
    SchemaNodeUpdate,  # noqa: TC001 - needed at runtime for FastMCP parameter serialization
)
from rossum_mcp.tools.update.schemas.patching import (
    PatchOperation,
    _find_node_anywhere,
    apply_schema_patch,
)
from rossum_mcp.tools.update.schemas.pruning import (
    _collect_all_field_ids,
    _collect_ancestor_ids,
    _remove_fields_from_content,
)
from rossum_mcp.tools.validation import sanitize_schema_content

if TYPE_CHECKING:
    from collections.abc import Callable

MAX_RETRIES_ON_PRECONDITION_FAILED = 5

logger = logging.getLogger(__name__)


async def _update_schema_with_retry(
    client: AsyncRossumAPIClient,
    schema_id: int,
    prepare_content: Callable[[list], list | None],
) -> tuple[list, list | None]:
    """Fetch schema, transform content, update with retry on 412 Precondition Failed.

    prepare_content receives the current content list and returns the transformed content,
    or None to indicate no changes are needed.

    Returns (original_content, transformed_content). transformed_content is None
    when prepare_content returned None.
    """
    for attempt in range(MAX_RETRIES_ON_PRECONDITION_FAILED):
        current_schema: dict = await client._http_client.request_json("GET", f"schemas/{schema_id}")
        content = current_schema.get("content", [])
        if not isinstance(content, list):
            raise ValueError("Unexpected schema content format")

        new_content = prepare_content(content)
        if new_content is None:
            return content, None

        sanitized = sanitize_schema_content(new_content)
        try:
            await client._http_client.update(Resource.Schema, schema_id, {"content": sanitized})
            return content, new_content
        except APIClientError as e:
            if e.status_code == 412 and attempt < MAX_RETRIES_ON_PRECONDITION_FAILED - 1:
                logger.warning(
                    f"Schema {schema_id} was modified concurrently (412 Precondition Failed), "
                    f"retrying ({attempt + 1}/{MAX_RETRIES_ON_PRECONDITION_FAILED})..."
                )
                await asyncio.sleep(0.5 * (attempt + 1) + random.uniform(0, 0.5))
                continue
            raise
    raise RuntimeError("Unreachable")


async def _patch_schema(
    client: AsyncRossumAPIClient,
    schema_id: int,
    operation: PatchOperation,
    node_id: str,
    node_data: SchemaNode | SchemaNodeUpdate | None = None,
    parent_id: str | None = None,
    position: int | None = None,
    after_field: str | None = None,
    before_field: str | None = None,
) -> dict:
    if operation not in ("add", "update", "remove"):
        raise ToolError(f"Invalid operation '{operation}'. Must be 'add', 'update', or 'remove'.")

    logger.debug(f"Patching schema: schema_id={schema_id}, operation={operation}, node_id={node_id}")

    node_data_dict: dict | None = None
    if node_data is not None:
        if isinstance(node_data, dict):
            node_data_dict = node_data
        elif hasattr(node_data, "to_dict"):
            node_data_dict = node_data.to_dict()
        else:
            node_data_dict = asdict(node_data)

    def prepare(content: list) -> list:
        return apply_schema_patch(
            content=content,
            operation=operation,
            node_id=node_id,
            node_data=node_data_dict,
            parent_id=parent_id,
            position=position,
            after_field=after_field,
            before_field=before_field,
        )

    try:
        _, result_content = await _update_schema_with_retry(client, schema_id, prepare)
    except ValueError as e:
        raise ToolError(str(e)) from e

    # Return concise confirmation with the affected node instead of the full schema
    if result_content is None:
        raise ToolError("Schema update returned no content")
    node, _, _, _ = _find_node_anywhere(result_content, node_id)
    return {
        "status": "success",
        "schema_id": schema_id,
        "operation": operation,
        "node_id": node_id,
        "node": node,
    }


async def _prune_schema_fields(
    client: AsyncRossumAPIClient,
    schema_id: int,
    fields_to_keep: list[str] | None = None,
    fields_to_remove: list[str] | None = None,
) -> dict:
    if fields_to_keep is not None and fields_to_remove is not None:
        raise ToolError("Specify fields_to_keep OR fields_to_remove, not both")
    if fields_to_keep is None and fields_to_remove is None:
        raise ToolError("Must specify fields_to_keep or fields_to_remove")

    def prepare(content: list) -> list | None:
        all_ids = _collect_all_field_ids(content)
        section_ids = {s.get("id") for s in content if s.get("category") == "section"}

        if fields_to_keep is not None:
            fields_to_keep_set = set(fields_to_keep)
            ancestor_ids = _collect_ancestor_ids(content, fields_to_keep_set)
            fields_to_keep_set |= ancestor_ids
            remove_set = all_ids - fields_to_keep_set
            # Sections explicitly listed in fields_to_keep are preserved as empty containers
            keep_empty_sections = set(fields_to_keep) & section_ids
        else:
            remove_set = set(fields_to_remove) - section_ids  # ty:ignore[invalid-argument-type]
            keep_empty_sections = set()

        if not remove_set:
            return None

        pruned_content, _ = _remove_fields_from_content(content, remove_set)

        # Re-add sections that were auto-removed (empty) but explicitly requested
        if keep_empty_sections:
            kept_ids = {s.get("id") for s in pruned_content}
            for section in content:
                sid = section.get("id")
                if sid in keep_empty_sections and sid not in kept_ids:
                    pruned_content.append(
                        {"id": sid, "label": section.get("label", ""), "category": "section", "children": []}
                    )

        return pruned_content

    try:
        original_content, result_content = await _update_schema_with_retry(client, schema_id, prepare)
    except ValueError as e:
        raise ToolError(str(e)) from e

    if result_content is None:
        all_ids = _collect_all_field_ids(original_content)
        return {"removed_fields": [], "remaining_fields": sorted(all_ids)}

    all_ids = _collect_all_field_ids(original_content)
    remaining_ids = _collect_all_field_ids(result_content)
    return {"removed_fields": sorted(all_ids - remaining_ids), "remaining_fields": sorted(remaining_ids)}


def register_schema_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(
        description="Patch schema nodes (add/update/remove). Prereq: load schema-patching skill. Ops: add (parent_id + node_data), update (node_id + node_data), remove (node_id only). Tuple datapoints require explicit id; section-level datapoints use the passed node_id. Use after_field/before_field to control insertion position.",
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
        after_field: str | None = None,
        before_field: str | None = None,
    ) -> dict:
        return await _patch_schema(
            client, schema_id, operation, node_id, node_data, parent_id, position, after_field, before_field
        )

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
