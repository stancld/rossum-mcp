"""Hook debugging tools for the Rossum Agent.

This module provides tools for debugging Rossum Python function hooks, including sandboxed execution
and an Opus sub-agent for iterative debugging.
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
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from anthropic import beta_tool

from rossum_agent.bedrock_client import create_bedrock_client
from rossum_agent.tools.core import (
    SubAgentProgress,
    get_mcp_connection,
    get_mcp_event_loop,
    get_output_dir,
    report_progress,
)
from rossum_agent.tools.knowledge_base import (
    OPUS_MODEL_ID,
    WebSearchError,
    _call_opus_for_web_search_analysis,
    search_knowledge_base,
)

logger = logging.getLogger(__name__)

_WEB_SEARCH_NO_RESULTS = "__NO_RESULTS__"


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


def _extract_and_analyze_web_search_results(block: Any, iteration: int, max_iterations: int) -> dict[str, Any] | None:
    """Extract web search results and analyze with Opus sub-agent.

    Args:
        block: The response content block to process.
        iteration: Current iteration number for logging.
        max_iterations: Maximum iterations for logging.

    Returns:
        Tool result dict with analyzed search results, or None if not a web search block.
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
    query = getattr(block, "search_query", "Rossum documentation")
    logger.info(f"debug_hook sub-agent [iter {iteration}/{max_iterations}]: analyzing with Opus sub-agent")
    analyzed_results = _call_opus_for_web_search_analysis(query, full_results)
    return {
        "type": "tool_result",
        "tool_use_id": block.id,
        "content": f"Analyzed Rossum Knowledge Base search results:\n\n{analyzed_results}",
    }


def _call_mcp_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Call an MCP tool synchronously from within a thread.

    This uses run_coroutine_threadsafe to call async MCP tools from sync context.
    """
    mcp_connection = get_mcp_connection()
    mcp_event_loop = get_mcp_event_loop()
    if mcp_connection is None or mcp_event_loop is None:
        raise RuntimeError("MCP connection not set. Call set_mcp_connection first.")

    future = asyncio.run_coroutine_threadsafe(mcp_connection.call_tool(name, arguments), mcp_event_loop)
    return future.result(timeout=60)


_ALLOWED_BUILTIN_NAMES = {
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
    "Exception",
    "ValueError",
    "TypeError",
    "KeyError",
    "IndexError",
    "RuntimeError",
    "AttributeError",
    "print",
}

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

_GET_HOOK_TOOL: dict[str, Any] = {
    "name": "get_hook",
    "description": "Fetch a Rossum hook by ID. Returns the hook object with config.code containing the Python code.",
    "input_schema": {
        "type": "object",
        "properties": {"hook_id": {"type": "string", "description": "The hook ID (numeric string)"}},
        "required": ["hook_id"],
    },
}

_GET_ANNOTATION_TOOL: dict[str, Any] = {
    "name": "get_annotation",
    "description": "Fetch a Rossum annotation by ID. Returns the annotation object with content containing datapoints.",
    "input_schema": {
        "type": "object",
        "properties": {"annotation_id": {"type": "string", "description": "The annotation ID (numeric string)"}},
        "required": ["annotation_id"],
    },
}

_GET_SCHEMA_TOOL: dict[str, Any] = {
    "name": "get_schema",
    "description": "Fetch a Rossum schema by ID. Returns the schema definition.",
    "input_schema": {
        "type": "object",
        "properties": {"schema_id": {"type": "string", "description": "The schema ID (numeric string)"}},
        "required": ["schema_id"],
    },
}

_EVALUATE_HOOK_TOOL: dict[str, Any] = {
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
            "annotation_json": {"type": "string", "description": "JSON string of annotation data"},
            "schema_json": {"type": "string", "description": "Optional JSON string of schema data"},
        },
        "required": ["code", "annotation_json"],
    },
}

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

_OPUS_TOOLS: list[dict[str, Any]] = [
    _GET_HOOK_TOOL,
    _GET_ANNOTATION_TOOL,
    _GET_SCHEMA_TOOL,
    _EVALUATE_HOOK_TOOL,
    _SEARCH_KNOWLEDGE_BASE_TOOL,
]


def _strip_imports(code: str) -> str:
    """Strip import statements from code since they're not allowed in sandbox."""
    result = []
    for line in code.split("\n"):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            continue
        result.append(line)
    return "\n".join(result)


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
        exc_info = {"type": exc.__class__.__name__, "message": str(exc), "traceback": traceback.format_exc()}
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
        if not (query := tool_input.get("query", "")):
            return json.dumps({"status": "error", "message": "Query is required"})
        kb_result: str = search_knowledge_base(query)
        return kb_result
    if tool_name in ("get_hook", "get_annotation", "get_schema"):
        mcp_result = _call_mcp_tool(tool_name, tool_input)
        return json.dumps(mcp_result, indent=2, default=str) if mcp_result else "No data returned"
    return f"Unknown tool: {tool_name}"


def _call_opus_for_debug(hook_id: str, annotation_id: str, schema_id: str | None) -> str:
    """Call Opus model for hook debugging with tool use for iterative testing."""
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

            report_progress(
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

            has_tool_use = any(hasattr(block, "type") and block.type == "tool_use" for block in response.content)

            if response.stop_reason == "end_of_turn" or not has_tool_use:
                logger.info(
                    f"debug_hook sub-agent: completed after {iteration + 1} iterations (stop_reason={response.stop_reason}, has_tool_use={has_tool_use})"
                )
                report_progress(
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
                web_result = _extract_and_analyze_web_search_results(block, iteration + 1, max_iterations)
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

                    report_progress(
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
                                logger.debug("Failed to parse tool result for logging")
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
        return _make_evaluate_response("invalid_input", start_time, stderr="No code provided")

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

    payload: dict[str, Any] = {"annotation": annotation}
    if schema is not None:
        payload["schema"] = schema

    safe_builtins: dict[str, object] = {
        name: getattr(builtins, name) for name in _ALLOWED_BUILTIN_NAMES if hasattr(builtins, name)
    }

    exec_namespace: dict[str, Any] = {
        "__builtins__": safe_builtins,
        "collections": collections,
        "datetime": dt,
        "decimal": decimal,
        "Decimal": Decimal,
        "InvalidOperation": InvalidOperation,
        "functools": functools,
        "itertools": itertools,
        "json": json,
        "math": math,
        "re": re,
        "string": string,
    }

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    clean_code = _strip_imports(code)

    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(clean_code, exec_namespace)

            handler = exec_namespace.get("rossum_hook_request_handler")
            if handler is None or not callable(handler):
                raise RuntimeError(
                    "No callable `rossum_hook_request_handler` found. "
                    "Define it as `def rossum_hook_request_handler(payload): ...`"
                )

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
