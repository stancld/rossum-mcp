"""Schema patching sub-agent for the Rossum Agent.

This module provides an Opus-driven sub-agent that uses deterministic programmatic
schema manipulation. The workflow:
1. Get schema tree structure (lightweight view)
2. Get full schema content
3. Opus instructs which fields to keep/add based on user requirements
4. Programmatic filtering/modification of schema content
5. Single PUT to update schema
"""

from __future__ import annotations

import copy
import json
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from anthropic import beta_tool

from rossum_agent.bedrock_client import create_bedrock_client
from rossum_agent.tools.core import (
    SubAgentProgress,
    SubAgentTokenUsage,
    get_output_dir,
    report_progress,
    report_token_usage,
)
from rossum_agent.tools.subagents.knowledge_base import OPUS_MODEL_ID
from rossum_agent.tools.subagents.mcp_helpers import call_mcp_tool

logger = logging.getLogger(__name__)

_SCHEMA_PATCHING_SYSTEM_PROMPT = """Goal: Update schema to match EXACTLY the requested fields—programmatically.

## Workflow

1. get_schema_tree_structure → see current field IDs
2. get_full_schema → get complete schema con
3. Analyze current vs requested fields
4. Call apply_schema_changes with:
   - fields_to_keep: list of field IDs to retain
   - fields_to_add: list of new field specifications
5. Return summary of changes

## Field Specification Format (for fields_to_add)

| Property | Required | Notes |
|----------|----------|-------|
| id | Yes | Unique identifier |
| label | Yes | Display name |
| parent_section | Yes | Section ID to add field to |
| type | Yes | string, number, date, enum |
| table_id | If table | Multivalue ID for table columns |

Optional: multiline, format, options (for enum), rir_field_names, hidden, can_export

## Type Mappings

| User Request | Schema Config |
|--------------|---------------|
| String | type: "string" |
| Multiline | type: "string", multiline: true |
| Float/Number | type: "number" |
| Integer | type: "number", format: "#" |
| Date | type: "date" |
| Enum | type: "enum", options: [...] |

Return: Summary of fields kept, added, removed."""

_GET_SCHEMA_TREE_STRUCTURE_TOOL: dict[str, Any] = {
    "name": "get_schema_tree_structure",
    "description": "Get lightweight tree view with field IDs, labels, categories, types. Call first.",
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
    "description": "Programmatically filter schema and add new fields, then PUT in one call.",
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
                        "multiline": {"type": "boolean"},
                        "format": {"type": "string"},
                        "options": {"type": "array"},
                        "rir_field_names": {"type": "array"},
                        "hidden": {"type": "boolean"},
                        "can_export": {"type": "boolean"},
                    },
                    "required": ["id", "label", "parent_section", "type"],
                },
                "description": "New fields to add to schema.",
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


def _build_field_node(spec: dict[str, Any]) -> dict[str, Any]:
    """Build a schema field node from specification."""
    field_type = spec.get("type", "string")
    node: dict[str, Any] = {
        "id": spec["id"],
        "label": spec.get("label", spec["id"]),
        "category": "datapoint",
        "type": field_type,
    }

    if field_type == "enum" and spec.get("options"):
        node["options"] = spec["options"]

    if spec.get("multiline"):
        node["ui_configuration"] = {"type": "captured-multiline"}

    if spec.get("format"):
        node["format"] = spec["format"]

    if spec.get("rir_field_names"):
        node["rir_field_names"] = spec["rir_field_names"]

    if spec.get("hidden") is not None:
        node["hidden"] = spec["hidden"]

    if spec.get("can_export") is not None:
        node["can_export"] = spec["can_export"]

    return node


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
        field_node = _build_field_node(spec)

        for section in modified:
            if section.get("category") != "section" or section.get("id") != parent_section:
                continue

            if table_id:
                for child in section.get("children", []):
                    if child.get("category") == "multivalue" and child.get("id") == table_id:
                        tuple_node = child.get("children", {})
                        if isinstance(tuple_node, dict) and "children" in tuple_node:
                            tuple_node["children"].append(field_node)
                            added.append(spec["id"])
                            break
            else:
                if "children" not in section:
                    section["children"] = []
                section["children"].append(field_node)
                added.append(spec["id"])
            break

    return modified, added


def _apply_schema_changes(
    schema_id: int,
    current_content: list[dict[str, Any]],
    fields_to_keep: list[str] | None,
    fields_to_add: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Apply changes to schema content and PUT to API."""
    result: dict[str, Any] = {
        "schema_id": schema_id,
        "fields_removed": [],
        "fields_added": [],
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

    mcp_result = call_mcp_tool("update_schema", {"schema_id": schema_id, "schema_data": {"content": modified_content}})
    result["fields_kept"] = sorted(_collect_field_ids(modified_content))
    result["update_result"] = "success" if mcp_result else "failed"

    return result


_schema_content_cache: dict[int, list[dict[str, Any]]] = {}


def _execute_opus_tool(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Execute a tool for the Opus sub-agent."""
    schema_id = tool_input.get("schema_id")

    if tool_name == "get_schema_tree_structure":
        mcp_result = call_mcp_tool("get_schema_tree_structure", tool_input)
        return json.dumps(mcp_result, indent=2, default=str) if mcp_result else "No data returned"

    if tool_name == "get_full_schema":
        mcp_result = call_mcp_tool("get_schema", tool_input)
        if mcp_result and schema_id:
            content = mcp_result.get("content", []) if isinstance(mcp_result, dict) else []
            _schema_content_cache[schema_id] = content
        return json.dumps(mcp_result, indent=2, default=str) if mcp_result else "No data returned"

    if tool_name == "apply_schema_changes":
        if not schema_id or schema_id not in _schema_content_cache:
            return json.dumps({"error": "Must call get_full_schema first to load content"})

        current_content = _schema_content_cache[schema_id]
        fields_to_keep = tool_input.get("fields_to_keep")
        fields_to_add = tool_input.get("fields_to_add")

        result = _apply_schema_changes(schema_id, current_content, fields_to_keep, fields_to_add)
        del _schema_content_cache[schema_id]
        return json.dumps(result, indent=2, default=str)

    return f"Unknown tool: {tool_name}"


def _save_patching_context(iteration: int, max_iterations: int, messages: list[dict[str, Any]]) -> None:
    """Save agent input context to file for debugging."""
    try:
        output_dir = get_output_dir()
        context_file = output_dir / f"patch_schema_context_iter_{iteration}.json"
        context_data = {
            "iteration": iteration,
            "max_iterations": max_iterations,
            "model": OPUS_MODEL_ID,
            "max_tokens": 4096,
            "system_prompt": _SCHEMA_PATCHING_SYSTEM_PROMPT,
            "messages": messages,
            "tools": _OPUS_TOOLS,
        }
        context_file.write_text(json.dumps(context_data, indent=2, default=str))
        logger.info(f"patch_schema sub-agent: saved context to {context_file}")
    except Exception as e:
        logger.warning(f"Failed to save patch_schema context: {e}")


def _call_opus_for_patching(schema_id: str, changes: list[dict[str, Any]]) -> tuple[str, int, int]:
    """Call Opus model for schema patching with deterministic tool workflow."""
    total_input_tokens = 0
    total_output_tokens = 0

    try:
        client_start = time.perf_counter()
        client = create_bedrock_client()
        logger.info(f"patch_schema: Bedrock client created in {(time.perf_counter() - client_start) * 1000:.1f}ms")

        changes_text = "\n".join(
            f"- {c.get('action', 'add')} field '{c.get('id')}' ({c.get('type', 'string')}) "
            f"in section '{c.get('parent_section')}'"
            + (f" with label '{c.get('label')}'" if c.get("label") else "")
            + (f" [TABLE: {c.get('table_id')}]" if c.get("table_field") or c.get("table_id") else "")
            for c in changes
        )

        user_content = f"""Update schema {schema_id} to have EXACTLY these fields:

{changes_text}

Workflow:
1. get_schema_tree_structure to see current field IDs
2. get_full_schema to load content
3. apply_schema_changes with fields_to_keep (IDs to retain) and/or fields_to_add
4. Return summary"""

        messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]

        max_iterations = 5
        response = None
        for iteration in range(max_iterations):
            iter_start = time.perf_counter()
            logger.info(f"patch_schema sub-agent: iteration {iteration + 1}/{max_iterations}")

            report_progress(
                SubAgentProgress(
                    tool_name="patch_schema",
                    iteration=iteration + 1,
                    max_iterations=max_iterations,
                    status="thinking",
                )
            )

            _save_patching_context(iteration + 1, max_iterations, messages)

            llm_start = time.perf_counter()
            response = client.messages.create(
                model=OPUS_MODEL_ID,
                max_tokens=4096,
                system=_SCHEMA_PATCHING_SYSTEM_PROMPT,
                messages=messages,
                tools=_OPUS_TOOLS,
            )
            llm_elapsed_ms = (time.perf_counter() - llm_start) * 1000

            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens

            logger.info(
                f"patch_schema [iter {iteration + 1}]: LLM {llm_elapsed_ms:.1f}ms, "
                f"tokens in={input_tokens} out={output_tokens}"
            )

            report_token_usage(
                SubAgentTokenUsage(
                    tool_name="patch_schema",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    iteration=iteration + 1,
                )
            )

            has_tool_use = any(hasattr(block, "type") and block.type == "tool_use" for block in response.content)

            if response.stop_reason == "end_of_turn" or not has_tool_use:
                iter_elapsed_ms = (time.perf_counter() - iter_start) * 1000
                logger.info(f"patch_schema: completed after {iteration + 1} iterations in {iter_elapsed_ms:.1f}ms")
                report_progress(
                    SubAgentProgress(
                        tool_name="patch_schema",
                        iteration=iteration + 1,
                        max_iterations=max_iterations,
                        status="completed",
                    )
                )
                text_parts = [block.text for block in response.content if hasattr(block, "text")]
                return (
                    "\n".join(text_parts) if text_parts else "No analysis provided",
                    total_input_tokens,
                    total_output_tokens,
                )

            messages.append({"role": "assistant", "content": response.content})

            tool_results: list[dict[str, Any]] = []
            for block in response.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    logger.info(f"patch_schema [iter {iteration + 1}]: calling '{tool_name}'")

                    report_progress(
                        SubAgentProgress(
                            tool_name="patch_schema",
                            iteration=iteration + 1,
                            max_iterations=max_iterations,
                            current_tool=tool_name,
                            status="running_tool",
                        )
                    )

                    try:
                        tool_start = time.perf_counter()
                        result = _execute_opus_tool(tool_name, tool_input)
                        tool_elapsed_ms = (time.perf_counter() - tool_start) * 1000
                        logger.info(f"patch_schema: tool '{tool_name}' executed in {tool_elapsed_ms:.1f}ms")
                        tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
                    except Exception as e:
                        logger.warning(f"Tool {tool_name} failed: {e}")
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": f"Error: {e}",
                                "is_error": True,
                            }
                        )

            if tool_results:
                messages.append({"role": "user", "content": tool_results})

        logger.warning(f"patch_schema: max iterations ({max_iterations}) reached")
        text_parts = [block.text for block in response.content if hasattr(block, "text")] if response else []
        return (
            "\n".join(text_parts) if text_parts else "Max iterations reached",
            total_input_tokens,
            total_output_tokens,
        )

    except Exception as e:
        logger.exception("Error calling Opus for schema patching")
        return f"Error calling Opus sub-agent: {e}", total_input_tokens, total_output_tokens


@beta_tool
def patch_schema_with_subagent(
    schema_id: str,
    changes: str,
) -> str:
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
            - action: "add" or "remove" (default: "add")
            - id: Field ID
            - parent_section: Section ID for the field
            - type: Field type (string, number, date, enum)
            - label: Field label (optional, defaults to id)
            - table_id: Multivalue ID if this is a table column
            - multiline: true for multiline string fields

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

    logger.info(f"patch_schema: Calling Opus for schema_id={schema_id}, {len(changes_list)} changes")
    analysis, input_tokens, output_tokens = _call_opus_for_patching(schema_id, changes_list)
    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)

    logger.info(f"patch_schema: completed in {elapsed_ms:.1f}ms, tokens in={input_tokens} out={output_tokens}")

    return json.dumps(
        {
            "schema_id": schema_id,
            "changes_requested": len(changes_list),
            "analysis": analysis,
            "elapsed_ms": elapsed_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
        ensure_ascii=False,
        default=str,
    )
