"""Custom check to verify queue was scheduled for deletion."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rossum_api import SyncRossumAPIClient
from rossum_api.dtos import Token

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep, ToolCall, ToolResult

    type Passed = bool
    type Reasoning = str
    type CustomCheckResult = tuple[Passed, Reasoning]


def _extract_queue_id_from_tool_call(tool_call: ToolCall, tool_results: list[ToolResult]) -> int | None:
    """Extract queue_id from a single tool call."""
    if tool_call.name == "delete_queue":
        args = tool_call.arguments
        if isinstance(args, dict) and "queue_id" in args:
            return args["queue_id"]

    if tool_call.name == "create_queue_from_template":
        for result in tool_results:
            if result.tool_call_id == tool_call.id and isinstance(result.content, str):
                match = re.search(r'"id":\s*(\d+)', result.content)
                if match:
                    return int(match.group(1))

    return None


def _find_queue_id(steps: list[AgentStep]) -> int | None:
    """Find queue_id from agent steps by checking tool calls."""
    for step in steps:
        if not step.tool_calls:
            continue
        for tool_call in step.tool_calls:
            queue_id = _extract_queue_id_from_tool_call(tool_call, step.tool_results)
            if queue_id is not None:
                return queue_id
    return None


def check_queue_deleted(steps: list[AgentStep], api_base_url: str, api_token: str) -> CustomCheckResult:
    """Verify that a queue was scheduled for deletion."""
    queue_id = _find_queue_id(steps)
    if not queue_id:
        return False, "Could not find queue_id in agent steps"

    try:
        client = SyncRossumAPIClient(base_url=api_base_url, credentials=Token(api_token))
        queue = client.retrieve_queue(queue_id)
        if queue.delete_after:
            return True, f"Queue {queue_id} is scheduled for deletion (delete_after={queue.delete_after})"
        return False, f"Queue {queue_id} exists but delete_after is not set"
    except Exception as e:
        if "404" in str(e) or "Not Found" in str(e):
            return True, f"Queue {queue_id} was deleted (404 returned)"
        return False, f"Error checking queue {queue_id}: {e}"
