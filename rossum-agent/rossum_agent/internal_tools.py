"""Internal tools for the Rossum Agent.

This module provides local tools that are executed directly by the agent
rather than through the MCP server. These tools handle file operations
and other local functionality.
"""

from __future__ import annotations

import asyncio
import builtins
import collections
import datetime as dt
import decimal
import functools
import io
import itertools
import json
import logging
import math
import re
import string
import threading
import time
import traceback
from collections.abc import Callable
from concurrent.futures import TimeoutError as FuturesTimeoutError
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests
from anthropic import beta_tool
from ddgs import DDGS
from ddgs.exceptions import DDGSException
from fastmcp import Client

from rossum_agent.agent.skills import get_skill, get_skill_registry
from rossum_agent.bedrock_client import create_bedrock_client
from rossum_agent.mcp_tools import MCPConnection, create_mcp_transport

if TYPE_CHECKING:
    from anthropic._tools import BetaTool

logger = logging.getLogger(__name__)


@dataclass
class SubAgentProgress:
    """Progress information from a sub-agent (e.g., debug_hook's Opus sub-agent)."""

    tool_name: str
    iteration: int
    max_iterations: int
    current_tool: str | None = None
    tool_calls: list[str] = field(default_factory=list)
    status: str = "running"


@dataclass
class SubAgentText:
    """Text output from a sub-agent (e.g., debug_hook's Opus sub-agent)."""

    tool_name: str
    text: str
    is_final: bool = False


# Type alias for progress callback
SubAgentProgressCallback = Callable[[SubAgentProgress], None]

# Type alias for text callback
SubAgentTextCallback = Callable[[SubAgentText], None]

# Module-level progress callback for sub-agent progress reporting
_progress_callback: SubAgentProgressCallback | None = None

# Module-level text callback for sub-agent text reporting
_text_callback: SubAgentTextCallback | None = None


def set_progress_callback(callback: SubAgentProgressCallback | None) -> None:
    """Set the progress callback for sub-agent progress reporting.

    Args:
        callback: Callback function called with SubAgentProgress updates.
    """
    global _progress_callback
    _progress_callback = callback


def set_text_callback(callback: SubAgentTextCallback | None) -> None:
    """Set the text callback for sub-agent text reporting.

    Args:
        callback: Callback function called with SubAgentText updates.
    """
    global _text_callback
    _text_callback = callback


def _report_progress(progress: SubAgentProgress) -> None:
    """Report progress via the callback if set."""
    if _progress_callback is not None:
        _progress_callback(progress)


def _report_text(text: SubAgentText) -> None:
    """Report text via the callback if set."""
    if _text_callback is not None:
        _text_callback(text)


# Module-level MCP connection for debug_hook sub-agent
# Set by the agent before calling debug_hook
_mcp_connection: MCPConnection | None = None
_mcp_event_loop: asyncio.AbstractEventLoop | None = None


@dataclass
class SpawnedConnection:
    """Record for a spawned MCP connection to a different environment."""

    connection: MCPConnection
    client: Client
    api_base_url: str


# Secondary MCP connections spawned at runtime for different environments
# NOTE: This module keeps global MCP connection state and assumes:
# - A single agent session per process
# - _mcp_event_loop is set once per process and is not changed concurrently
# If multi-session in a single process is needed, this registry must become per-session.
_spawned_connections: dict[str, SpawnedConnection] = {}
_spawned_connections_lock = threading.Lock()

# Module-level output directory for file operations
# Set by the agent service before running the agent
# This is needed because ContextVars don't propagate to ThreadPoolExecutor threads
_output_dir: Path | None = None


def set_output_dir(output_dir: Path | None) -> None:
    """Set the output directory for internal tools.

    This must be called before running the agent to ensure write_file
    saves files to the correct session-specific directory.

    Args:
        output_dir: The output directory path, or None to clear.
    """
    global _output_dir
    _output_dir = output_dir


def get_output_dir() -> Path:
    """Get the output directory for internal tools.

    Returns:
        The configured output directory, or a fallback './outputs' directory.
    """
    if _output_dir is not None:
        return _output_dir
    fallback = Path("./outputs")
    fallback.mkdir(exist_ok=True)
    return fallback


def set_mcp_connection(connection: MCPConnection, loop: asyncio.AbstractEventLoop) -> None:
    """Set the MCP connection for use by internal tools.

    This also clears any stale spawned connections from previous turns, since their
    underlying clients become disconnected when the main MCP connection's subprocess exits.

    Args:
        connection: The MCP connection to use for tool calls.
        loop: The event loop where the MCP connection was created.
    """
    global _mcp_connection, _mcp_event_loop
    _mcp_connection = connection
    _mcp_event_loop = loop

    # Clear stale spawned connections from previous turns
    # Their underlying clients are disconnected when the main connection's subprocess exited
    with _spawned_connections_lock:
        _spawned_connections.clear()


def _call_mcp_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Call an MCP tool synchronously from within a thread.

    This uses run_coroutine_threadsafe to call async MCP tools from sync context.
    """
    if _mcp_connection is None or _mcp_event_loop is None:
        raise RuntimeError("MCP connection not set. Call set_mcp_connection first.")

    future = asyncio.run_coroutine_threadsafe(_mcp_connection.call_tool(name, arguments), _mcp_event_loop)
    return future.result(timeout=60)


async def _spawn_connection_async(
    connection_id: str, api_token: str, api_base_url: str, mcp_mode: str = "read-write"
) -> SpawnedConnection:
    """Spawn a new MCP connection asynchronously.

    Raises:
        ValueError: If connection_id already exists.
    """
    with _spawned_connections_lock:
        if connection_id in _spawned_connections:
            raise ValueError(f"Connection '{connection_id}' already exists")

    transport = create_mcp_transport(api_token, api_base_url, mcp_mode)  # type: ignore[arg-type]
    client = Client(transport)

    await client.__aenter__()
    connection = MCPConnection(client=client)

    record = SpawnedConnection(
        connection=connection,
        client=client,
        api_base_url=api_base_url,
    )

    with _spawned_connections_lock:
        _spawned_connections[connection_id] = record

    return record


async def _close_spawned_connection_async(connection_id: str) -> None:
    """Close a spawned MCP connection."""
    with _spawned_connections_lock:
        record = _spawned_connections.pop(connection_id, None)

    if record is not None:
        await record.client.__aexit__(None, None, None)


def cleanup_all_spawned_connections() -> None:
    """Cleanup all spawned connections. Call this when the agent session ends.

    Should only be called once at session teardown, after no more tool calls are expected.
    """
    if _mcp_event_loop is None:
        return

    with _spawned_connections_lock:
        conn_ids = list(_spawned_connections.keys())

    for conn_id in conn_ids:
        try:
            future = asyncio.run_coroutine_threadsafe(_close_spawned_connection_async(conn_id), _mcp_event_loop)
            future.result(timeout=10)
        except FuturesTimeoutError:
            future.cancel()
            logger.warning(f"Timeout cleaning up connection {conn_id}")
        except Exception as e:
            logger.warning(f"Failed to cleanup connection {conn_id}: {e}")


@beta_tool
def spawn_mcp_connection(connection_id: str, api_token: str, api_base_url: str, mcp_mode: str = "read-write") -> str:
    """Spawn a new MCP connection to a different Rossum environment.

    Use this when you need to make changes to a different Rossum environment than the one the agent was initialized with.
    For example, when deploying changes from a source environment to a target environment.

    Args:
        connection_id: A unique identifier for this connection (e.g., 'target', 'sandbox')

    Returns:
        Success message with available tools, or error message if failed.
    """
    if _mcp_event_loop is None:
        return "Error: MCP event loop not set. Agent not properly initialized."

    if not connection_id or not connection_id.strip():
        return "Error: connection_id must be non-empty."

    if not api_base_url or not api_base_url.startswith("https://"):
        return "Error: api_base_url must start with https://"

    try:
        future = asyncio.run_coroutine_threadsafe(
            _spawn_connection_async(connection_id, api_token, api_base_url, mcp_mode),
            _mcp_event_loop,
        )
        record = future.result(timeout=30)

        tools_future = asyncio.run_coroutine_threadsafe(record.connection.get_tools(), _mcp_event_loop)
        tools = tools_future.result(timeout=30)
        tool_names = [t.name for t in tools]

        return f"Successfully spawned MCP connection '{connection_id}' to {api_base_url}. Available tools: {', '.join(tool_names[:10])}{'...' if len(tool_names) > 10 else ''}"
    except ValueError as e:
        return f"Error: {e}"
    except FuturesTimeoutError:
        future.cancel()
        return "Error: Timed out while spawning MCP connection."
    except RuntimeError as e:
        logger.exception("Error scheduling MCP call")
        return f"Error: Failed to schedule MCP call: {e}"
    except Exception as e:
        logger.error(f"Failed to spawn connection: {e}")
        return f"Error spawning connection: {e}"


@beta_tool
def call_on_connection(connection_id: str, tool_name: str, arguments: str) -> str:
    """Call a tool on a spawned MCP connection.

    Use this to execute MCP tools on a connection that was previously spawned with spawn_mcp_connection.

    Args:
        connection_id: The identifier of the spawned connection.
        tool_name: The name of the MCP tool to call.
        arguments: JSON string of arguments to pass to the tool.

    Returns:
        The result of the tool call as a JSON string, or error message.
    """
    if _mcp_event_loop is None:
        return "Error: MCP event loop not set."

    with _spawned_connections_lock:
        if connection_id not in _spawned_connections:
            available = list(_spawned_connections.keys())
            return f"Error: Connection '{connection_id}' not found. Available: {available}"
        record = _spawned_connections[connection_id]

    logger.debug(f"call_on_connection: Using connection '{connection_id}' - API URL: {record.api_base_url}")

    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError as e:
        return f"Error parsing arguments JSON: {e}"

    try:
        future = asyncio.run_coroutine_threadsafe(record.connection.call_tool(tool_name, args), _mcp_event_loop)
        result = future.result(timeout=60)

        if isinstance(result, (dict, list)):
            return json.dumps(result, indent=2, default=str)
        return str(result) if result is not None else "Tool executed successfully"
    except FuturesTimeoutError:
        future.cancel()
        return f"Error: Timed out calling {tool_name} after 60 seconds."
    except Exception as e:
        logger.error(f"Error calling tool on connection: {e}")
        return f"Error calling {tool_name}: {e}"


@beta_tool
def close_connection(connection_id: str) -> str:
    """Close a spawned MCP connection."""
    if _mcp_event_loop is None:
        return "Error: MCP event loop not set."

    with _spawned_connections_lock:
        if connection_id not in _spawned_connections:
            return f"Connection '{connection_id}' not found."

    try:
        future = asyncio.run_coroutine_threadsafe(_close_spawned_connection_async(connection_id), _mcp_event_loop)
        future.result(timeout=10)
        return f"Successfully closed connection '{connection_id}'."
    except FuturesTimeoutError:
        future.cancel()
        return f"Error: Timed out closing connection '{connection_id}'."
    except Exception as e:
        return f"Error closing connection: {e}"


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

    output_dir = get_output_dir()
    file_path = output_dir / safe_filename

    try:
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"Wrote file: {file_path}")
        return f"Successfully wrote {len(content)} characters to '{safe_filename}'"
    except Exception as e:
        error_msg = f"Error writing file '{safe_filename}': {e}"
        logger.error(error_msg)
        return error_msg


@beta_tool
def search_knowledge_base(query: str, user_query: str | None = None) -> str:
    """Search the Rossum Knowledge Base for documentation about extensions, hooks, and configurations.

    Use this tool to find information about Rossum features, troubleshoot errors,
    and understand extension configurations. The search is performed against
    https://knowledge-base.rossum.ai/docs.

    Args:
        query: Search query. Be specific - include extension names, error messages,
        or feature names. Examples: 'document splitting extension',
        'duplicate handling configuration', 'webhook timeout error'.
        user_query: The original user question for context. Pass the user's full
        question here so Opus can tailor the analysis to address their specific needs.

    Returns:
        JSON with search results containing title, URL, and snippet for each result.
    """
    if not query:
        return json.dumps({"status": "error", "message": "Query is required"})
    return _search_knowledge_base(query, user_query=user_query)


def _strip_imports(code: str) -> str:
    """Strip import statements from code since they're not allowed in sandbox."""
    lines = code.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        # Skip import lines
        if stripped.startswith("import ") or stripped.startswith("from "):
            continue
        result.append(line)
    return "\n".join(result)


# Restricted builtins for evaluate_python_hook (conservative set)
_ALLOWED_BUILTIN_NAMES = {
    # Basics
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "enumerate",
    "filter",
    "float",
    "frozenset",
    "getattr",
    "hasattr",
    "int",
    "isinstance",
    "iter",
    "len",
    "list",
    "map",
    "max",
    "min",
    "next",
    "pow",
    "range",
    "repr",
    "reversed",
    "round",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
    # Exceptions / types
    "Exception",
    "ValueError",
    "TypeError",
    "KeyError",
    "IndexError",
    "RuntimeError",
    "AttributeError",
    # I/O (print only)
    "print",
    # None, True, False are handled automatically
}


def _make_evaluate_response(
    status: str,
    start_time: float,
    result: Any = None,
    stdout: str = "",
    stderr: str = "",
    exc: BaseException | None = None,
) -> str:
    """Create a JSON response for evaluate_python_hook."""
    exc_info: dict[str, str] | None
    if exc is not None:
        exc_info = {
            "type": exc.__class__.__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
    else:
        exc_info = None

    payload = {
        "status": status,
        "result": result,
        "stdout": stdout,
        "stderr": stderr,
        "exception": exc_info,
        "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


@beta_tool
def evaluate_python_hook(
    code: str,
    annotation_json: str,
    schema_json: str | None = None,
) -> str:
    """Execute Rossum function hook Python code against test annotation/schema data for debugging.

    This runs the provided code in a restricted environment, looks for a function named
    `rossum_hook_request_handler`, and calls it with a payload containing the annotation
    and optional schema data.

    **IMPORTANT**: This is for debugging only. No imports or external I/O are allowed.
    The code runs in a sandboxed environment with limited builtins.

    Args:
        code: Full Python source containing a function:
            `def rossum_hook_request_handler(payload): ...`
            The function receives a dict with 'annotation' and optionally 'schema' keys.
        annotation_json: JSON string of the annotation object as seen in hook payload["annotation"].
            Get this from the get_annotation MCP tool.
        schema_json: Optional JSON string of the schema object as seen in payload["schema"].
            Get this from the get_schema MCP tool.

    Returns:
        A JSON string with structure:
        {
          "status": "success" | "error" | "invalid_input",
          "result": <return value from handler, if any>,
          "stdout": "<captured stdout from print statements>",
          "stderr": "<captured stderr>",
          "exception": {"type": "...", "message": "...", "traceback": "..."} | null,
          "elapsed_ms": <execution time in milliseconds>
        }
    """
    start_time = time.perf_counter()

    if not code:
        return _make_evaluate_response(
            "invalid_input",
            start_time,
            stderr="No code provided",
        )

    # Parse JSON inputs
    try:
        annotation = json.loads(annotation_json)
    except Exception as e:
        logger.exception("Failed to parse annotation_json")
        return _make_evaluate_response("invalid_input", start_time, stderr=f"Invalid annotation_json: {e}", exc=e)

    schema = None
    if schema_json:
        try:
            schema = json.loads(schema_json)
        except Exception as e:
            logger.exception("Failed to parse schema_json")
            return _make_evaluate_response("invalid_input", start_time, stderr=f"Invalid schema_json: {e}", exc=e)

    # Construct a minimal Rossum-like payload
    payload: dict[str, Any] = {"annotation": annotation}
    if schema is not None:
        payload["schema"] = schema

    # Build safe builtins dict
    safe_builtins: dict[str, object] = {
        name: getattr(builtins, name) for name in _ALLOWED_BUILTIN_NAMES if hasattr(builtins, name)
    }
    # Intentionally DO NOT expose __import__, open, exec, eval, compile, etc.

    # Execution environment for user code
    # Use single namespace so helper functions defined in the code are visible to the handler
    exec_namespace: dict[str, Any] = {
        "__builtins__": safe_builtins,
        # Commonly used modules/types in hooks
        "collections": collections,
        "datetime": dt,
        "decimal": decimal,
        "Decimal": Decimal,
        "InvalidOperation": decimal.InvalidOperation,
        "functools": functools,
        "itertools": itertools,
        "json": json,
        "math": math,
        "re": re,
        "string": string,
    }

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    # Strip import statements since they're not allowed
    clean_code = _strip_imports(code)

    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            # 1. Load the code - use single namespace so all definitions are in same scope
            exec(clean_code, exec_namespace)

            # 2. Find the handler
            handler = exec_namespace.get("rossum_hook_request_handler")
            if handler is None or not callable(handler):
                raise RuntimeError(
                    "No callable `rossum_hook_request_handler` found. "
                    "Define it as `def rossum_hook_request_handler(payload): ...`"
                )

            # 3. Call the handler
            result = handler(payload)

        return _make_evaluate_response(
            status="success",
            start_time=start_time,
            result=result,
            stdout=stdout_buf.getvalue(),
            stderr=stderr_buf.getvalue(),
        )
    except Exception as e:
        logger.exception("Error while evaluating python hook")
        return _make_evaluate_response(
            status="error",
            start_time=start_time,
            result=None,
            stdout=stdout_buf.getvalue(),
            stderr=stderr_buf.getvalue(),
            exc=e,
        )


# Opus model for debug_hook sub-agent
OPUS_MODEL_ID = "eu.anthropic.claude-opus-4-5-20251101-v1:0"

# System prompt for the hook debugging sub-agent
_HOOK_DEBUG_SYSTEM_PROMPT = """You are an expert Rossum hook debugger. Your role is to fetch hook code and annotation data, \
analyze the code, identify ALL issues, and FIX THEM by iteratively testing with the evaluate_python_hook tool.

## CRITICAL: Investigate ALL Issues

**DO NOT stop at the first issue you find.** You MUST:
- Continue investigating after fixing each issue
- Look for multiple problems in the code (there are often several)
- Check for edge cases, missing error handling, and potential runtime failures
- Analyze the ENTIRE codebase, not just the first error location
- Keep iterating until the code handles ALL scenarios correctly

Common categories of issues to check:
- Syntax errors and typos
- Missing null/empty value checks
- Type conversion errors (especially Decimal)
- Missing fields or incorrect field access
- Logic errors in calculations
- Edge cases (empty lists, missing data, zero values)
- Return value format errors

## Available Tools

You have access to:
1. `get_hook` - Fetch hook code by ID. The code is in `config.code`.
2. `get_annotation` - Fetch annotation data by ID. Use `content` for datapoints.
3. `get_schema` - Optionally fetch schema by ID.
4. `evaluate_python_hook` - Execute hook code against annotation data.
5. `web_search` - Search Rossum Knowledge Base for documentation on extensions, hooks, and best practices that cannot be obtained from the API.

## Rossum Hook Context

Rossum hooks are Python functions that process document annotations. The main entry point is:
```python
def rossum_hook_request_handler(payload):
    annotation = payload["annotation"]  # The annotation object with content
    schema = payload.get("schema")      # Optional schema definition
    # Process and return results
```

Typical behavior:
1. **Field access**: `annotation["content"]` contains datapoints with `schema_id`, `value`, and numeric `id`.
2. **Field updates**: Return `{"operations": [{"op": "replace", "id": <numeric_id>, "value": {...}}]}`.
3. **Messages**: Return `{"messages": [{"type": "error", "content": "..."}]}`.

## Debugging Environment Constraints

In this debugging environment:
- Imports and external I/O are NOT allowed in the hook code.
- You have access to `evaluate_python_hook` tool to execute and test hook code.
- Available modules: `collections`, `datetime`, `decimal` (with `Decimal`, `InvalidOperation`), `functools`, `itertools`, `json`, `math`, `re`, `string`.

## Common Pitfalls

- **Decimal conversion**: Field values may be empty strings, None, or contain formatting. Always handle: `Decimal(value) if value else Decimal(0)` or use try/except.
- **Missing fields**: Always check if fields exist before accessing them.
- **Type mismatches**: Field values are often strings, not numbers. Convert explicitly.

## Your Task - EXHAUSTIVE ITERATIVE DEBUGGING

You MUST follow this process:

1. **Fetch data**: Call `get_hook` and `get_annotation` to get the hook code and annotation data.
2. **Analyze thoroughly**: Understand what the hook is supposed to do. Look for ALL potential issues, not just the first one.
3. **Execute**: Use `evaluate_python_hook` tool to run the code and see the actual error.
4. **Fix ALL issues**: Based on the execution result AND your analysis, fix all problems you identified.
5. **Verify**: Use `evaluate_python_hook` again to confirm your fix works (status="success").
6. **Continue investigating**: Even after getting "success", review the code for other potential issues, edge cases, and improvements.
7. **Repeat**: Keep iterating until the code is robust and handles all scenarios.

IMPORTANT: You MUST call `evaluate_python_hook` at least once to verify your fix works before providing \
your final answer. Do not just analyze - actually execute the code!

## Final Output Format

After your exhaustive debugging, provide:

1. **What the hook does**: Brief explanation of the hook's intended purpose.
2. **ALL issues found**: List EVERY problem you discovered through analysis and execution (not just the first one).
3. **Root causes**: Explain why each error occurred based on actual execution results.
4. **Fixed code**: The complete, working code that you have VERIFIED by executing it and that addresses ALL issues.
5. **Verification**: Show the successful execution result proving your fix works.

Be thorough and exhaustive. Your primary goal is to provide ROBUST, WORKING code that handles all edge cases, verified by actual execution."""


# Tool definitions for Opus sub-agent
_GET_HOOK_TOOL = {
    "name": "get_hook",
    "description": "Fetch a Rossum hook by ID. Returns the hook object with config.code containing the Python code.",
    "input_schema": {
        "type": "object",
        "properties": {
            "hook_id": {
                "type": "string",
                "description": "The hook ID (numeric string)",
            },
        },
        "required": ["hook_id"],
    },
}

_GET_ANNOTATION_TOOL = {
    "name": "get_annotation",
    "description": "Fetch a Rossum annotation by ID. Returns the annotation object with content containing datapoints.",
    "input_schema": {
        "type": "object",
        "properties": {
            "annotation_id": {
                "type": "string",
                "description": "The annotation ID (numeric string)",
            },
        },
        "required": ["annotation_id"],
    },
}

_GET_SCHEMA_TOOL = {
    "name": "get_schema",
    "description": "Fetch a Rossum schema by ID. Returns the schema definition.",
    "input_schema": {
        "type": "object",
        "properties": {
            "schema_id": {
                "type": "string",
                "description": "The schema ID (numeric string)",
            },
        },
        "required": ["schema_id"],
    },
}

_EVALUATE_HOOK_TOOL = {
    "name": "evaluate_python_hook",
    "description": (
        "Execute Rossum hook Python code against annotation/schema data. "
        "Returns JSON with status, result, stdout, stderr, and exception info."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Full Python source with rossum_hook_request_handler(payload) function",
            },
            "annotation_json": {
                "type": "string",
                "description": "JSON string of annotation data",
            },
            "schema_json": {
                "type": "string",
                "description": "Optional JSON string of schema data",
            },
        },
        "required": ["code", "annotation_json"],
    },
}

# Knowledge base search tool definition
_SEARCH_KNOWLEDGE_BASE_TOOL: dict[str, Any] = {
    "name": "search_knowledge_base",
    "description": (
        "Search the Rossum Knowledge Base (https://knowledge-base.rossum.ai/docs) "
        "for documentation about extensions, hooks, configurations, and best practices. "
        "Use this tool to find information about Rossum features, troubleshoot errors, "
        "and understand extension configurations."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Search query. Be specific - include extension names, error messages, "
                    "or feature names. Examples: 'document splitting extension', "
                    "'duplicate handling configuration', 'webhook timeout error'"
                ),
            },
        },
        "required": ["query"],
    },
}

# All tools available to the Opus sub-agent
_OPUS_TOOLS: list[dict[str, Any]] = [
    _GET_HOOK_TOOL,
    _GET_ANNOTATION_TOOL,
    _GET_SCHEMA_TOOL,
    _EVALUATE_HOOK_TOOL,
    _SEARCH_KNOWLEDGE_BASE_TOOL,
]


class WebSearchError(Exception):
    """Raised when web search fails."""

    pass


_WEB_SEARCH_NO_RESULTS = "__NO_RESULTS__"

# System prompt for the web search analysis sub-agent
_WEB_SEARCH_ANALYSIS_SYSTEM_PROMPT = """You are a Rossum documentation expert. Your role is to analyze search results from the Rossum Knowledge Base and extract the most relevant information.

## Your Task

Given search results from the Rossum Knowledge Base, you must:

1. **Analyze the results**: Identify which results are most relevant to the user's query
2. **Extract key information**: Pull out the specific technical details, code examples, and JSON configurations
3. **Synthesize a response**: Provide a clear, actionable summary that directly addresses the user's needs

## Output Format

Your response should be structured and concise:

1. **Most Relevant Information**: The key facts, JSON configurations, or code examples that answer the query
2. **Implementation Details**: Specific steps or code patterns if applicable
3. **Configuration Details**: Specific configuration details, i.e. file datatypes, singlevalue vs multivalue datapoints must be returned as bold text
4. **Related Topics**: Brief mention of related documentation pages for further reading

IMPORTANT: You must return exact configuration requirements and mention they are CRITICAL!.

Be direct and technical. Focus on actionable information that helps with Rossum hook development, extension configuration, or API usage."""


def _call_opus_for_web_search_analysis(query: str, search_results: str, user_query: str | None = None) -> str:
    """Call Opus model to analyze web search results.

    Args:
        query: The search query used to find the results.
        search_results: The raw search results text.
        user_query: The original user query/question for context (optional).

    Returns:
        Opus model's analysis of the search results.
    """
    try:
        _report_progress(
            SubAgentProgress(
                tool_name="search_knowledge_base",
                iteration=0,
                max_iterations=0,
                status="thinking",
            )
        )

        client = create_bedrock_client()

        user_query_context = ""
        if user_query and user_query != query:
            user_query_context = f"""
## User's Original Question

The user asked: "{user_query}"

Keep this context in mind when analyzing the search results and tailor your response to address the user's specific question.

"""

        user_content = f"""Analyze these Rossum Knowledge Base search results for the query: "{query}"
{user_query_context}
## Search Results

{search_results}

## Instructions

Extract and summarize the most relevant information from these search results. Focus on:
- Specific technical details, configurations, and code examples
- **Exact schema definition - data types, singlevalue datapoints vs multivalues**
- Step-by-step instructions if present
- API endpoints, parameters, and payloads
- Common patterns and best practices

Provide a clear, actionable summary that a developer can use immediately."""

        response = client.messages.create(
            model=OPUS_MODEL_ID,
            max_tokens=4096,
            temperature=0.25,
            system=_WEB_SEARCH_ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        text_parts = [block.text for block in response.content if hasattr(block, "text")]
        analysis_result = "\n".join(text_parts) if text_parts else "No analysis provided"

        _report_progress(
            SubAgentProgress(
                tool_name="search_knowledge_base",
                iteration=0,
                max_iterations=0,
                status="completed",
            )
        )

        _report_text(
            SubAgentText(
                tool_name="search_knowledge_base",
                text=analysis_result,
                is_final=True,
            )
        )

        return analysis_result

    except Exception as e:
        logger.exception("Error calling Opus for web search analysis")
        return f"Error analyzing search results: {e}\n\nRaw results:\n{search_results}"


# Constants for knowledge base search
_KNOWLEDGE_BASE_DOMAIN = "knowledge-base.rossum.ai"
_MAX_SEARCH_RESULTS = 5
_WEBPAGE_FETCH_TIMEOUT = 30
_JINA_READER_PREFIX = "https://r.jina.ai/"


def _fetch_webpage_content(url: str) -> str:
    """Fetch and extract webpage content using Jina Reader for JS-rendered pages.

    Uses Jina Reader API to render JavaScript content from SPAs like the
    Rossum knowledge base.

    Args:
        url: The URL to fetch.

    Returns:
        Markdown content of the page, or error message if fetch fails.
    """
    jina_url = f"{_JINA_READER_PREFIX}{url}"
    try:
        response = requests.get(jina_url, timeout=_WEBPAGE_FETCH_TIMEOUT)
        response.raise_for_status()
        content = response.text
        return content[:50000]
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch webpage {url} via Jina Reader: {e}")
        return f"[Failed to fetch content: {e}]"


def _search_knowledge_base(query: str, analyze_with_opus: bool = True, user_query: str | None = None) -> str:
    """Search Rossum Knowledge Base using DDGS metasearch library.

    Args:
        query: Search query string.
        analyze_with_opus: Whether to analyze results with Opus sub-agent.
        user_query: The original user query/question for context (optional).

    Returns:
        JSON string with analyzed results, raw results, or error message.

    Raises:
        WebSearchError: If search fails completely.
    """
    site_query = f"site:{_KNOWLEDGE_BASE_DOMAIN} {query}"
    logger.info(f"Searching knowledge base: {site_query}")

    try:
        with DDGS() as ddgs:
            raw_results = ddgs.text(site_query, max_results=_MAX_SEARCH_RESULTS)
    except DDGSException as e:
        logger.error(f"Knowledge base search failed: {e}")
        raise WebSearchError(f"Search failed: {e}")

    filtered_results = [r for r in raw_results if _KNOWLEDGE_BASE_DOMAIN in r.get("href", "")][:2]

    results = []
    for r in filtered_results:
        url = r.get("href", "")
        logger.info(f"Fetching full content from: {url}")
        full_content = _fetch_webpage_content(url)
        results.append(
            {
                "title": r.get("title", ""),
                "url": url,
                "content": full_content,
            }
        )

    if not results:
        logger.warning(f"No results found for query: {query}")
        return json.dumps(
            {
                "status": "no_results",
                "query": query,
                "message": (
                    f"No results found in Rossum Knowledge Base for: '{query}'. "
                    "Try different keywords or check the extension/hook name spelling."
                ),
            }
        )

    logger.info(f"Found {len(results)} results for query: {query}")

    if analyze_with_opus:
        search_results_text = "\n\n---\n\n".join(
            f"## {r['title']}\nURL: {r['url']}\n\n{r['content']}" for r in results
        )
        logger.info("Analyzing knowledge base results with Opus sub-agent")
        analyzed = _call_opus_for_web_search_analysis(query, search_results_text, user_query=user_query)
        return json.dumps(
            {"status": "success", "query": query, "analysis": analyzed, "source_urls": [r["url"] for r in results]}
        )

    return json.dumps({"status": "success", "query": query, "results": results})


def _extract_web_search_text_from_block(block: Any) -> str | None:
    """Extract full web search results text from a single web_search_tool_result block.

    Args:
        block: The response content block to process.

    Returns:
        Formatted text with full search results, _WEB_SEARCH_NO_RESULTS if search
        returned empty, or None if not a web search block.

    Raises:
        WebSearchError: If web search returned an error.
    """
    if not (hasattr(block, "type") and block.type == "web_search_tool_result"):
        return None

    search_results_text = []
    if hasattr(block, "content") and block.content:
        for result in block.content:
            result_type = getattr(result, "type", None)

            if result_type == "web_search_result_error":
                error_code = getattr(result, "error_code", "unknown")
                error_message = getattr(result, "message", "Web search failed")
                logger.error(f"Web search error: code={error_code}, message={error_message}")
                raise WebSearchError(f"Web search failed: {error_code} - {error_message}")

            if result_type == "web_search_result":
                title = getattr(result, "title", "")
                url = getattr(result, "url", "")
                page_content = getattr(result, "page_content", "")
                search_results_text.append(f"## {title}\nURL: {url}\n\n{page_content}\n")

    if not search_results_text:
        logger.warning("Web search returned no results for the query")
        return _WEB_SEARCH_NO_RESULTS

    return "\n---\n".join(search_results_text)


def _extract_web_search_results(
    block: Any, iteration: int, max_iterations: int, analyze_with_opus: bool = True
) -> dict[str, Any] | None:
    """Extract web search results from a web_search_tool_result block for sub-agent.

    Args:
        block: The response content block to process.
        iteration: Current iteration number for logging.
        max_iterations: Maximum iterations for logging.
        analyze_with_opus: Whether to analyze results with Opus sub-agent.

    Returns:
        Tool result dict with search results (analyzed or raw), or None if not a web search block.
    """
    full_results = _extract_web_search_text_from_block(block)
    if full_results is None:
        return None

    if full_results == _WEB_SEARCH_NO_RESULTS:
        logger.info(f"debug_hook sub-agent [iter {iteration}/{max_iterations}]: web search returned no results")
        return {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": "Web search returned no results for the query.",
        }

    logger.info(f"debug_hook sub-agent [iter {iteration}/{max_iterations}]: processing web search results")

    if analyze_with_opus:
        query = getattr(block, "search_query", "Rossum documentation")
        logger.info(f"debug_hook sub-agent [iter {iteration}/{max_iterations}]: analyzing with Opus sub-agent")
        analyzed_results = _call_opus_for_web_search_analysis(query, full_results)
        content = f"Analyzed Rossum Knowledge Base search results:\n\n{analyzed_results}"
    else:
        content = f"Full Rossum Knowledge Base search results:\n\n{full_results}"

    return {
        "type": "tool_result",
        "tool_use_id": block.id,
        "content": content,
    }


def _save_debug_context(iteration: int, max_iterations: int, messages: list[dict[str, Any]]) -> None:
    """Save agent input context to file for debugging."""
    try:
        output_dir = get_output_dir()
        context_file = output_dir / f"debug_hook_context_iter_{iteration}.json"
        context_data = {
            "iteration": iteration,
            "max_iterations": max_iterations,
            "model": OPUS_MODEL_ID,
            "max_tokens": 16384,
            "system_prompt": _HOOK_DEBUG_SYSTEM_PROMPT,
            "messages": messages,
            "tools": _OPUS_TOOLS,
        }
        context_file.write_text(json.dumps(context_data, indent=2, default=str))
        logger.info(f"debug_hook sub-agent: saved context to {context_file}")
    except Exception as e:
        logger.warning(f"Failed to save debug_hook context: {e}")


def _execute_opus_tool(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Execute a tool for the Opus sub-agent.

    Args:
        tool_name: Name of the tool to execute.
        tool_input: Tool input arguments.

    Returns:
        Tool result as a string.
    """
    if tool_name == "evaluate_python_hook":
        result: str = evaluate_python_hook(
            code=tool_input.get("code", ""),
            annotation_json=tool_input.get("annotation_json", ""),
            schema_json=tool_input.get("schema_json"),
        )
        return result
    if tool_name == "search_knowledge_base":
        query = tool_input.get("query", "")
        if not query:
            return json.dumps({"status": "error", "message": "Query is required"})
        return _search_knowledge_base(query, analyze_with_opus=False)
    if tool_name in ("get_hook", "get_annotation", "get_schema"):
        mcp_result = _call_mcp_tool(tool_name, tool_input)
        return json.dumps(mcp_result, indent=2, default=str) if mcp_result else "No data returned"
    return f"Unknown tool: {tool_name}"


def _call_opus_for_debug(hook_id: str, annotation_id: str, schema_id: str | None) -> str:
    """Call Opus model for hook debugging with tool use for iterative testing.

    Args:
        hook_id: The hook ID to fetch and debug.
        annotation_id: The annotation ID to use for testing.
        schema_id: Optional schema ID.

    Returns:
        Opus model's analysis and recommendations after iterative debugging
    """
    try:
        client = create_bedrock_client()

        user_content = f"""Debug the hook with ID {hook_id} using annotation ID {annotation_id}.

Steps:
1. Call `get_hook` with hook_id="{hook_id}" to fetch the hook code (in config.code)
2. Call `get_annotation` with annotation_id="{annotation_id}" to fetch the annotation data
{f'3. Optionally call `get_schema` with schema_id="{schema_id}" if needed' if schema_id else ""}
3. Use `evaluate_python_hook` to execute the code and debug any issues
4. Fix and verify your fixes work before providing your final answer"""

        messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]

        max_iterations = 15
        response = None
        for iteration in range(max_iterations):
            logger.info(f"debug_hook sub-agent: iteration {iteration + 1}/{max_iterations}")

            _report_progress(
                SubAgentProgress(
                    tool_name="debug_hook", iteration=iteration + 1, max_iterations=max_iterations, status="thinking"
                )
            )

            _save_debug_context(iteration + 1, max_iterations, messages)

            response = client.messages.create(
                model=OPUS_MODEL_ID,
                max_tokens=16384,
                system=_HOOK_DEBUG_SYSTEM_PROMPT,
                messages=messages,
                tools=_OPUS_TOOLS,
            )

            # Check if model wants to stop (end_of_turn or no tool calls)
            has_tool_use = any(hasattr(block, "type") and block.type == "tool_use" for block in response.content)

            if response.stop_reason == "end_of_turn" or not has_tool_use:
                logger.info(
                    f"debug_hook sub-agent: completed after {iteration + 1} iterations (stop_reason={response.stop_reason}, has_tool_use={has_tool_use})"
                )
                _report_progress(
                    SubAgentProgress(
                        tool_name="debug_hook",
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

            # Process web_search_tool_result blocks - add full results to context
            for block in response.content:
                web_result = _extract_web_search_results(block, iteration + 1, max_iterations)
                if web_result:
                    tool_results.append(web_result)

            for block in response.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    iteration_tool_calls.append(tool_name)
                    logger.info(
                        f"debug_hook sub-agent [iter {iteration + 1}/{max_iterations}]: calling tool '{tool_name}'"
                    )

                    _report_progress(
                        SubAgentProgress(
                            tool_name="debug_hook",
                            iteration=iteration + 1,
                            max_iterations=max_iterations,
                            current_tool=tool_name,
                            tool_calls=iteration_tool_calls.copy(),
                            status="running_tool",
                        )
                    )

                    try:
                        result = _execute_opus_tool(tool_name, tool_input)
                        if tool_name == "evaluate_python_hook":
                            try:
                                result_obj = json.loads(result)
                                status = result_obj.get("status", "unknown")
                                exc_type = (
                                    result_obj.get("exception", {}).get("type")
                                    if result_obj.get("exception")
                                    else None
                                )
                                log_msg = f"evaluate_python_hook returned status='{status}'" + (
                                    f", exception={exc_type}" if exc_type else ""
                                )
                                logger.info(f"debug_hook sub-agent [iter {iteration + 1}/{max_iterations}]: {log_msg}")
                            except Exception:
                                pass
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
        logger.exception("Error calling Opus for hook debugging")
        return f"Error calling Opus sub-agent: {e}"


@beta_tool
def debug_hook(hook_id: str, annotation_id: str, schema_id: str | None = None) -> str:
    """Debug a Rossum hook using an Opus sub-agent. ALWAYS use this tool when debugging hook code errors.

    This is the PRIMARY tool for debugging Python function hooks. Simply pass the hook ID and annotation ID,
    and the Opus sub-agent will fetch the data and debug the hook.

    The tool:
    1. Fetches hook code and annotation data via MCP tools
    2. Executes and analyzes errors with Claude Opus for deep reasoning
    3. Iteratively fixes and verifies the code works
    4. Returns detailed analysis with working code

    Args:
        hook_id: The hook ID (from get_hook or hook URL). The sub-agent will fetch the code.
        annotation_id: The annotation ID to use for testing. The sub-agent will fetch the data.
        schema_id: Optional schema ID if schema context is needed.

    Returns:
        JSON with Opus expert analysis including fixed code.
    """
    start_time = time.perf_counter()

    if not hook_id:
        return json.dumps(
            {"error": "No hook_id provided", "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3)}
        )

    if not annotation_id:
        return json.dumps(
            {"error": "No annotation_id provided", "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3)}
        )

    logger.info(f"debug_hook: Calling Opus sub-agent for hook_id={hook_id}, annotation_id={annotation_id}")
    analysis = _call_opus_for_debug(hook_id, annotation_id, schema_id)

    response = {
        "hook_id": hook_id,
        "annotation_id": annotation_id,
        "analysis": analysis,
        "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
    }

    return json.dumps(response, ensure_ascii=False, default=str)


@beta_tool
def load_skill(name: str) -> str:
    """Load a specialized skill that provides domain-specific instructions and workflows.

    Use this tool when you recognize that a task matches one of the available skills.
    The skill will provide detailed instructions, workflows, and context for the task.

    Available skills:
    - rossum-deployment: Safe workflow for creating and deploying Rossum configurations.
      Provides access to deployment tools: deploy_pull, deploy_diff, deploy_push,
      deploy_copy_org, deploy_copy_workspace, deploy_to_org.
      **LOAD THIS SKILL WHEN:**
      - Creating new queues, schemas, hooks, or extensions
      - Setting up document splitting, sorting, or automation
      - Deploying configuration changes
      - Copying configurations between organizations
      - Any configuration task that modifies Rossum resources

    Args:
        name: The name of the skill to load (e.g., "rossum-deployment").

    Returns:
        The skill instructions and workflows, or an error if skill not found.
    """
    skill = get_skill(name)
    if skill is None:
        available = get_skill_registry().get_skill_names()
        return json.dumps({"status": "error", "message": f"Skill '{name}' not found.", "available_skills": available})

    return json.dumps({"status": "success", "skill_name": skill.name, "instructions": skill.content})


INTERNAL_TOOLS: list[BetaTool[..., str]] = [
    write_file,
    search_knowledge_base,
    evaluate_python_hook,
    debug_hook,
    load_skill,
    spawn_mcp_connection,
    call_on_connection,
    close_connection,
]


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
