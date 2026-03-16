from __future__ import annotations

import difflib
import json
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

# Compact JSON separators for token-efficient serialization
COMPACT_JSON_SEPARATORS: tuple[str, str] = (",", ":")


def compute_json_diff(
    before: dict | list | Any,
    after: dict | list | Any,
    *,
    fromfile: str = "before",
    tofile: str = "after",
    sort_keys: bool = False,
    ensure_ascii: bool = True,
    context_lines: int = 3,
) -> str:
    """Compute a unified diff between two JSON-serializable dicts."""
    before_lines = json.dumps(before, indent=2, sort_keys=sort_keys, ensure_ascii=ensure_ascii).splitlines(
        keepends=True
    )
    after_lines = json.dumps(after, indent=2, sort_keys=sort_keys, ensure_ascii=ensure_ascii).splitlines(keepends=True)
    diff = list(difflib.unified_diff(before_lines, after_lines, fromfile=fromfile, tofile=tofile, n=context_lines))
    return "".join(diff)


# Base directory for all session outputs
BASE_OUTPUT_DIR = Path(tempfile.gettempdir()) / "rossum_agent_outputs"


def create_session_output_dir() -> Path:
    """Create a new session-specific output directory.

    Returns:
        Path to the newly created session directory
    """
    session_id = str(uuid.uuid4())
    session_dir = BASE_OUTPUT_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def add_message_cache_breakpoint(messages: list[dict[str, Any]]) -> None:
    """Add cache_control to the last content block of the last message.

    Mutates messages in-place. Removes any previous message-level
    cache_control breakpoints first to stay within Anthropic's
    4-breakpoint limit.
    """
    if not messages:
        return
    # Remove previous message-level cache_control breakpoints
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    block.pop("cache_control", None)
    # Add breakpoint to last message
    last_msg = messages[-1]
    content = last_msg.get("content")
    if isinstance(content, list) and content:
        last_block = content[-1]
        if isinstance(last_block, dict):
            last_block["cache_control"] = {"type": "ephemeral"}
    elif isinstance(content, str) and content:
        last_msg["content"] = [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]
