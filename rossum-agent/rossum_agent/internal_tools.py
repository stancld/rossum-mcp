"""Internal tools for the Rossum Agent.

This module provides local tools that are executed directly by the agent
rather than through the MCP server. These tools handle file operations
and other local functionality.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from anthropic import beta_tool

from rossum_agent.utils import get_session_output_dir

if TYPE_CHECKING:
    from anthropic._tools import BetaTool

logger = logging.getLogger(__name__)


@beta_tool
def write_file(filename: str, content: str) -> str:
    """Write text or markdown content to a file. Use this to save documentation, reports, diagrams, or any text output.
    Files are saved to a session-specific output directory and will be available for download in the sidebar.

    Args:
        filename: The name of the file to create (e.g., 'report.md', 'hooks.txt').
        Do not include directory paths - files are saved to the session output directory.
        content: The text content to write to the file.

    Returns:
        Success message with the file path, or error message if failed.
    """
    if not filename:
        return "Error: filename is required"

    if not content:
        return "Error: content is required"

    safe_filename = Path(filename).name
    if not safe_filename:
        return "Error: invalid filename"

    output_dir = get_session_output_dir()
    file_path = output_dir / safe_filename

    try:
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"Wrote file: {file_path}")
        return f"Successfully wrote {len(content)} characters to '{safe_filename}'"
    except Exception as e:
        error_msg = f"Error writing file '{safe_filename}': {e}"
        logger.error(error_msg)
        return error_msg


INTERNAL_TOOLS: list[BetaTool[..., str]] = [write_file]


def get_internal_tools() -> list[dict[str, object]]:
    """Get all internal tools in Anthropic format.

    Returns:
        List of tool definitions in Anthropic format.
    """
    return [tool.to_dict() for tool in INTERNAL_TOOLS]


def get_internal_tool_names() -> set[str]:
    """Get the names of all internal tools.

    Returns:
        Set of internal tool names.
    """
    return {tool.name for tool in INTERNAL_TOOLS}


def execute_internal_tool(name: str, arguments: dict[str, str]) -> str:
    """Execute an internal tool by name.

    Args:
        name: The name of the tool to execute.
        arguments: The arguments to pass to the tool.

    Returns:
        The result of the tool execution as a string.

    Raises:
        ValueError: If the tool name is not recognized.
    """
    for tool in INTERNAL_TOOLS:
        if tool.name == name:
            result: str = tool(**arguments)
            return result

    raise ValueError(f"Unknown internal tool: {name}")
