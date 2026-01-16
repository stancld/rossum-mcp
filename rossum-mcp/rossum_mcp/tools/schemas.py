"""Schema tools for Rossum MCP Server."""

from __future__ import annotations

import copy
import logging
from dataclasses import asdict, dataclass, is_dataclass, replace
from typing import TYPE_CHECKING, Any, Literal

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.schema import Schema

from rossum_mcp.tools.base import TRUNCATED_MARKER, is_read_write_mode

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)

PatchOperation = Literal["add", "update", "remove"]
DatapointType = Literal["string", "number", "date", "enum", "button"]
NodeCategory = Literal["datapoint", "multivalue", "tuple"]

MAX_ID_LENGTH = 50
VALID_DATAPOINT_TYPES = {"string", "number", "date", "enum", "button"}


class SchemaValidationError(ValueError):
    """Raised when schema validation fails."""


def _validate_id(node_id: str, context: str = "") -> None:
    """Validate node ID constraints."""
    if not node_id:
        raise SchemaValidationError(f"Node id is required{context}")
    if len(node_id) > MAX_ID_LENGTH:
        raise SchemaValidationError(f"Node id '{node_id}' exceeds {MAX_ID_LENGTH} characters{context}")


def _validate_datapoint(node: dict, context: str = "") -> None:
    """Validate a datapoint node has required fields."""
    if "label" not in node:
        raise SchemaValidationError(f"Datapoint missing required 'label'{context}")
    if "type" not in node:
        raise SchemaValidationError(f"Datapoint missing required 'type'{context}")
    if node["type"] not in VALID_DATAPOINT_TYPES:
        raise SchemaValidationError(
            f"Invalid datapoint type '{node['type']}'. Must be one of: {', '.join(VALID_DATAPOINT_TYPES)}{context}"
        )


def _validate_tuple(node: dict, node_id: str, context: str) -> None:
    """Validate a tuple node."""
    if "label" not in node:
        raise SchemaValidationError(f"Tuple missing required 'label'{context}")
    if "id" not in node:
        raise SchemaValidationError(f"Tuple missing required 'id'{context}")
    children = node.get("children", [])
    if not isinstance(children, list):
        raise SchemaValidationError(f"Tuple children must be a list{context}")
    for i, child in enumerate(children):
        child_id = child.get("id", f"index {i}")
        _validate_node(child, f" in tuple '{node_id}' child '{child_id}'")
        if "id" not in child:
            raise SchemaValidationError(f"Datapoint inside tuple must have 'id'{context} child index {i}")


def _validate_multivalue(node: dict, node_id: str, context: str) -> None:
    """Validate a multivalue node."""
    if "label" not in node:
        raise SchemaValidationError(f"Multivalue missing required 'label'{context}")
    children = node.get("children")
    if children is None:
        raise SchemaValidationError(f"Multivalue missing required 'children'{context}")
    if isinstance(children, list):
        raise SchemaValidationError(f"Multivalue 'children' must be a single object (dict), not a list{context}")
    if isinstance(children, dict):
        _validate_node(children, f" in multivalue '{node_id}' children")


def _validate_section(node: dict, node_id: str, context: str) -> None:
    """Validate a section node."""
    if "label" not in node:
        raise SchemaValidationError(f"Section missing required 'label'{context}")
    if "id" not in node:
        raise SchemaValidationError(f"Section missing required 'id'{context}")
    children = node.get("children", [])
    if not isinstance(children, list):
        raise SchemaValidationError(f"Section children must be a list{context}")
    for child in children:
        child_id = child.get("id", "unknown")
        _validate_node(child, f" in section '{node_id}' child '{child_id}'")


def _validate_node(node: dict, context: str = "") -> None:
    """Validate a schema node recursively."""
    category = node.get("category")
    node_id = node.get("id", "")

    if node_id:
        _validate_id(node_id, context)

    if category == "datapoint":
        _validate_datapoint(node, context)
    elif category == "tuple":
        _validate_tuple(node, node_id, context)
    elif category == "multivalue":
        _validate_multivalue(node, node_id, context)
    elif category == "section":
        _validate_section(node, node_id, context)


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


@dataclass
class SchemaNodeUpdate:
    """Partial update for an existing schema node.

    Only include fields you want to update - all fields are optional.
    """

    label: str | None = None
    type: DatapointType | None = None
    score_threshold: float | None = None
    hidden: bool | None = None
    disable_prediction: bool | None = None
    can_export: bool | None = None
    default_value: str | None = None
    rir_field_names: list[str] | None = None
    constraints: dict | None = None
    options: list[dict] | None = None
    ui_configuration: dict | None = None
    formula: str | None = None
    prompt: str | None = None
    context: list[str] | None = None
    width: int | None = None
    stretch: bool | None = None
    min_occurrences: int | None = None
    max_occurrences: int | None = None

    def to_dict(self) -> dict:
        """Convert to dict, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


SchemaNode = SchemaDatapoint | SchemaMultivalue | SchemaTuple


def _find_node_in_children(
    children: list[dict], node_id: str, parent_node: dict | None = None
) -> tuple[dict | None, int | None, list[dict] | None, dict | None]:
    """Recursively find a node by ID in schema children.

    Returns (node, index, parent_children_list, parent_node) or (None, None, None, None) if not found.
    The parent_node is needed for multivalue's dict children where we need to modify the parent directly.
    """
    for i, child in enumerate(children):
        if child.get("id") == node_id:
            return child, i, children, parent_node

        nested_children = child.get("children")
        if nested_children:
            if isinstance(nested_children, list):
                result = _find_node_in_children(nested_children, node_id, child)
                if result[0] is not None:
                    return result
            elif isinstance(nested_children, dict):
                if nested_children.get("id") == node_id:
                    return nested_children, 0, None, child
                if "children" in nested_children:
                    result = _find_node_in_children(nested_children["children"], node_id, nested_children)
                    if result[0] is not None:
                        return result

    return None, None, None, None


def _is_multivalue_node(node: dict) -> bool:
    """Check if a node is a multivalue (has dict children or category is multivalue)."""
    return node.get("category") == "multivalue" or ("children" in node and isinstance(node["children"], dict))


def _find_parent_children_list(content: list[dict], parent_id: str) -> tuple[list[dict] | None, bool]:
    """Find the children list of a parent node by its ID.

    Returns (children_list, is_multivalue) tuple.
    For multivalue nodes, returns (None, True) since they can't have children added.
    """
    for section in content:
        if section.get("id") == parent_id:
            if _is_multivalue_node(section):
                return None, True
            children: list[dict] = section.setdefault("children", [])
            return children, False

        section_children = section.get("children")
        if section_children is None:
            continue

        if isinstance(section_children, list):
            node, _, _, _ = _find_node_in_children(section_children, parent_id)
        else:
            if section_children.get("id") == parent_id:
                node = section_children
            elif "children" in section_children:
                node, _, _, _ = _find_node_in_children(section_children.get("children", []), parent_id)
            else:
                node = None

        if node is not None:
            if _is_multivalue_node(node):
                return None, True
            if "children" in node:
                if isinstance(node["children"], list):
                    result: list[dict] = node["children"]
                    return result, False
            else:
                node["children"] = []
                node_children: list[dict] = node["children"]
                return node_children, False

    return None, False


def _apply_add_operation(
    content: list[dict], node_id: str, node_data: dict | None, parent_id: str | None, position: int | None
) -> list[dict]:
    if node_data is None:
        raise ValueError("node_data is required for 'add' operation")
    if parent_id is None:
        raise ValueError("parent_id is required for 'add' operation")

    node_data = copy.deepcopy(node_data)
    node_data["id"] = node_id

    parent_children, is_multivalue = _find_parent_children_list(content, parent_id)
    if is_multivalue:
        raise ValueError(
            f"Cannot add children to multivalue '{parent_id}'. "
            "Multivalue nodes have a single child (tuple or datapoint). "
            "Use 'update' to replace the multivalue's children, or add to the tuple inside it."
        )
    if parent_children is None:
        raise ValueError(f"Parent node '{parent_id}' not found in schema")

    if position is not None and 0 <= position <= len(parent_children):
        parent_children.insert(position, node_data)
    else:
        parent_children.append(node_data)
    return content


def _get_section_children_as_list(section: dict) -> list[dict]:
    """Get section children as a list, handling both list and dict (multivalue) cases."""
    children = section.get("children")
    if children is None:
        return []
    if isinstance(children, list):
        return children
    if isinstance(children, dict):
        return [children]
    return []


def _find_node_anywhere(
    content: list[dict], node_id: str
) -> tuple[dict | None, int | None, list[dict] | None, dict | None]:
    """Find a node by ID anywhere in the schema content.

    Returns (node, index, parent_children_list, parent_node).
    """
    for section in content:
        if section.get("id") == node_id:
            return section, None, None, None

        section_children = _get_section_children_as_list(section)
        result = _find_node_in_children(section_children, node_id, section)
        if result[0] is not None:
            return result

    return None, None, None, None


def _apply_update_operation(content: list[dict], node_id: str, node_data: dict | None) -> list[dict]:
    if node_data is None:
        raise ValueError("node_data is required for 'update' operation")

    node, _, _, _ = _find_node_anywhere(content, node_id)

    if node is None:
        raise ValueError(f"Node '{node_id}' not found in schema")

    node.update(node_data)
    return content


def _apply_remove_operation(content: list[dict], node_id: str) -> list[dict]:
    for section in content:
        if section.get("id") == node_id and section.get("category") == "section":
            raise ValueError("Cannot remove a section - sections must exist")

    node, idx, parent_list, parent_node = _find_node_anywhere(content, node_id)

    if node is None:
        raise ValueError(f"Node '{node_id}' not found in schema")

    if idx is None and parent_list is None:
        if node.get("category") == "section":
            raise ValueError("Cannot remove a section - sections must exist")
        raise ValueError(f"Cannot determine how to remove node '{node_id}'")

    if parent_list is not None and idx is not None:
        parent_list.pop(idx)
    elif parent_node is not None:
        if parent_node.get("category") == "multivalue":
            raise ValueError(f"Cannot remove '{node_id}' from multivalue - remove the multivalue instead")
        raise ValueError(f"Cannot remove '{node_id}' - unexpected parent structure")

    return content


def apply_schema_patch(
    content: list[dict],
    operation: PatchOperation,
    node_id: str,
    node_data: dict | None = None,
    parent_id: str | None = None,
    position: int | None = None,
) -> list[dict]:
    """Apply a patch operation to schema content."""
    content = copy.deepcopy(content)

    if operation == "add":
        return _apply_add_operation(content, node_id, node_data, parent_id, position)
    if operation == "update":
        return _apply_update_operation(content, node_id, node_data)
    if operation == "remove":
        return _apply_remove_operation(content, node_id)

    return content


async def _get_schema(client: AsyncRossumAPIClient, schema_id: int) -> Schema:
    schema: Schema = await client.retrieve_schema(schema_id)
    return schema


@dataclass
class SchemaTreeNode:
    """Lightweight schema node for tree structure display."""

    id: str
    label: str
    category: str
    type: str | None = None
    children: list[SchemaTreeNode] | None = None

    def to_dict(self) -> dict:
        """Convert to dict, excluding None values."""
        result: dict = {"id": self.id, "label": self.label, "category": self.category}
        if self.type:
            result["type"] = self.type
        if self.children:
            result["children"] = [child.to_dict() for child in self.children]
        return result


def _build_tree_node(node: dict) -> SchemaTreeNode:
    """Build a lightweight tree node from a schema node."""
    category = node.get("category", "")
    node_id = node.get("id", "")
    label = node.get("label", "")
    node_type = node.get("type") if category == "datapoint" else None

    children_data = node.get("children")
    children: list[SchemaTreeNode] | None = None

    if children_data is not None:
        if isinstance(children_data, list):
            children = [_build_tree_node(child) for child in children_data]
        elif isinstance(children_data, dict):
            children = [_build_tree_node(children_data)]

    return SchemaTreeNode(id=node_id, label=label, category=category, type=node_type, children=children)


def _extract_schema_tree(content: list[dict]) -> list[dict]:
    """Extract lightweight tree structure from schema content."""
    return [_build_tree_node(section).to_dict() for section in content]


def _collect_all_field_ids(content: list[dict]) -> set[str]:
    """Collect all field IDs from schema content recursively."""
    ids: set[str] = set()

    def _traverse(node: dict) -> None:
        node_id = node.get("id")
        if node_id:
            ids.add(node_id)
        children = node.get("children")
        if children is not None:
            if isinstance(children, list):
                for child in children:
                    _traverse(child)
            elif isinstance(children, dict):
                _traverse(children)

    for section in content:
        _traverse(section)

    return ids


def _collect_ancestor_ids(content: list[dict], target_ids: set[str]) -> set[str]:
    """Collect all ancestor IDs for the given target field IDs.

    Returns set of IDs for all parent containers (multivalue, tuple, section) of target fields.
    """
    ancestors: set[str] = set()

    def _find_ancestors(node: dict, path: list[str]) -> None:
        node_id = node.get("id", "")
        current_path = [*path, node_id] if node_id else path

        if node_id in target_ids:
            ancestors.update(current_path[:-1])

        children = node.get("children")
        if children is not None:
            if isinstance(children, list):
                for child in children:
                    _find_ancestors(child, current_path)
            elif isinstance(children, dict):
                _find_ancestors(children, current_path)

    for section in content:
        _find_ancestors(section, [])

    return ancestors


def _remove_fields_from_content(content: list[dict], fields_to_remove: set[str]) -> tuple[list[dict], list[str]]:
    """Remove multiple fields from schema content.

    Returns (modified_content, list_of_removed_field_ids).
    Sections cannot be removed.
    """
    content = copy.deepcopy(content)
    removed: list[str] = []

    def _filter_children(children: list[dict]) -> list[dict]:
        result = []
        for child in children:
            child_id = child.get("id", "")
            category = child.get("category", "")

            if child_id in fields_to_remove and category != "section":
                removed.append(child_id)
                continue

            nested = child.get("children")
            if nested is not None:
                if isinstance(nested, list):
                    child["children"] = _filter_children(nested)
                elif isinstance(nested, dict):
                    nested_id = nested.get("id", "")
                    if nested_id in fields_to_remove:
                        removed.append(nested_id)
                        removed.append(child_id)
                        continue
                    nested_children = nested.get("children")
                    if isinstance(nested_children, list):
                        filtered_nested = _filter_children(nested_children)
                        if not filtered_nested:
                            removed.append(nested_id)
                            removed.append(child_id)
                            continue
                        nested["children"] = filtered_nested
            result.append(child)
        return result

    for section in content:
        section_children = section.get("children")
        if isinstance(section_children, list):
            section["children"] = _filter_children(section_children)

    # Remove sections with empty children (API rejects empty sections)
    removed_sections = [s.get("id", "") for s in content if not s.get("children")]
    removed.extend(removed_sections)
    content = [s for s in content if s.get("children")]

    return content, removed


def _truncate_schema_for_list(schema: Schema) -> Schema:
    """Truncate content field in schema to save context in list responses."""
    return replace(schema, content=TRUNCATED_MARKER)


async def _list_schemas(
    client: AsyncRossumAPIClient, name: str | None = None, queue_id: int | None = None
) -> list[Schema]:
    logger.debug(f"Listing schemas: name={name}, queue_id={queue_id}")
    filters: dict[str, int | str] = {}
    if name is not None:
        filters["name"] = name
    if queue_id is not None:
        filters["queue"] = queue_id

    schemas = [schema async for schema in client.list_schemas(**filters)]  # type: ignore[arg-type]
    return [_truncate_schema_for_list(schema) for schema in schemas]


async def _update_schema(client: AsyncRossumAPIClient, schema_id: int, schema_data: dict) -> Schema | dict:
    if not is_read_write_mode():
        return {"error": "update_schema is not available in read-only mode"}

    logger.debug(f"Updating schema: schema_id={schema_id}")
    await client._http_client.update(Resource.Schema, schema_id, schema_data)
    updated_schema: Schema = await client.retrieve_schema(schema_id)
    return updated_schema


async def _create_schema(client: AsyncRossumAPIClient, name: str, content: list[dict]) -> Schema | dict:
    if not is_read_write_mode():
        return {"error": "create_schema is not available in read-only mode"}

    logger.debug(f"Creating schema: name={name}")
    schema_data = {"name": name, "content": content}
    schema: Schema = await client.create_new_schema(schema_data)
    return schema


async def _patch_schema(
    client: AsyncRossumAPIClient,
    schema_id: int,
    operation: PatchOperation,
    node_id: str,
    node_data: SchemaNode | SchemaNodeUpdate | None = None,
    parent_id: str | None = None,
    position: int | None = None,
) -> Schema | dict:
    if not is_read_write_mode():
        return {"error": "patch_schema is not available in read-only mode"}

    if operation not in ("add", "update", "remove"):
        return {"error": f"Invalid operation '{operation}'. Must be 'add', 'update', or 'remove'."}

    logger.debug(f"Patching schema: schema_id={schema_id}, operation={operation}, node_id={node_id}")

    node_data_dict: dict | None = None
    if node_data is not None:
        if isinstance(node_data, dict):
            node_data_dict = node_data
        elif hasattr(node_data, "to_dict"):
            node_data_dict = node_data.to_dict()
        else:
            node_data_dict = asdict(node_data)

    current_schema: dict = await client._http_client.request_json("GET", f"schemas/{schema_id}")
    content_list = current_schema.get("content", [])
    if not isinstance(content_list, list):
        return {"error": "Unexpected schema content format"}

    try:
        patched_content = apply_schema_patch(
            content=content_list,
            operation=operation,
            node_id=node_id,
            node_data=node_data_dict,
            parent_id=parent_id,
            position=position,
        )
    except ValueError as e:
        return {"error": str(e)}

    await client._http_client.update(Resource.Schema, schema_id, {"content": patched_content})
    updated_schema: Schema = await client.retrieve_schema(schema_id)
    return updated_schema


async def _get_schema_tree_structure(client: AsyncRossumAPIClient, schema_id: int) -> list[dict]:
    schema = await _get_schema(client, schema_id)
    content_dicts: list[dict[str, Any]] = [
        asdict(section) if is_dataclass(section) else dict(section)  # type: ignore[arg-type]
        for section in schema.content
    ]
    return _extract_schema_tree(content_dicts)


async def _prune_schema_fields(
    client: AsyncRossumAPIClient,
    schema_id: int,
    fields_to_keep: list[str] | None = None,
    fields_to_remove: list[str] | None = None,
) -> dict:
    if not is_read_write_mode():
        return {"error": "prune_schema_fields is not available in read-only mode"}

    if fields_to_keep and fields_to_remove:
        return {"error": "Specify fields_to_keep OR fields_to_remove, not both"}
    if not fields_to_keep and not fields_to_remove:
        return {"error": "Must specify fields_to_keep or fields_to_remove"}

    current_schema: dict = await client._http_client.request_json("GET", f"schemas/{schema_id}")
    content = current_schema.get("content", [])
    if not isinstance(content, list):
        return {"error": "Unexpected schema content format"}
    all_ids = _collect_all_field_ids(content)

    section_ids = {s.get("id") for s in content if s.get("category") == "section"}

    if fields_to_keep:
        fields_to_keep_set = set(fields_to_keep) | section_ids
        ancestor_ids = _collect_ancestor_ids(content, fields_to_keep_set)
        fields_to_keep_set |= ancestor_ids
        remove_set = all_ids - fields_to_keep_set
    else:
        remove_set = set(fields_to_remove) - section_ids  # type: ignore[arg-type]

    if not remove_set:
        return {"removed_fields": [], "remaining_fields": sorted(all_ids)}

    pruned_content, removed = _remove_fields_from_content(content, remove_set)
    await client._http_client.update(Resource.Schema, schema_id, {"content": pruned_content})

    remaining_ids = _collect_all_field_ids(pruned_content)
    return {"removed_fields": sorted(removed), "remaining_fields": sorted(remaining_ids)}


def register_schema_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    """Register schema-related tools with the FastMCP server."""

    @mcp.tool(description="Retrieve schema details.")
    async def get_schema(schema_id: int) -> Schema:
        return await _get_schema(client, schema_id)

    @mcp.tool(description="List all schemas with optional filters.")
    async def list_schemas(name: str | None = None, queue_id: int | None = None) -> list[Schema]:
        return await _list_schemas(client, name, queue_id)

    @mcp.tool(description="Update schema, typically for field-level thresholds.")
    async def update_schema(schema_id: int, schema_data: dict) -> Schema | dict:
        return await _update_schema(client, schema_id, schema_data)

    @mcp.tool(description="Create a schema. Must have ≥1 section with children (datapoints).")
    async def create_schema(name: str, content: list[dict]) -> Schema | dict:
        return await _create_schema(client, name, content)

    @mcp.tool(
        description="""Patch schema nodes (add/update/remove fields in a schema).

You MUST load `schema-patching` skill first to avoid errors.

Operations:
- add: Create new field. Requires parent_id (section or tuple id) and node_data.
- update: Modify existing field. Requires node_data with fields to change.
- remove: Delete field. Only requires node_id.

Node types for add:
- Datapoint (simple field): {"label": "Field Name", "category": "datapoint", "type": "string|number|date|enum"}
- Enum field: Include "options": [{"value": "v1", "label": "Label 1"}, ...]
- Multivalue (table): {"label": "Table", "category": "multivalue", "children": <tuple>}
- Tuple (table row): {"id": "row_id", "label": "Row", "category": "tuple", "children": [<datapoints with id>]}

Important: Datapoints inside a tuple MUST have an "id" field. Section-level datapoints get id from node_id parameter.
"""
    )
    async def patch_schema(
        schema_id: int,
        operation: PatchOperation,
        node_id: str,
        node_data: SchemaNode | SchemaNodeUpdate | None = None,
        parent_id: str | None = None,
        position: int | None = None,
    ) -> Schema | dict:
        return await _patch_schema(client, schema_id, operation, node_id, node_data, parent_id, position)

    @mcp.tool(description="Get lightweight tree structure of schema with only ids, labels, categories, and types.")
    async def get_schema_tree_structure(schema_id: int) -> list[dict]:
        return await _get_schema_tree_structure(client, schema_id)

    @mcp.tool(
        description="""Remove multiple fields from schema at once. Efficient for pruning unwanted fields during setup.

Use fields_to_keep OR fields_to_remove (not both):
- fields_to_keep: Keep only these field IDs (plus sections). All others removed.
- fields_to_remove: Remove these specific field IDs.

Returns dict with removed_fields and remaining_fields lists. Sections cannot be removed."""
    )
    async def prune_schema_fields(
        schema_id: int,
        fields_to_keep: list[str] | None = None,
        fields_to_remove: list[str] | None = None,
    ) -> dict:
        return await _prune_schema_fields(client, schema_id, fields_to_keep, fields_to_remove)
