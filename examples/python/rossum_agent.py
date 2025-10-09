#!/usr/bin/env python3
"""
Rossum Invoice Processing Agent

AI agent that interacts with the Rossum MCP server to upload and process documents.

Usage:
    python rossum_agent.py

Environment Variables:
    ROSSUM_API_TOKEN: Rossum API authentication token
    ROSSUM_API_BASE_URL: Rossum API base URL
    LLM_API_BASE_URL: LLM API endpoint URL
    LLM_MODEL_ID: (Optional) LLM model identifier
"""

import asyncio
import importlib.resources
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from smolagents import CodeAgent, LiteLLMModel, tool

# Constants
DEFAULT_LLM_MODEL = "openai/Qwen/Qwen3-Next-80B-A3B-Instruct-FP8"
SERVER_SCRIPT_PATH = "../../server.py"


@tool
def rossum_mcp_tool(operation: str, arguments: str = "{}") -> str:
    """Interface to Rossum MCP server for document processing.

    Args:
        operation: MCP operation name. Available:
            - 'upload_document': Upload document (requires: file_path, queue_id)
            - 'list_annotations': List annotations with optional filtering
            - 'get_annotation': Get annotation details (requires: annotation_id)
        arguments: JSON string of operation arguments.
            MUST use json.dumps() to convert dict to JSON string.
            IDs (queue_id, annotation_id) must be integers, not strings.

    Returns:
        JSON string with operation result. Use json.loads() to parse.
        Errors are returned with an "error" field.

    Note:
        After uploading documents, wait for "importing" state to complete.
        Use 'list_annotations' to check if any annotations are still importing
        before accessing their data.

    Example:
        # Upload document
        result = rossum_mcp_tool("upload_document",
                                json.dumps({"file_path": "/path/to/file.pdf", "queue_id": 12345}))
        data = json.loads(result)
        if "error" not in data:
            annotation_id = data.get("annotation_id")
    """
    # Validate arguments type
    if isinstance(arguments, dict):
        return json.dumps(
            {"error": "Arguments must be a JSON string. Use json.dumps({'file_path': '...', 'queue_id': 123})"}
        )

    try:
        args_dict = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON in arguments: {e!s}"})

    return asyncio.run(_execute_operation(operation, args_dict))


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


async def _execute_operation(operation: str, arguments: dict[str, Any]) -> str:
    """Execute Rossum MCP operation via stdio client."""
    server_script = os.path.join(os.path.dirname(__file__), SERVER_SCRIPT_PATH)
    server_params = StdioServerParameters(
        command="python3",
        args=[server_script],
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

                if result.content:
                    return result.content[0].text  # type: ignore[no-any-return]
                return json.dumps({"error": "No content in MCP result"})
    except Exception as e:
        return json.dumps({"error": f"MCP tool error: {e!s}"})


def create_agent() -> CodeAgent:
    """Create and configure the Rossum agent with custom tools and instructions."""
    llm = LiteLLMModel(
        model_id=os.environ.get("LLM_MODEL_ID", DEFAULT_LLM_MODEL),
        api_base=os.environ["LLM_API_BASE_URL"],
        api_key="not_needed",
    )

    prompt_templates = yaml.safe_load(
        importlib.resources.files("smolagents.prompts").joinpath("code_agent.yaml").read_text()
    )

    # Extend system prompt with JSON handling instructions for tools
    custom_instructions = """
CRITICAL: JSON String Handling for Tools

Tools returning JSON strings (MUST parse with json.loads()):
- rossum_mcp_tool, list_files, read_file, get_file_info

For rossum_mcp_tool:
- INPUT: Pass 'arguments' as JSON string using json.dumps(), NOT dict
- IDs: queue_id and annotation_id must be INTEGERS, not strings
- OUTPUT: Parse result with json.loads() before accessing

IMPORTANT: When uploading documents and checking status:
- After upload, documents enter "importing" state while being processed
- Use 'list_annotations' to check status of annotations in a queue
- Wait until no annotations are in "importing" state before accessing data
- Annotations in "importing" state are still being processed and data may be incomplete

Correct pattern:
```python
import json
import time

# Parse JSON string results
files_json = list_files('/path', '*.pdf')
files_data = json.loads(files_json)
for file in files_data['files']:
    file_path = file['path']

    # Upload document
    result_json = rossum_mcp_tool('upload_document',
                                  json.dumps({'file_path': file_path, 'queue_id': 12345}))
    result = json.loads(result_json)
    if 'error' not in result:
        annotation_id = result.get('annotation_id')

# Wait for all imports to complete before checking annotations
# Use list_annotations to verify no annotations are in "importing" state
annotations_json = rossum_mcp_tool('list_annotations', json.dumps({'queue_id': 12345}))
annotations = json.loads(annotations_json)
```

Common mistakes to avoid:
- Accessing JSON string as dict without json.loads()
- Passing dict to rossum_mcp_tool (use json.dumps())
- Using string IDs instead of integers
- Checking annotation data before imports finish
"""

    prompt_templates["system_prompt"] += "\n" + custom_instructions

    return CodeAgent(
        tools=[rossum_mcp_tool, list_files, read_file, get_file_info],
        model=llm,
        prompt_templates=prompt_templates,
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


def _check_env_vars() -> None:
    """Validate required environment variables are set."""
    required_vars = {
        "ROSSUM_API_TOKEN": "Rossum API authentication token",
        "ROSSUM_API_BASE_URL": "Rossum API base URL",
        "LLM_API_BASE_URL": "LLM API endpoint URL",
    }

    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        print("❌ Missing required environment variables:\n")
        for var in missing:
            print(f"  {var}: {required_vars[var]}")
            print(f"  Set with: export {var}=<value>\n")
        sys.exit(1)


def main() -> None:
    """Main entry point - run interactive agent CLI."""
    print("🤖 Rossum Invoice Processing Agent")
    print("=" * 50)

    _check_env_vars()

    print("\n🔧 Initializing agent...")
    agent = create_agent()

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

            response = agent.run(user_input)
            print(f"\n🤖 Agent: {response}\n")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e!s}\n")


if __name__ == "__main__":
    main()
