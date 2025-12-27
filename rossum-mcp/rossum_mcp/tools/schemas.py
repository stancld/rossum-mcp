"""Schema tools for Rossum MCP Server."""

from __future__ import annotations

import copy
import logging
from typing import TYPE_CHECKING, Literal

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.schema import Schema  # noqa: TC002 - needed at runtime for FastMCP

from rossum_mcp.tools.base import is_read_write_mode

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)

PatchOperation = Literal["add", "update", "remove"]


def _find_node_in_children(children: list[dict], node_id: str) -> tuple[dict | None, int | None, list[dict] | None]:
    """Recursively find a node by ID in schema children.

    Returns (node, index, parent_children_list) or (None, None, None) if not found.
    """
    for i, child in enumerate(children):
        if child.get("id") == node_id:
            return child, i, children

        nested_children = child.get("children")
        if nested_children:
            if isinstance(nested_children, list):
                result = _find_node_in_children(nested_children, node_id)
                if result[0] is not None:
                    return result
            elif isinstance(nested_children, dict):
                if nested_children.get("id") == node_id:
                    return nested_children, 0, [nested_children]
                if "children" in nested_children:
                    result = _find_node_in_children(nested_children["children"], node_id)
                    if result[0] is not None:
                        return result

    return None, None, None


def _find_parent_children_list(content: list[dict], parent_id: str) -> list[dict] | None:
    """Find the children list of a parent node by its ID."""
    for section in content:
        if section.get("id") == parent_id:
            children: list[dict] = section.setdefault("children", [])
            return children

        section_children = section.get("children", [])
        node, _, _ = _find_node_in_children(section_children, parent_id)
        if node is not None:
            if "children" in node:
                if isinstance(node["children"], list):
                    result: list[dict] = node["children"]
                    return result
                if isinstance(node["children"], dict):
                    return [node["children"]]
            else:
                node["children"] = []
                node_children: list[dict] = node["children"]
                return node_children

    return None


def _apply_add_operation(
    content: list[dict],
    node_id: str,
    node_data: dict | None,
    parent_id: str | None,
    position: int | None,
) -> list[dict]:
    """Apply an add operation to schema content."""
    if node_data is None:
        raise ValueError("node_data is required for 'add' operation")
    if parent_id is None:
        raise ValueError("parent_id is required for 'add' operation")

    node_data = copy.deepcopy(node_data)
    node_data["id"] = node_id

    parent_children = _find_parent_children_list(content, parent_id)
    if parent_children is None:
        raise ValueError(f"Parent node '{parent_id}' not found in schema")

    if position is not None and 0 <= position <= len(parent_children):
        parent_children.insert(position, node_data)
    else:
        parent_children.append(node_data)
    return content


def _apply_update_operation(
    content: list[dict],
    node_id: str,
    node_data: dict | None,
) -> list[dict]:
    """Apply an update operation to schema content."""
    if node_data is None:
        raise ValueError("node_data is required for 'update' operation")

    for section in content:
        if section.get("id") == node_id:
            section.update(node_data)
            return content

    node: dict | None = None
    for section in content:
        node, _, _ = _find_node_in_children(section.get("children", []), node_id)
        if node is not None:
            break

    if node is None:
        raise ValueError(f"Node '{node_id}' not found in schema")

    node.update(node_data)
    return content


def _apply_remove_operation(content: list[dict], node_id: str) -> list[dict]:
    """Apply a remove operation to schema content."""
    for section in content:
        if section.get("id") == node_id:
            raise ValueError("Cannot remove a section - sections must exist")

    for section in content:
        section_children = section.get("children", [])
        node, idx, parent_list = _find_node_in_children(section_children, node_id)
        if node is not None and idx is not None and parent_list is not None:
            parent_list.pop(idx)
            return content

    raise ValueError(f"Node '{node_id}' not found in schema")


def apply_schema_patch(
    content: list[dict],
    operation: PatchOperation,
    node_id: str,
    node_data: dict | None = None,
    parent_id: str | None = None,
    position: int | None = None,
) -> list[dict]:
    """Apply a patch operation to schema content.

    Args:
        content: The schema content (list of sections)
        operation: One of "add", "update", "remove"
        node_id: ID of the node to operate on
        node_data: Data for add/update operations
        parent_id: Parent node ID for add operation (section ID or multivalue/tuple ID)
        position: Optional position for add operation (appends if not specified)

    Returns:
        Modified content

    Raises:
        ValueError: If the operation cannot be completed
    """
    content = copy.deepcopy(content)

    if operation == "add":
        return _apply_add_operation(content, node_id, node_data, parent_id, position)
    if operation == "update":
        return _apply_update_operation(content, node_id, node_data)
    if operation == "remove":
        return _apply_remove_operation(content, node_id)

    return content


def register_schema_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    """Register schema-related tools with the FastMCP server."""

    @mcp.tool(description="Retrieve schema details.")
    async def get_schema(schema_id: int) -> Schema:
        """Retrieve schema details."""
        logger.debug(f"Retrieving schema: schema_id={schema_id}")
        schema: Schema = await client.retrieve_schema(schema_id)
        return schema

    @mcp.tool(description="Update schema, typically for field-level thresholds.")
    async def update_schema(schema_id: int, schema_data: dict) -> Schema | dict:
        """Update an existing schema."""
        if not is_read_write_mode():
            return {"error": "update_schema is not available in read-only mode"}

        logger.debug(f"Updating schema: schema_id={schema_id}")
        await client._http_client.update(Resource.Schema, schema_id, schema_data)
        updated_schema: Schema = await client.retrieve_schema(schema_id)
        return updated_schema

    @mcp.tool(description="Create a schema. Must have ≥1 section with children (datapoints).")
    async def create_schema(name: str, content: list[dict]) -> Schema | dict:
        """Create a new schema."""
        if not is_read_write_mode():
            return {"error": "create_schema is not available in read-only mode"}

        logger.debug(f"Creating schema: name={name}")
        schema_data = {"name": name, "content": content}
        schema: Schema = await client.create_new_schema(schema_data)
        return schema

    @mcp.tool(
        description="""Patch a schema by adding, updating, or removing individual nodes.

Schema hierarchy: Section → Datapoint | Multivalue → Tuple → Datapoint
- Section: top-level container (children is a list)
- Multivalue: table container (children is a SINGLE Tuple or Datapoint, NOT a list)
- Tuple: row template within multivalue (children is a list of Datapoints)

Operations:
- "add": Add a node to a parent's children list. Requires parent_id and node_data.
- "update": Update properties of an existing node. Requires node_data with fields to update.
- "remove": Remove a node from the schema. Only node_id is required.

Examples:
1. Add a datapoint to a section:
   patch_schema(schema_id=123, operation="add", node_id="vendor_name",
                parent_id="header_section", node_data={"label": "Vendor", "type": "string", "category": "datapoint"})

2. Add a multivalue with repeating simple field (single datapoint, not a table):
   patch_schema(schema_id=123, operation="add", node_id="po_numbers",
                parent_id="header_section", node_data={
                    "label": "PO Numbers", "category": "multivalue",
                    "children": {"id": "po_number", "label": "PO Number", "type": "string", "category": "datapoint"}
                })

3. Add a multivalue table (with tuple containing multiple columns):
   patch_schema(schema_id=123, operation="add", node_id="line_items",
                parent_id="line_items_section", node_data={
                    "label": "Line Items", "category": "multivalue",
                    "children": {"id": "line_item", "category": "tuple", "children": [
                        {"id": "item_description", "label": "Description", "type": "string", "category": "datapoint"},
                        {"id": "item_amount", "label": "Amount", "type": "number", "category": "datapoint"}
                    ]}
                })

4. Add a column to existing table (add datapoint to tuple):
   patch_schema(schema_id=123, operation="add", node_id="item_quantity",
                parent_id="line_item", node_data={"label": "Quantity", "type": "number", "category": "datapoint"})

5. Update a field's label and threshold:
   patch_schema(schema_id=123, operation="update", node_id="invoice_number",
                node_data={"label": "Invoice #", "score_threshold": 0.9})

6. Remove a field:
   patch_schema(schema_id=123, operation="remove", node_id="old_field")
"""
    )
    async def patch_schema(
        schema_id: int,
        operation: PatchOperation,
        node_id: str,
        node_data: dict | None = None,
        parent_id: str | None = None,
        position: int | None = None,
    ) -> Schema | dict:
        """Patch a schema by adding, updating, or removing individual nodes."""
        if not is_read_write_mode():
            return {"error": "patch_schema is not available in read-only mode"}

        if operation not in ("add", "update", "remove"):
            return {"error": f"Invalid operation '{operation}'. Must be 'add', 'update', or 'remove'."}

        logger.debug(f"Patching schema: schema_id={schema_id}, operation={operation}, node_id={node_id}")

        current_schema: dict = await client._http_client.request_json("GET", f"schemas/{schema_id}")
        content_list = current_schema.get("content", [])
        if not isinstance(content_list, list):
            return {"error": "Unexpected schema content format"}

        try:
            patched_content = apply_schema_patch(
                content=content_list,
                operation=operation,  # type: ignore[arg-type]
                node_id=node_id,
                node_data=node_data,
                parent_id=parent_id,
                position=position,
            )
        except ValueError as e:
            return {"error": str(e)}

        await client._http_client.update(Resource.Schema, schema_id, {"content": patched_content})
        updated_schema: Schema = await client.retrieve_schema(schema_id)
        return updated_schema
