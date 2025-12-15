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
import time
import traceback
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from anthropic import beta_tool

from rossum_agent.bedrock_client import create_bedrock_client
from rossum_agent.utils import get_session_output_dir

if TYPE_CHECKING:
    from anthropic._tools import BetaTool

    from rossum_agent.mcp_tools import MCPConnection

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
    """Text output from a sub-agent for streaming."""

    tool_name: str
    text: str
    is_final: bool = False


# Type alias for progress callback
SubAgentProgressCallback = Callable[[SubAgentProgress], None]
SubAgentTextCallback = Callable[[SubAgentText], None]

# Module-level progress callback for sub-agent progress reporting
_progress_callback: SubAgentProgressCallback | None = None
_text_callback: SubAgentTextCallback | None = None


def set_progress_callback(callback: SubAgentProgressCallback | None) -> None:
    """Set the progress callback for sub-agent progress reporting.

    Args:
        callback: Callback function called with SubAgentProgress updates.
    """
    global _progress_callback
    _progress_callback = callback


def set_text_callback(callback: SubAgentTextCallback | None) -> None:
    """Set the text callback for sub-agent text streaming.

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


def set_mcp_connection(connection: MCPConnection, loop: asyncio.AbstractEventLoop) -> None:
    """Set the MCP connection for use by internal tools.

    Args:
        connection: The MCP connection to use for tool calls.
        loop: The event loop where the MCP connection was created.
    """
    global _mcp_connection, _mcp_event_loop
    _mcp_connection = connection
    _mcp_event_loop = loop


def _call_mcp_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Call an MCP tool synchronously from within a thread.

    This uses run_coroutine_threadsafe to call async MCP tools from sync context.
    """
    if _mcp_connection is None or _mcp_event_loop is None:
        raise RuntimeError("MCP connection not set. Call set_mcp_connection first.")

    future = asyncio.run_coroutine_threadsafe(_mcp_connection.call_tool(name, arguments), _mcp_event_loop)
    return future.result(timeout=60)


# Debug file for tracing debug_hook execution
_DEBUG_LOG_FILE = Path("/tmp/debug_hook_trace.log")


def _debug_log(msg: str) -> None:
    """Write debug message to file with timestamp."""
    import datetime as dt  # noqa: PLC0415 - intentionally imported inside function to avoid import at module load

    timestamp = dt.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    with open(_DEBUG_LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")
        f.flush()


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
analyze the code, identify issues, and FIX THEM by iteratively testing with the evaluate_python_hook tool.

## Available Tools

You have access to:
1. `get_hook` - Fetch hook code by ID. The code is in `config.code`.
2. `get_annotation` - Fetch annotation data by ID. Use `content` for datapoints.
3. `get_schema` - Optionally fetch schema by ID.
4. `evaluate_python_hook` - Execute hook code against annotation data.

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

## Your Task - ITERATIVE DEBUGGING

You MUST follow this process:

1. **Fetch data**: Call `get_hook` and `get_annotation` to get the hook code and annotation data.
2. **Analyze**: Understand what the hook is supposed to do.
3. **Execute**: Use `evaluate_python_hook` tool to run the code and see the actual error.
4. **Fix**: Based on the execution result, write corrected code.
5. **Verify**: Use `evaluate_python_hook` again to confirm your fix works (status="success").
6. **Repeat**: If still failing, iterate until you have working code.

IMPORTANT: You MUST call `evaluate_python_hook` at least once to verify your fix works before providing \
your final answer. Do not just analyze - actually execute the code!

## Final Output Format

After your iterative debugging, provide:

1. **What the hook does**: Brief explanation of the hook's intended purpose.
2. **Issues found**: List specific problems you discovered through execution.
3. **Root cause**: Explain why the error(s) occurred based on actual execution results.
4. **Fixed code**: The complete, working code that you have VERIFIED by executing it.
5. **Verification**: Show the successful execution result proving your fix works.

Be concise but thorough. Your primary goal is to provide WORKING code, verified by actual execution."""


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

# All tools available to the Opus sub-agent
_OPUS_TOOLS = [_GET_HOOK_TOOL, _GET_ANNOTATION_TOOL, _GET_SCHEMA_TOOL, _EVALUATE_HOOK_TOOL]


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
    _debug_log("Starting sub-agent for hook analysis...")
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
            _debug_log(f"Sub-agent iteration {iteration + 1}/{max_iterations}")

            _report_progress(
                SubAgentProgress(
                    tool_name="debug_hook", iteration=iteration + 1, max_iterations=max_iterations, status="thinking"
                )
            )

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
                _debug_log(f"Sub-agent completed after {iteration + 1} iterations")
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
            for block in response.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    iteration_tool_calls.append(tool_name)
                    logger.info(
                        f"debug_hook sub-agent [iter {iteration + 1}/{max_iterations}]: calling tool '{tool_name}'"
                    )
                    _debug_log(f"Calling tool '{tool_name}'")

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
                                _debug_log(log_msg)
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
def debug_hook(
    hook_id: str,
    annotation_id: str,
    schema_id: str | None = None,
) -> str:
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
    _debug_log("ENTERED debug_hook function")
    start_time = time.perf_counter()

    if not hook_id:
        return json.dumps(
            {"error": "No hook_id provided", "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3)}
        )

    if not annotation_id:
        return json.dumps(
            {"error": "No annotation_id provided", "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3)}
        )

    _debug_log(f"Calling sub-agent with hook_id={hook_id}, annotation_id={annotation_id}, schema_id={schema_id}")
    logger.info(f"debug_hook: Calling Opus sub-agent for hook_id={hook_id}, annotation_id={annotation_id}")
    analysis = _call_opus_for_debug(hook_id, annotation_id, schema_id)

    response = {
        "hook_id": hook_id,
        "annotation_id": annotation_id,
        "analysis": analysis,
        "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
    }

    return json.dumps(response, ensure_ascii=False, default=str)


INTERNAL_TOOLS: list[BetaTool[..., str]] = [write_file, evaluate_python_hook, debug_hook]


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
