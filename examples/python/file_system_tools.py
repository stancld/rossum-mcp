"""
File System Tools

Collection of file system utilities for the Rossum Agent.
Provides tools for listing, reading, and getting information about files.
"""

import json
from pathlib import Path

from smolagents import tool


@tool
def list_files(directory_path: str, pattern: str | None = None) -> str:
    """List files and directories with optional pattern filtering.

    Args:
        directory_path: Path to directory (absolute or relative)
        pattern: Optional glob pattern (e.g., '*.pdf')

    Returns:
        JSON string with files list. Use json.loads() to parse.
        Example: files_data = json.loads(list_files("/path", "*.pdf"))
    """
    try:
        dir_path = Path(directory_path).expanduser().resolve()

        if not dir_path.exists():
            return json.dumps({"error": f"Directory not found: {directory_path}"})
        if not dir_path.is_dir():
            return json.dumps({"error": f"Path is not a directory: {directory_path}"})

        files = list(dir_path.glob(pattern)) if pattern else list(dir_path.iterdir())

        file_list = [
            {
                "name": file.name,
                "path": str(file),
                "type": "directory" if file.is_dir() else "file",
                "size": file.stat().st_size,
                "modified": file.stat().st_mtime,
            }
            for file in sorted(files)
        ]

        return json.dumps({"directory": str(dir_path), "count": len(file_list), "files": file_list}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to list files: {e!s}"})


@tool
def read_file(file_path: str) -> str:
    """Read text file contents with metadata.

    Args:
        file_path: Path to file (absolute or relative)

    Returns:
        JSON string with file content. Use json.loads() to parse.
    """
    try:
        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            return json.dumps({"error": f"File not found: {file_path}"})
        if not path.is_file():
            return json.dumps({"error": f"Path is not a file: {file_path}"})

        stat = path.stat()
        return json.dumps(
            {"path": str(path), "size": stat.st_size, "modified": stat.st_mtime, "content": path.read_text()}, indent=2
        )
    except Exception as e:
        return json.dumps({"error": f"Failed to read file: {e!s}"})


@tool
def get_file_info(path: str) -> str:
    """Get file or directory metadata.

    Args:
        path: Path to file or directory (absolute or relative)

    Returns:
        JSON string with metadata. Use json.loads() to parse.
    """
    try:
        target_path = Path(path).expanduser().resolve()

        if not target_path.exists():
            return json.dumps({"error": f"Path not found: {path}"})

        stat = target_path.stat()
        return json.dumps(
            {
                "path": str(target_path),
                "name": target_path.name,
                "type": "directory" if target_path.is_dir() else "file",
                "size": stat.st_size,
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "accessed": stat.st_atime,
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"error": f"Failed to get file info: {e!s}"})
