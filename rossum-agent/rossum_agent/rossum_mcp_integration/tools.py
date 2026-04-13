"""MCP tool utilities.

Pure functions for tool classification, entity extraction, format conversion,
and result unwrapping.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any, Literal, TypeAlias

from anthropic.types import ToolParam

if TYPE_CHECKING:
    from mcp.types import Tool as MCPTool

Operation: TypeAlias = Literal["create", "update", "delete"]  # noqa: UP040 - `type` keyword causes cyclic definition with `from __future__ import annotations`

_TRACKED_RESOURCES_KEY = "_tracked_resources"
_WRITE_PREFIXES = ("create_", "update_", "delete_", "patch_")
_READ_PREFIXES = ("get_", "list_")

_OPERATION_MAP: dict[str, Operation] = {
    "create_": "create",
    "update_": "update",
    "patch_": "update",
    "delete_": "delete",
}

# Tools that don't follow the standard prefix convention
_TOOL_OVERRIDES: dict[str, tuple[str, Operation]] = {
    "prune_schema_fields": ("schema", "update"),
    "create_queue_from_template": ("queue", "create"),
    "create_hook_from_template": ("hook", "create"),
}


def extract_entity_type(tool_name: str) -> str | None:
    """Extract entity type from tool name (e.g., 'update_queue' -> 'queue')."""
    if tool_name in _TOOL_OVERRIDES:
        return _TOOL_OVERRIDES[tool_name][0]
    for prefix in (*_WRITE_PREFIXES, *_READ_PREFIXES):
        if tool_name.startswith(prefix):
            return tool_name[len(prefix) :]
    return None


def extract_entity_id(entity_type: str, arguments: dict[str, Any]) -> str | None:
    """Extract entity ID from tool arguments (e.g., queue_id from update_queue args)."""
    id_key = f"{entity_type}_id"
    entity_id = arguments.get(id_key)
    if entity_id is not None:
        return str(entity_id)
    if "id" in arguments:
        return str(arguments["id"])
    return None


def to_dict(obj: Any) -> dict | None:
    """Convert MCP result to a plain dict. Handles Pydantic models, dataclasses, and dicts."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    return None


def unwrap(data: dict) -> dict:
    """Unwrap FastMCP's {"result": ...} wrapper if present."""
    inner = data.get("result")
    return inner if isinstance(inner, dict) else data


def extract_entity_name(data: dict | None) -> str:
    """Extract a human-readable name from entity data, unwrapping FastMCP wrapper."""
    if data is None:
        return ""
    source = unwrap(data)
    for key in ("name", "label", "title", "subject"):
        if source.get(key):
            return str(source[key])
    return ""


def classify_operation(tool_name: str) -> Operation:
    """Classify the operation type from tool name."""
    if tool_name in _TOOL_OVERRIDES:
        return _TOOL_OVERRIDES[tool_name][1]
    for prefix, operation in _OPERATION_MAP.items():
        if tool_name.startswith(prefix):
            return operation
    return "update"


def _pop_tracked_resources(result: Any) -> list[dict[str, Any]]:
    """Extract and remove _tracked_resources from a dict result.

    Returns the list of tracked resource entries, or an empty list if the
    result is not a dict or has no tracked resources.
    """
    if isinstance(result, dict):
        return result.pop(_TRACKED_RESOURCES_KEY, [])
    return []


def mcp_tools_to_anthropic_format(mcp_tools: list[MCPTool]) -> list[ToolParam]:
    """Convert MCP tools to Anthropic tool format."""
    return [
        ToolParam(name=mcp_tool.name, description=mcp_tool.description or "", input_schema=mcp_tool.inputSchema)
        for mcp_tool in mcp_tools
    ]
