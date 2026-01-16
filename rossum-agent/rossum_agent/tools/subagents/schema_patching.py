"""Schema patching sub-agent for the Rossum Agent.

This module provides a sub-agent for safely updating document schemas by replacing
the entire content in a single API call (PUT) rather than field-by-field patching.
"""

from __future__ import annotations

import asyncio
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
    get_mcp_connection,
    get_mcp_event_loop,
    get_output_dir,
    report_progress,
)
from rossum_agent.tools.subagents.knowledge_base import OPUS_MODEL_ID

logger = logging.getLogger(__name__)

_SCHEMA_PATCHING_SYSTEM_PROMPT = """Goal: Update schema to match EXACTLY the requested changes—nothing more.

## Constraints

- Only add/remove/modify fields explicitly requested
- Never add fields you think might be useful
- Never add optional properties unless specified (no default rir_field_names, no default constraints)
- Preserve all existing fields not mentioned in the request

## Workflow

1. get_schema → inspect current structure
2. Apply ONLY requested changes to content array
3. update_schema_content with modified content (one call)

## Field Structure

| Property | Required | Notes |
|----------|----------|-------|
| category | Yes | "datapoint" |
| id | Yes | Unique identifier |
| label | Yes | Display name |
| type | Yes | string, number, date, enum |

Optional properties—include ONLY if explicitly requested:
- rir_field_names, constraints, default_value, hidden, can_export, format, options, ui_configuration

## Field Types

| Type | Schema |
|------|--------|
| String | `"type": "string"` |
| Multiline | `"type": "string", "ui_configuration": {"type": "captured-multiline"}` |
| Number | `"type": "number"` |
| Integer | `"type": "number", "format": "#"` |
| Date | `"type": "date"` |
| Enum | `"type": "enum", "options": [{"value": "v", "label": "L"}]` |

## Section/Table Structure

Section: `{"category": "section", "id": "...", "label": "...", "children": [...]}`
Table: `{"category": "multivalue", ..., "children": {"category": "tuple", "children": [...]}}`

Return: list of changes made (added/removed/modified)."""

_GET_SCHEMA_TOOL: dict[str, Any] = {
    "name": "get_schema",
    "description": "Fetch schema by ID. Returns full structure with sections and datapoints.",
    "input_schema": {
        "type": "object",
        "properties": {"schema_id": {"type": "integer", "description": "Schema ID"}},
        "required": ["schema_id"],
    },
}

_UPDATE_SCHEMA_CONTENT_TOOL: dict[str, Any] = {
    "name": "update_schema_content",
    "description": "Replace entire schema content in one API call. Much more efficient than patching field by field.",
    "input_schema": {
        "type": "object",
        "properties": {
            "schema_id": {"type": "integer", "description": "Schema ID"},
            "content": {
                "type": "array",
                "description": "Complete new content array (list of sections with children)",
                "items": {"type": "object"},
            },
        },
        "required": ["schema_id", "content"],
    },
}

_OPUS_TOOLS: list[dict[str, Any]] = [_GET_SCHEMA_TOOL, _UPDATE_SCHEMA_CONTENT_TOOL]


def _call_mcp_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Call an MCP tool synchronously from within a thread."""
    mcp_connection = get_mcp_connection()
    mcp_event_loop = get_mcp_event_loop()
    if mcp_connection is None or mcp_event_loop is None:
        raise RuntimeError("MCP connection not set. Call set_mcp_connection first.")

    future = asyncio.run_coroutine_threadsafe(mcp_connection.call_tool(name, arguments), mcp_event_loop)
    return future.result(timeout=60)


def _save_patching_context(iteration: int, max_iterations: int, messages: list[dict[str, Any]]) -> None:
    """Save agent input context to file for debugging."""
    try:
        output_dir = get_output_dir()
        context_file = output_dir / f"patch_schema_context_iter_{iteration}.json"
        context_data = {
            "iteration": iteration,
            "max_iterations": max_iterations,
            "model": OPUS_MODEL_ID,
            "max_tokens": 8192,
            "system_prompt": _SCHEMA_PATCHING_SYSTEM_PROMPT,
            "messages": messages,
            "tools": _OPUS_TOOLS,
        }
        context_file.write_text(json.dumps(context_data, indent=2, default=str))
        logger.info(f"patch_schema sub-agent: saved context to {context_file}")
    except Exception as e:
        logger.warning(f"Failed to save patch_schema context: {e}")


def _execute_opus_tool(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Execute a tool for the Opus sub-agent."""
    if tool_name == "get_schema":
        mcp_result = _call_mcp_tool("get_schema", tool_input)
        return json.dumps(mcp_result, indent=2, default=str) if mcp_result else "No data returned"
    if tool_name == "update_schema_content":
        schema_id = tool_input["schema_id"]
        content = tool_input["content"]
        mcp_result = _call_mcp_tool("update_schema", {"schema_id": schema_id, "schema_data": {"content": content}})
        return json.dumps(mcp_result, indent=2, default=str) if mcp_result else "No data returned"
    return f"Unknown tool: {tool_name}"


def _call_opus_for_patching(schema_id: str, changes: list[dict[str, Any]]) -> str:
    """Call Opus model for schema patching with tool use."""
    try:
        client = create_bedrock_client()

        changes_text = "\n".join(
            f"- {c.get('action', 'add')} field '{c.get('id')}' ({c.get('type', 'string')}) "
            f"in section '{c.get('parent_section')}'"
            + (f" with label '{c.get('label')}'" if c.get("label") else "")
            + (" [TABLE COLUMN]" if c.get("table_field") else "")
            for c in changes
        )

        user_content = f"""Update schema {schema_id} to have EXACTLY these fields:

{changes_text}

Workflow:
1. get_schema to see current structure
2. Build new content array with exactly the requested fields
3. update_schema_content with complete new content (one call replaces everything)
4. Report what was added/removed"""

        messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]

        max_iterations = 10
        response = None
        for iteration in range(max_iterations):
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

            response = client.messages.create(
                model=OPUS_MODEL_ID,
                max_tokens=8192,
                system=_SCHEMA_PATCHING_SYSTEM_PROMPT,
                messages=messages,
                tools=_OPUS_TOOLS,
            )

            has_tool_use = any(hasattr(block, "type") and block.type == "tool_use" for block in response.content)

            if response.stop_reason == "end_of_turn" or not has_tool_use:
                logger.info(
                    f"patch_schema sub-agent: completed after {iteration + 1} iterations "
                    f"(stop_reason={response.stop_reason})"
                )
                report_progress(
                    SubAgentProgress(
                        tool_name="patch_schema",
                        iteration=iteration + 1,
                        max_iterations=max_iterations,
                        status="completed",
                    )
                )
                text_parts = [block.text for block in response.content if hasattr(block, "text")]
                return "\n".join(text_parts) if text_parts else "No analysis provided"

            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results: list[dict[str, Any]] = []
            iteration_tool_calls: list[str] = []

            for block in response.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    iteration_tool_calls.append(tool_name)
                    logger.info(
                        f"patch_schema sub-agent [iter {iteration + 1}/{max_iterations}]: calling '{tool_name}'"
                    )

                    report_progress(
                        SubAgentProgress(
                            tool_name="patch_schema",
                            iteration=iteration + 1,
                            max_iterations=max_iterations,
                            current_tool=tool_name,
                            tool_calls=iteration_tool_calls.copy(),
                            status="running_tool",
                        )
                    )

                    try:
                        result = _execute_opus_tool(tool_name, tool_input)
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

        text_parts = [block.text for block in response.content if hasattr(block, "text")] if response else []
        return "\n".join(text_parts) if text_parts else "Max iterations reached without final response"

    except Exception as e:
        logger.exception("Error calling Opus for schema patching")
        return f"Error calling Opus sub-agent: {e}"


@beta_tool
def patch_schema_with_subagent(
    schema_id: str,
    changes: str,
) -> str:
    """Update a Rossum schema using an Opus sub-agent with efficient bulk replacement.

    Delegates schema update to a sub-agent that:
    1. Fetches current schema structure
    2. Builds new content array with all changes
    3. Replaces entire content in ONE API call (not field-by-field)
    4. Returns summary of changes made

    Args:
        schema_id: The schema ID to update.
        changes: JSON array of field specifications. Each object should have:
            - action: "add" or "remove" (default: "add")
            - id: Field ID
            - parent_section: Section ID for the field
            - type: Field type (string, number, date, enum)
            - label: Field label (optional, defaults to id)
            - table_field: true if this is a table column (optional)
            - Additional properties like options, is_formula, formula, etc.

    Returns:
        JSON with update results including fields added, removed, and final state.
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

    logger.info(f"patch_schema: Calling Opus sub-agent for schema_id={schema_id}, {len(changes_list)} changes")
    analysis = _call_opus_for_patching(schema_id, changes_list)

    response = {
        "schema_id": schema_id,
        "changes_requested": len(changes_list),
        "analysis": analysis,
        "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
    }

    return json.dumps(response, ensure_ascii=False, default=str)
