"""Schema patching utilities for Rossum MCP Server."""

from __future__ import annotations

import copy
from enum import StrEnum


class PatchOperation(StrEnum):
    ADD = "add"
    UPDATE = "update"
    REMOVE = "remove"


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
