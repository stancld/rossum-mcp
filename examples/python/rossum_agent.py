#!/usr/bin/env python3
"""
Rossum Invoice Processing Agent

This script uses smolagents to create an AI agent that can interact with the Rossum MCP server
to upload and process invoices from a local folder.

Usage:
    python agent.py

Requirements:
    - smolagents
    - MCP client library
    - Rossum MCP server running
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from smolagents import CodeAgent, LiteLLMModel, tool


@tool
def rossum_mcp_tool(operation: str, arguments: str = "{}") -> str:
    """A tool for uploading and processing documents using Rossum API.

    Args:
        operation: The MCP tool operation to perform. Available operations:
            - 'upload_document': Upload a document to Rossum. Requires arguments: {"file_path": "/absolute/path/to/file.pdf", "queue_id": "12345"}
            - 'get_annotation': Get annotation data. Requires arguments: {"annotation_id": "12345"}
        arguments: JSON string of arguments to pass to the MCP tool.
            IMPORTANT: Must be a JSON STRING, not a dict. Use json.dumps() to convert dict to JSON string.
            For upload_document: json.dumps({"file_path": "/path/to/file", "queue_id": "queue_id_number"})
            For get_annotation: json.dumps({"annotation_id": "annotation_id_number"})

    Returns:
        JSON result of the operation

    Example:
        rossum_mcp_tool("upload_document", json.dumps({"file_path": "/path/to/invoice.pdf", "queue_id": "12345"}))
    """
    try:
        args_dict = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON in arguments: {e!s}. Arguments must be valid JSON string."})
    return asyncio.run(_execute_operation(operation, args_dict))


@tool
def list_files(directory_path: str, pattern: str | None = None) -> str:
    """List files and directories in a given path, optionally filtered by pattern.

    Args:
        directory_path: Absolute or relative path to the directory to list
        pattern: Optional glob pattern to filter files (e.g., '*.pdf' for PDF files)

    Returns:
        JSON string with list of files and their metadata.
        IMPORTANT: The return value is a JSON STRING. You must use json.loads() to parse it before accessing its contents.
        Example usage:
            result = list_files("/path/to/dir", "*.pdf")
            files_data = json.loads(result)
            for file in files_data['files']:
                print(file['path'])
    """
    try:
        dir_path = Path(directory_path).expanduser().resolve()

        if not dir_path.exists():
            return json.dumps({"error": f"Directory not found: {directory_path}"})

        if not dir_path.is_dir():
            return json.dumps({"error": f"Path is not a directory: {directory_path}"})

        # Get files
        files = list(dir_path.glob(pattern)) if pattern is not None else list(dir_path.iterdir())

        # Build result
        file_list = []
        for file in sorted(files):
            stat = file.stat()
            file_list.append(
                {
                    "name": file.name,
                    "path": str(file),
                    "type": "directory" if file.is_dir() else "file",
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                }
            )

        return json.dumps({"directory": str(dir_path), "count": len(file_list), "files": file_list}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to list files: {e!s}"})


@tool
def read_file(file_path: str) -> str:
    """Read the contents of a text file.

    Args:
        file_path: Absolute or relative path to the file to read

    Returns:
        JSON string with file content and metadata
    """
    try:
        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            return json.dumps({"error": f"File not found: {file_path}"})

        if not path.is_file():
            return json.dumps({"error": f"Path is not a file: {file_path}"})

        content = path.read_text()
        stat = path.stat()

        return json.dumps(
            {"path": str(path), "size": stat.st_size, "modified": stat.st_mtime, "content": content}, indent=2
        )
    except Exception as e:
        return json.dumps({"error": f"Failed to read file: {e!s}"})


@tool
def get_file_info(path: str) -> str:
    """Get metadata information about a file or directory.

    Args:
        path: Absolute or relative path to the file or directory

    Returns:
        JSON string with file/directory metadata
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


async def _execute_operation(operation: str, arguments: dict[str, Any]) -> str:
    """Execute the Rossum MCP operation"""
    server_params = StdioServerParameters(
        command="node",
        args=[os.path.join(os.path.dirname(__file__), "../../index.js")],
        env={
            **os.environ,
            "ROSSUM_API_BASE_URL": os.environ["ROSSUM_API_BASE_URL"],
            "ROSSUM_API_TOKEN": os.environ["ROSSUM_API_TOKEN"],
        },
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(operation, arguments=arguments)
                return str(result)
    except Exception as e:
        return f"Error calling MCP tool: {e!s}"


def create_agent() -> CodeAgent:
    """Create and configure the Rossum agent"""
    llm = LiteLLMModel(
        model_id=os.environ.get("LLM_MODEL_ID", "openai/Qwen/Qwen3-Next-80B-A3B-Instruct-FP8"),
        api_base=os.environ["LLM_API_BASE_URL"],
        api_key="not_needed",
    )
    return CodeAgent(
        tools=[rossum_mcp_tool, list_files, read_file, get_file_info],
        model=llm,
        additional_authorized_imports=[
            "collections",
            "datetime",
            "itertools",
            "json",
            "math",
            "os",
            "pathlib",
            "queue",
            "random",
            "re",
            "stat",
            "statistics",
            "time",
            "unicodedata",
        ],
        stream_outputs=True,
    )


def main() -> None:
    """Main entry point for the agent"""

    print("🤖 Rossum Invoice Processing Agent")
    print("=" * 50)

    # Check for required environment variables
    if not os.getenv("ROSSUM_API_TOKEN"):
        print("❌ Error: ROSSUM_API_TOKEN environment variable not set")
        print("Please set it with: export ROSSUM_API_TOKEN=your_token")
        sys.exit(1)

    if not os.getenv("ROSSUM_API_BASE_URL"):
        print("❌ Error: ROSSUM_API_BASE_URL environment variable not set")
        print("Please set it with: export ROSSUM_API_BASE_URL=your_url")
        sys.exit(1)

    if not os.getenv("LLM_API_BASE_URL"):
        print("❌ Error: LLM_API_BASE_URL environment variable not set")
        print("Please set it with: export LLM_API_BASE_URL=llm_api_base_url")
        sys.exit(1)

    # Create the agent
    print("\n🔧 Initializing agent...")
    agent = create_agent()

    # Interactive mode
    print("\n" + "=" * 50)
    print("Agent ready! You can now give instructions.")
    print("Example: 'Upload all invoices from the data folder'")
    print("Type 'quit' to exit")
    print("=" * 50 + "\n")

    while True:
        try:
            user_input = input("You: ").strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                print("👋 Goodbye!")
                break

            if not user_input:
                continue

            # Run the agent
            response = agent.run(user_input)
            print(f"\n🤖 Agent: {response}\n")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e!s}\n")


if __name__ == "__main__":
    main()
