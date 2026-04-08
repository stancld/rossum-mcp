"""Schema patching sub-agent.

Provides deterministic programmatic schema manipulation. The workflow:
1. Get schema tree structure (lightweight view)
2. Get full schema content
3. LLM instructs which fields to keep/add based on user requirements
4. Programmatic filtering/modification of schema content
5. Single PATCH to update schema via direct API call
"""

from __future__ import annotations

import copy
import json
import logging
import re
import time
from dataclasses import asdict, is_dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

import httpx
from anthropic import beta_tool
from rossum_mcp.tools.update.schemas.patching import _resolve_relative_field_position
from rossum_mcp.tools.validation import sanitize_schema_content

from rossum_agent.tools.core import get_context
from rossum_agent.tools.dynamic_tools import load_tool
from rossum_agent.tools.subagents.base import (
    SubAgent,
    SubAgentConfig,
    SubAgentResult,
)
from rossum_agent.tools.subagents.mcp_helpers import call_mcp_tool

logger = logging.getLogger(__name__)


class SchemaFieldType(StrEnum):
    STRING = "string"
    NUMBER = "number"
    DATE = "date"
    ENUM = "enum"


_ENGINE_RESTRICTION_RE = re.compile(r"extracted field '(\w+)' is not present among names of engine fields")


def _to_plain(obj: Any) -> Any:
    """Recursively convert dataclass/Pydantic objects to plain dicts/lists."""
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_plain(v) for v in obj]
    if isinstance(obj, tuple):
        return [_to_plain(v) for v in obj]
    if hasattr(obj, "model_dump"):
        return _to_plain(obj.model_dump())
    if is_dataclass(obj) and not isinstance(obj, type):
        return _to_plain(asdict(obj))
    return obj


def _unwrap_get_response(obj: Any) -> Any:
    """Unwrap unified get response: {"entity": ..., "id": ..., "data": {...}} or FastMCP {"result": ...}."""
    if isinstance(obj, dict):
        if "data" in obj and "entity" in obj:
            return obj["data"]
        if "result" in obj:
            return obj["result"]
    elif hasattr(obj, "result"):
        return obj.result
    return obj


def _extract_schema_content(mcp_result: Any) -> list[dict[str, Any]]:
    """Extract schema content list from MCP result, handling dict, dataclass, or Pydantic."""
    if mcp_result is None:
        return []

    obj = _unwrap_get_response(mcp_result)

    if isinstance(obj, dict):
        content = obj.get("content", [])
        if isinstance(content, list):
            return _to_plain(content)
        return []
    if hasattr(obj, "content"):
        content = obj.content
        if isinstance(content, list):
            return _to_plain(content)
        return []
    return []


_SCHEMA_PATCHING_SYSTEM_PROMPT = """Goal: Update schema to match EXACTLY the requested fields—programmatically.

## Workflow

Schema tree structure and full content are pre-fetched and provided in the user message.

1. Analyze current vs requested fields
2. Call apply_schema_changes with:
   - fields_to_keep: list of field IDs to retain
   - fields_to_add: list of new field specifications
   - fields_to_update: list of updates to existing fields (e.g., formula changes)
3. Return summary of changes

Use get_schema_tree_structure / get_full_schema only if you need to verify or refresh data.

## Field Specification Format (for fields_to_add)

| Property | Required | Notes |
|----------|----------|-------|
| id | Yes | Unique identifier |
| label | Yes | Display name |
| parent_section | Yes | Section ID to add field to |
| type | Yes | string, number, date, enum |
| table_id | If table | Multivalue ID for table columns |
| after_field | No | Insert after this field ID (within same parent). Without this, fields append to end. |
| before_field | No | Insert before this field ID (within same parent). |

Optional: format, options (for enum), rir_field_names, description, hidden, disable_prediction, can_export, can_collapse, ui_configuration, prompt, context, matching, aggregations, grid, show_grid_by_default

## Constraints

- Field `id` must be valid identifier (lowercase, underscores, no spaces)
- Do NOT set `rir_field_names` unless user explicitly provides engine field names — the API rejects schemas when `rir_field_names` contains values unknown to the engine ("Engine restriction: extracted field '...' is not present among names of engine fields")
- If user mentions extraction/AI capture, check existing schema for rir_field_names patterns first
- `ui_configuration.type` must be one of: captured, data, manual, formula, reasoning, lookup
- `ui_configuration.edit` must be one of: enabled, enabled_without_warning, disabled

## Lookup Fields

Lookup fields require ALL of these attributes — omitting any causes API errors:
- `type`: "enum"
- `ui_configuration`: {"type": "lookup", "edit": "disabled"}
- `matching`: the full matching config object (type, configuration with dataset/queries/placeholders)
- Do NOT set `rir_field_names` on lookup fields

## Type Mappings

| User Request | Schema Config |
|--------------|---------------|
| String | type: "string" |
| Float/Number | type: "number" |
| Integer | type: "number", format: "# ##0" |
| Date | type: "date" |
| Enum | type: "enum", options: [...] |

Not supported: multiline fields. Use regular string type instead.

Return: Summary of fields kept, added, removed."""

_GET_SCHEMA_TREE_STRUCTURE_TOOL: dict[str, Any] = {
    "name": "get_schema_tree_structure",
    "description": "Get lightweight tree view with field IDs, labels, categories, types.",
    "input_schema": {
        "type": "object",
        "properties": {"schema_id": {"type": "integer", "description": "Schema ID"}},
        "required": ["schema_id"],
    },
}

_GET_FULL_SCHEMA_TOOL: dict[str, Any] = {
    "name": "get_full_schema",
    "description": "Get complete schema content for modification.",
    "input_schema": {
        "type": "object",
        "properties": {"schema_id": {"type": "integer", "description": "Schema ID"}},
        "required": ["schema_id"],
    },
}

_APPLY_SCHEMA_CHANGES_TOOL: dict[str, Any] = {
    "name": "apply_schema_changes",
    "description": "Programmatically filter, update, and add fields in schema, then PUT in one call.",
    "input_schema": {
        "type": "object",
        "properties": {
            "schema_id": {"type": "integer", "description": "Schema ID"},
            "fields_to_keep": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Field IDs to retain. Sections always kept. Omit to keep all.",
            },
            "fields_to_add": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "label": {"type": "string"},
                        "parent_section": {"type": "string"},
                        "type": {"type": "string"},
                        "table_id": {"type": "string"},
                        "after_field": {
                            "type": "string",
                            "description": "Insert after this field ID within the same parent section/table",
                        },
                        "before_field": {
                            "type": "string",
                            "description": "Insert before this field ID within the same parent section/table",
                        },
                        "format": {"type": "string"},
                        "options": {"type": "array"},
                        "description": {"type": "string"},
                        "rir_field_names": {"type": "array"},
                        "hidden": {"type": "boolean"},
                        "disable_prediction": {"type": "boolean"},
                        "can_export": {"type": "boolean"},
                        "can_collapse": {"type": "boolean"},
                        "aggregations": {"type": "object"},
                        "grid": {"type": "object"},
                        "show_grid_by_default": {"type": "boolean"},
                        "ui_configuration": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["captured", "data", "manual", "formula", "reasoning", "lookup"],
                                    "description": "Field value source type",
                                },
                                "edit": {
                                    "type": "string",
                                    "enum": ["enabled", "enabled_without_warning", "disabled"],
                                    "description": "Edit behavior in UI",
                                },
                            },
                        },
                        "prompt": {
                            "type": "string",
                            "description": "LLM prompt for reasoning fields (max 2000 chars)",
                        },
                        "context": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Context field IDs for reasoning (TxScript format, e.g. field.invoice_id)",
                        },
                        "matching": {
                            "type": "object",
                            "description": "Lookup field matching config (type + configuration with dataset, queries, placeholders). Required for lookup fields.",
                        },
                    },
                    "required": ["id", "label", "parent_section", "type"],
                },
                "description": "New fields to add to schema.",
            },
            "fields_to_update": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Existing field ID to update"},
                        "formula": {"type": "string", "description": "New formula code"},
                        "label": {"type": "string"},
                        "type": {"type": "string"},
                        "description": {"type": "string"},
                        "hidden": {"type": "boolean"},
                        "disable_prediction": {"type": "boolean"},
                        "can_export": {"type": "boolean"},
                        "can_collapse": {"type": "boolean"},
                        "ui_configuration": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "edit": {"type": "string"},
                            },
                        },
                        "matching": {
                            "type": "object",
                            "description": "Lookup field matching config update.",
                        },
                        "aggregations": {"type": "object"},
                        "grid": {"type": "object"},
                        "show_grid_by_default": {"type": "boolean"},
                    },
                    "required": ["id"],
                },
                "description": "Existing fields to update (e.g., change formula, label, type, description, matching).",
            },
        },
        "required": ["schema_id"],
    },
}

_OPUS_TOOLS: list[dict[str, Any]] = [
    _GET_SCHEMA_TREE_STRUCTURE_TOOL,
    _GET_FULL_SCHEMA_TOOL,
    _APPLY_SCHEMA_CHANGES_TOOL,
]


def _collect_field_ids(content: list[dict[str, Any]]) -> set[str]:
    """Collect all field IDs from schema content recursively."""
    ids: set[str] = set()
    for node in content:
        if node_id := node.get("id"):
            ids.add(node_id)
        if children := node.get("children"):
            if isinstance(children, list):
                ids.update(_collect_field_ids(children))
            elif isinstance(children, dict):
                if child_id := children.get("id"):
                    ids.add(child_id)
                nested = children.get("children")
                if nested and isinstance(nested, list):
                    ids.update(_collect_field_ids(nested))
    return ids


def _coerce_field_type(value: Any) -> SchemaFieldType:
    """Coerce a type value to SchemaFieldType, handling LLM-generated dicts like {"type": "number"}."""
    raw: str
    if isinstance(value, SchemaFieldType):
        return value
    if isinstance(value, str):
        raw = value
    elif isinstance(value, dict) and isinstance(value.get("type"), str):
        raw = value["type"]
    else:
        return SchemaFieldType.STRING
    try:
        return SchemaFieldType(raw)
    except ValueError:
        return SchemaFieldType.STRING


_BOOL_FIELD_KEYS = ("hidden", "can_export", "disable_prediction", "can_collapse", "show_grid_by_default")
_TRUTHY_FIELD_KEYS = (
    "format",
    "ui_configuration",
    "prompt",
    "context",
    "formula",
    "matching",
    "description",
    "aggregations",
    "grid",
)


def _build_field_node(spec: dict[str, Any]) -> dict[str, Any]:
    """Build a schema field node from specification."""
    field_type = _coerce_field_type(spec.get("type", "string"))
    node: dict[str, Any] = {
        "id": spec["id"],
        "label": spec.get("label", spec["id"]),
        "category": "datapoint",
        "type": field_type,
    }

    if field_type == "enum":
        node["options"] = spec.get("options") or []

    is_lookup = isinstance(spec.get("ui_configuration"), dict) and spec["ui_configuration"].get("type") == "lookup"
    if not is_lookup and spec.get("rir_field_names"):
        node["rir_field_names"] = spec["rir_field_names"]

    for key in _BOOL_FIELD_KEYS:
        if spec.get(key) is not None:
            node[key] = spec[key]

    for key in _TRUTHY_FIELD_KEYS:
        if spec.get(key):
            node[key] = spec[key]

    return node


def _filter_content(
    content: list[dict[str, Any]],
    fields_to_keep: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Filter schema content to keep only specified fields. Sections always preserved."""
    filtered: list[dict[str, Any]] = []
    removed: list[str] = []

    for node in content:
        node_id = node.get("id", "")
        category = node.get("category", "")

        if category == "section":
            new_section = copy.deepcopy(node)
            if "children" in new_section and isinstance(new_section["children"], list):
                new_children, section_removed = _filter_content(new_section["children"], fields_to_keep)
                new_section["children"] = new_children
                removed.extend(section_removed)
            filtered.append(new_section)

        elif category == "multivalue":
            new_mv = copy.deepcopy(node)
            mv_children_removed: list[str] = []

            if "children" in new_mv and isinstance(new_mv["children"], dict):
                tuple_node = new_mv["children"]
                if "children" in tuple_node and isinstance(tuple_node["children"], list):
                    tuple_children, mv_children_removed = _filter_content(tuple_node["children"], fields_to_keep)
                    tuple_node["children"] = tuple_children

            has_remaining_children = bool(new_mv.get("children", {}).get("children", []))

            if node_id in fields_to_keep or has_remaining_children:
                filtered.append(new_mv)
                removed.extend(mv_children_removed)
            else:
                removed.append(node_id)
                removed.extend(_collect_field_ids([node]) - {node_id})

        else:
            if node_id in fields_to_keep:
                filtered.append(copy.deepcopy(node))
            elif node_id:
                removed.append(node_id)

    return filtered, removed


def _strip_invalid_rir_fields(content: list[dict[str, Any]], bad_names: set[str]) -> list[str]:
    """Remove rir_field_names entries matching bad_names from all fields in content. Returns list of fixed field IDs."""
    fixed: list[str] = []

    def _walk(nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            rir = node.get("rir_field_names")
            if isinstance(rir, list):
                cleaned = [name for name in rir if name not in bad_names]
                if len(cleaned) != len(rir):
                    fixed.append(node.get("id", "?"))
                    if cleaned:
                        node["rir_field_names"] = cleaned
                    else:
                        del node["rir_field_names"]
            children = node.get("children")
            if isinstance(children, list):
                _walk(children)
            elif isinstance(children, dict):
                _walk([children])

    _walk(content)
    return fixed


def _section_label_from_id(section_id: str) -> str:
    """Derive a human-readable label from a section ID (e.g. 'basic_info_section' → 'Basic Info')."""
    label = section_id.removesuffix("_section").replace("_", " ").strip()
    return label.title() if label else section_id


def _find_or_create_section(
    content: list[dict[str, Any]],
    section_id: str | None,
) -> dict[str, Any] | None:
    """Find existing section by ID, or create it and append to content.

    Returns None if section_id is empty/None.
    """
    if not section_id:
        return None
    for node in content:
        if node.get("category") == "section" and node.get("id") == section_id:
            return node
    section: dict[str, Any] = {
        "category": "section",
        "id": section_id,
        "label": _section_label_from_id(section_id),
        "children": [],
    }
    content.append(section)
    return section


def _insert_field_into_list(
    children: list[dict[str, Any]],
    field_node: dict[str, Any],
    after_field: str | None = None,
    before_field: str | None = None,
) -> None:
    """Insert a field node into a children list, optionally relative to a specific field."""
    position = _resolve_relative_field_position(children, after_field, before_field)
    if position is not None:
        children.insert(position, field_node)
    else:
        children.append(field_node)


def _add_fields_to_content(
    content: list[dict[str, Any]],
    fields_to_add: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Add new fields to schema content. Returns (modified_content, added_ids)."""
    modified = copy.deepcopy(content)
    added: list[str] = []

    for spec in fields_to_add:
        parent_section = spec.get("parent_section")
        table_id = spec.get("table_id")
        after_field = spec.get("after_field")
        before_field = spec.get("before_field")
        field_node = _build_field_node(spec)

        section = _find_or_create_section(modified, parent_section)
        if section is None:
            logger.warning("Skipping field %r: no parent_section specified", spec.get("id"))
            continue

        if table_id:
            for child in section.get("children", []):
                if child.get("category") == "multivalue" and child.get("id") == table_id:
                    tuple_node = child.get("children", {})
                    if isinstance(tuple_node, dict) and "children" in tuple_node:
                        _insert_field_into_list(tuple_node["children"], field_node, after_field, before_field)
                        added.append(spec["id"])
                        break
        else:
            if "children" not in section:
                section["children"] = []
            _insert_field_into_list(section["children"], field_node, after_field, before_field)
            added.append(spec["id"])

    return modified, added


def _update_fields_in_content(
    content: list[dict[str, Any]],
    fields_to_update: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Update existing fields in schema content. Returns (modified_content, updated_ids)."""
    modified = copy.deepcopy(content)
    updated: list[str] = []

    updates_by_id = {spec["id"]: spec for spec in fields_to_update}

    def _apply_spec(target: dict[str, Any], spec: dict[str, Any]) -> None:
        for key, value in spec.items():
            if key == "id":
                continue
            if key == "type":
                value = _coerce_field_type(value)
            target[key] = value

    def _apply_updates(nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            node_id = node.get("id", "")
            if node_id in updates_by_id:
                _apply_spec(node, updates_by_id[node_id])
                updated.append(node_id)

            children = node.get("children")
            if isinstance(children, list):
                _apply_updates(children)
            elif isinstance(children, dict):
                child_id = children.get("id", "")
                if child_id in updates_by_id:
                    _apply_spec(children, updates_by_id[child_id])
                    updated.append(child_id)
                nested = children.get("children")
                if isinstance(nested, list):
                    _apply_updates(nested)

    _apply_updates(modified)
    return modified, updated


def _update_schema_via_api(schema_id: int, content: list[dict[str, Any]]) -> None:
    """Update schema content via direct Rossum API call (no MCP)."""
    ctx = get_context()
    base_url, token = ctx.require_rossum_credentials()
    url = f"{base_url}/schemas/{schema_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    sanitized = sanitize_schema_content(content)
    response = httpx.patch(url, json={"content": sanitized}, headers=headers, timeout=60)
    response.raise_for_status()


def _apply_schema_changes(
    schema_id: int,
    current_content: list[dict[str, Any]],
    fields_to_keep: list[str] | None,
    fields_to_add: list[dict[str, Any]] | None,
    fields_to_update: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Apply changes to schema content and PATCH to API."""
    result: dict[str, Any] = {
        "schema_id": schema_id,
        "fields_removed": [],
        "fields_added": [],
        "fields_updated": [],
        "fields_kept": [],
    }

    modified_content = current_content

    if fields_to_keep is not None:
        keep_set = set(fields_to_keep)
        section_ids = {s.get("id") for s in current_content if s.get("category") == "section" and s.get("id")}
        keep_set.update(sid for sid in section_ids if sid is not None)

        modified_content, removed = _filter_content(modified_content, keep_set)
        result["fields_removed"] = removed

    if fields_to_add:
        modified_content, added = _add_fields_to_content(modified_content, fields_to_add)
        result["fields_added"] = added

    if fields_to_update:
        modified_content, updated = _update_fields_in_content(modified_content, fields_to_update)
        result["fields_updated"] = updated

    try:
        _update_schema_via_api(schema_id, modified_content)
    except Exception as e:
        bad_names = set(_ENGINE_RESTRICTION_RE.findall(str(e)))
        if not bad_names:
            raise
        fixed = _strip_invalid_rir_fields(modified_content, bad_names)
        logger.info(f"Auto-fixed engine restriction: stripped rir_field_names from fields {fixed}")
        _update_schema_via_api(schema_id, modified_content)

    result["fields_kept"] = sorted(_collect_field_ids(modified_content))
    result["update_result"] = "success"

    return result


_schema_content_cache: dict[int, list[dict[str, Any]]] = {}


def _execute_opus_tool(tool_name: str, tool_input: dict[str, Any]) -> str:
    schema_id = tool_input.get("schema_id")

    if tool_name == "get_schema_tree_structure":
        mcp_result = call_mcp_tool("get_schema_tree_structure", tool_input)
        plain_result = _to_plain(mcp_result) if mcp_result else None
        return json.dumps(plain_result, indent=2, default=str) if plain_result else "No data returned"

    if tool_name == "get_full_schema":
        mcp_result = call_mcp_tool("get", {"entity": "schema", "entity_id": schema_id})
        mcp_result = _unwrap_get_response(mcp_result)
        if mcp_result and schema_id:
            content = _extract_schema_content(mcp_result)
            if not content:
                logger.info("get_full_schema: schema %s has empty content", schema_id)
            _schema_content_cache[schema_id] = content
        plain_result = _to_plain(mcp_result) if mcp_result else None
        return json.dumps(plain_result, indent=2, default=str) if plain_result else "No data returned"

    if tool_name == "apply_schema_changes":
        if not schema_id or schema_id not in _schema_content_cache:
            return json.dumps({"error": "Must call get_full_schema first to load content"})

        current_content = _schema_content_cache[schema_id]
        fields_to_keep = tool_input.get("fields_to_keep")
        fields_to_add = tool_input.get("fields_to_add")
        fields_to_update = tool_input.get("fields_to_update")

        result = _apply_schema_changes(schema_id, current_content, fields_to_keep, fields_to_add, fields_to_update)
        del _schema_content_cache[schema_id]
        return json.dumps(result, indent=2, default=str)

    return f"Unknown tool: {tool_name}"


class SchemaPatchingSubAgent(SubAgent):
    """Sub-agent for schema patching with programmatic bulk replacement."""

    def __init__(self) -> None:
        config = SubAgentConfig(
            tool_name="patch_schema",
            system_prompt=_SCHEMA_PATCHING_SYSTEM_PROMPT,
            tools=_OPUS_TOOLS,
            max_iterations=3,
            max_tokens=4096,
        )
        super().__init__(config)

    def execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool call from the LLM."""
        return _execute_opus_tool(tool_name, tool_input)


def _call_opus_for_patching(schema_id: str, changes: list[dict[str, Any]]) -> SubAgentResult:
    """Call Opus model for schema patching with deterministic tool workflow.

    Pre-fetches schema data and injects it into context to skip redundant tool calls.

    Returns:
        SubAgentResult with analysis text and token counts.
    """
    schema_id_int = int(schema_id)

    tree_result = call_mcp_tool("get_schema_tree_structure", {"schema_id": schema_id_int})
    schema_result = _unwrap_get_response(call_mcp_tool("get", {"entity": "schema", "entity_id": schema_id_int}))
    if schema_result:
        content = _extract_schema_content(schema_result)
        if not content:
            logger.info("_call_opus_for_patching: schema %s has empty content", schema_id)
        _schema_content_cache[schema_id_int] = content

    tree_str = json.dumps(_to_plain(tree_result), indent=2, default=str) if tree_result else "No data"
    schema_str = json.dumps(_to_plain(schema_result), indent=2, default=str) if schema_result else "No data"

    changes_text = "\n".join(
        f"- {c.get('action', 'add')} field '{c.get('id')}' ({c.get('type', 'string')})"
        + (f" in section '{c.get('parent_section')}'" if c.get("parent_section") else "")
        + (f" with label '{c.get('label')}'" if c.get("label") else "")
        + (f" description='{c.get('description')}'" if c.get("description") else "")
        + (f" hidden={c.get('hidden')}" if c.get("hidden") is not None else "")
        + (f" [TABLE: {c.get('table_id')}]" if c.get("table_field") or c.get("table_id") else "")
        + (f" formula='{c.get('formula')}'" if c.get("formula") else "")
        + (" [LOOKUP]" if c.get("matching") else "")
        for c in changes
    )

    # Include full JSON specs for update/lookup fields so the sub-agent passes all properties through
    detail_changes = [c for c in changes if c.get("matching") or c.get("action") == "update"]
    detail_section = ""
    if detail_changes:
        detail_json = json.dumps(detail_changes, indent=2, ensure_ascii=False)
        detail_section = f"""

## Full Change Specs (apply ALL field properties as specified below)

```json
{detail_json}
```
"""
        lookup_changes = [c for c in detail_changes if c.get("matching")]
        if lookup_changes:
            detail_section += """
Lookup fields MUST include: type "enum", ui_configuration {"type": "lookup", "edit": "disabled"}, and the matching object exactly as shown."""

    actions = {c.get("action", "add") for c in changes}
    if actions == {"update"}:
        intro = f"Update the following fields in schema {schema_id} (keep all other fields unchanged):"
    else:
        intro = f"Update schema {schema_id} to have EXACTLY these fields:"

    user_content = f"""{intro}

{changes_text}{detail_section}

## Current Schema Tree
{tree_str}

## Full Schema Content
{schema_str}

Call apply_schema_changes with fields_to_keep (IDs to retain), fields_to_add, and/or fields_to_update, then return summary."""

    try:
        sub_agent = SchemaPatchingSubAgent()
        return sub_agent.run(user_content)
    finally:
        # Ensure cache is cleaned up even if the sub-agent fails or skips apply_schema_changes
        _schema_content_cache.pop(schema_id_int, None)


_SCHEMA_SKILL_MCP_TOOLS = ["patch_schema", "get_schema_tree_structure", "prune_schema_fields"]


@beta_tool
def patch_schema_with_subagent(schema_id: str, changes: str) -> str:
    """Update a Rossum schema using an Opus sub-agent with programmatic bulk replacement.

    Delegates schema update to a sub-agent that:
    1. Fetches schema tree structure (lightweight view)
    2. Fetches full schema content
    3. Programmatically filters to keep only required fields
    4. Adds new fields as specified
    5. PUTs entire content in ONE API call

    Args:
        schema_id: The schema ID to update.
        changes: JSON array of field specifications. Each object should have:
            - action: "add", "update", or "remove" (default: "add")
            - id: Field ID
            - parent_section: Section ID for the field (required for "add")
            - type: Field type (string, number, date, enum)
            - label: Field label (optional, defaults to id)
            - description: Field description text
            - hidden: Whether the field is hidden (boolean)
            - table_id: Multivalue ID if this is a table column
            - formula: TxScript formula code (for formula fields)

    Returns:
        JSON with update results including fields added, removed, and summary.
    """
    start_time = time.perf_counter()

    if not schema_id:
        return json.dumps(
            {"error": "No schema_id provided", "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3)}
        )

    try:
        changes_list = json.loads(changes)
    except json.JSONDecodeError as e:
        return json.dumps(
            {"error": f"Invalid changes JSON: {e}", "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3)}
        )

    if not changes_list:
        return json.dumps(
            {"error": "No changes provided", "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3)}
        )

    # Auto-load schema MCP tools so the main agent can call patch_schema directly for follow-ups
    load_tool(_SCHEMA_SKILL_MCP_TOOLS)

    logger.info(f"patch_schema: Calling Opus for schema_id={schema_id}, {len(changes_list)} changes")
    result = _call_opus_for_patching(schema_id, changes_list)
    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)

    logger.info(
        f"patch_schema: completed in {elapsed_ms:.1f}ms, "
        f"tokens in={result.input_tokens} out={result.output_tokens}, "
        f"iterations={result.iterations_used}"
    )

    return json.dumps(
        {
            "schema_id": schema_id,
            "changes_requested": len(changes_list),
            "analysis": result.analysis,
            "elapsed_ms": elapsed_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        },
        ensure_ascii=False,
        default=str,
    )
