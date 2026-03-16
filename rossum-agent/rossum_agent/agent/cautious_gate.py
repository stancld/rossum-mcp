"""Cautious persona write gating for the Rossum agent.

When the agent runs in "cautious" persona mode, all write operations are blocked until the user explicitly confirms them.
For update operations on identifiable entities, a field-level diff is shown instead of raw arguments.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from rossum_agent.agent.models import ToolCall, ToolResult
from rossum_agent.api.models.schemas import Persona
from rossum_agent.rossum_mcp_integration import classify_operation, extract_entity_id, extract_entity_type
from rossum_agent.tools import INTERNAL_WRITE_TOOL_NAMES
from rossum_agent.tools.core import (
    CAUTIOUS_APPROVAL_LABEL,
    CAUTIOUS_CONFIRMATION_MARKER,
    AgentContext,
    AgentQuestion,
    AgentQuestionItem,
    QuestionOption,
)
from rossum_agent.tools.dynamic_tools import is_mcp_write_tool
from rossum_agent.utils import compute_json_diff

if TYPE_CHECKING:
    from rossum_agent.rossum_mcp_integration import MCPConnection

logger = logging.getLogger(__name__)


def is_write_tool(name: str) -> bool:
    """Check if a tool is a write operation (MCP or internal)."""
    return name in INTERNAL_WRITE_TOOL_NAMES or is_mcp_write_tool(name)


async def check_cautious_write_gate(
    tool_call: ToolCall, agent_ctx: AgentContext, mcp_connection: MCPConnection
) -> ToolResult | None:
    """Gate write tools behind user confirmation for cautious persona.

    For update/patch operations, fetches the existing object and shows a field-level diff instead of raw arguments.

    Returns a ToolResult (blocking the tool) if confirmation is needed, or None if the tool should proceed.
    """
    if agent_ctx.persona != Persona.CAUTIOUS:
        return None
    if not is_write_tool(tool_call.name):
        return None
    if tool_call.name in agent_ctx.cautious_preapproved_writes:
        agent_ctx.cautious_preapproved_writes.discard(tool_call.name)
        logger.info(f"Cautious persona: allowing pre-approved write tool {tool_call.name}")
        return None

    # Block the tool and ask the user for confirmation
    agent_ctx.cautious_blocked_writes.add(tool_call.name)

    change_preview = await build_change_preview(tool_call, mcp_connection)
    agent_ctx.report_question(
        AgentQuestion(
            questions=[
                AgentQuestionItem(
                    question=(
                        f"The agent wants to execute write operation **{tool_call.name}**\n\n"
                        f"{change_preview}\n\n"
                        "Do you want to proceed?"
                    ),
                    options=[
                        QuestionOption(value="yes", label=CAUTIOUS_APPROVAL_LABEL),
                        QuestionOption(value="no", label="No, cancel"),
                        QuestionOption(value="chat", label="Let me provide context"),
                    ],
                )
            ]
        )
    )

    logger.info(f"Cautious persona: blocked write tool {tool_call.name}, asking user for confirmation")
    return ToolResult(
        tool_call_id=tool_call.id,
        name=tool_call.name,
        content=(
            f"Write operation `{tool_call.name}` {CAUTIOUS_CONFIRMATION_MARKER} (cautious persona). "
            "Waiting for user response. STOP — do not call other tools or produce text in the same turn."
        ),
        is_error=True,
    )


async def build_change_preview(tool_call: ToolCall, mcp_connection: MCPConnection) -> str:
    """Build a human-readable change preview for a write tool call.

    For MCP update/patch operations, fetches the existing entity and shows
    a field-level diff. Falls back to raw arguments for other operations.
    """
    args = tool_call.arguments
    entity_type = extract_entity_type(tool_call.name)
    entity_id = extract_entity_id(entity_type or "", args) if entity_type else None
    operation = classify_operation(tool_call.name)

    # Only fetch existing object for update operations on identifiable entities
    if operation == "update" and entity_type and entity_id and mcp_connection:
        existing = await mcp_connection.fetch_snapshot(entity_type, entity_id)
        if existing is not None:
            # Populate read cache so _get_before_snapshot doesn't re-fetch on approval
            mcp_connection._cache_set(entity_type, entity_id, existing)
            return format_field_diff(existing, args, entity_type, entity_id)

    # Fallback: raw arguments
    args_json = json.dumps(args, indent=2, ensure_ascii=False)
    return f"**Arguments:**\n```json\n{args_json}\n```"


def extract_update_fields(arguments: dict, entity_type: str) -> dict:
    """Extract the fields being changed from tool arguments.

    Handles both flat args (update_hook: hook_id, name, active, ...) and
    nested data objects (update_queue: queue_id, queue_data={...}).
    """
    id_key = f"{entity_type}_id"
    update_fields: dict = {}

    for key, value in arguments.items():
        if key in (id_key, "id"):
            continue
        if value is None:
            continue
        # Nested data object (e.g. queue_data, engine_data) — flatten it
        if isinstance(value, dict) and key.endswith("_data"):
            update_fields.update(value)
        else:
            update_fields[key] = value

    return update_fields


def format_field_diff(existing: dict, arguments: dict, entity_type: str, entity_id: str) -> str:
    """Format a unified diff between existing object and proposed changes."""
    update_fields = extract_update_fields(arguments, entity_type)

    if not update_fields:
        args_json = json.dumps(arguments, indent=2, ensure_ascii=False)
        return f"**Arguments:**\n```json\n{args_json}\n```"

    after = {**existing, **update_fields}
    diff_text = compute_json_diff(
        existing, after, fromfile="current", tofile="proposed", ensure_ascii=False, context_lines=2
    )

    if not diff_text:
        return f"**No effective changes to {entity_type} {entity_id}**"

    return f"**Changes to {entity_type} {entity_id}:**\n```diff\n{diff_text}```"
