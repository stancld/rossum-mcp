"""File system tools for the Rossum Agent.

We use these tools to write into a specific output location.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from anthropic import beta_tool

from rossum_agent.tools.core import get_output_dir

logger = logging.getLogger(__name__)


@beta_tool
def write_file(filename: str, content: str) -> str:
    """Write content to a file in the agent's output directory.

    Use this tool to save analysis results, export data, or create reports.
    Files are saved to a session-specific directory that can be shared with the user.

    Args:
        filename: The name of the file to write (e.g., 'report.md', 'analysis.json').
        content: The content to write to the file.

    Returns:
        JSON with status, message, and file path.
    """
    if not filename or not filename.strip():
        return json.dumps({"status": "error", "message": "Error: filename is required"})

    if not content:
        return json.dumps({"status": "error", "message": "Error: content is required"})

    try:
        output_dir = get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = Path(filename).name
        file_path = output_dir / safe_filename

        file_path.write_text(content, encoding="utf-8")

        logger.info(f"write_file: wrote {len(content)} chars to {file_path}")
        return json.dumps(
            {
                "status": "success",
                "message": f"Successfully wrote {len(content)} characters to {safe_filename}",
                "path": str(file_path),
            }
        )
    except Exception as e:
        logger.exception("Error in write_file")
        return json.dumps({"status": "error", "message": f"Error writing file: {e}"})
