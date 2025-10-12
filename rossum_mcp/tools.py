"""Rossum Agent Tools

Collection of tools for AI agents working with Rossum MCP server.
Provides interfaces for MCP operations and annotation content parsing.

Note:
    This module requires the 'tools' extra to be installed:
    pip install rossum-mcp[tools]
"""

import asyncio
import json
import os
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

try:
    from smolagents import tool
except ImportError as e:
    raise ImportError(
        "The 'smolagents' package is required to use rossum_mcp.tools. Install it with: pip install rossum-mcp[tools]"
    ) from e


@tool
def rossum_mcp_tool(operation: str, arguments: str = "{}") -> str:
    """Interface to Rossum MCP server for document processing.

    Args:
        operation: MCP operation name. Available:
            - 'upload_document': Upload document (requires: file_path, queue_id)
            - 'list_annotations': List annotations with optional filtering (requires: queue_id, optional: status)
            - 'get_annotation': Get annotation details (requires: annotation_id, optional: sideloads)
                sideloads=['content'] is used to necessary to get a annotation content, not only its URL.
                Output can be deserialized with `ann = Annotation(**json.loads(...))` for further processing.
                Annotation content is then access as `ann.content`.
            - 'get_queue': Get queue details including schema_id (requires: queue_id)
            - 'get_schema': Get schema details (requires: schema_id)
            - 'get_queue_schema': Get complete schema for a queue in one call (requires: queue_id) - RECOMMENDED
        arguments: JSON string of operation arguments.
            MUST use json.dumps() to convert dict to JSON string.
            IDs (queue_id, annotation_id, schema_id) must be integers, not strings.

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

        # Get queue schema (recommended approach)
        schema_result = rossum_mcp_tool("get_queue_schema",
                                       json.dumps({"queue_id": 12345}))
        schema_data = json.loads(schema_result)
        if "error" not in schema_data:
            schema_content = schema_data.get("schema_content")
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


def _get_datapoint_value(items: list, schema_id: str) -> Any:
    """Recursively search for a datapoint value by schema_id"""
    for item in items:
        if item.get("category") == "datapoint" and item.get("schema_id") == schema_id:
            return item.get("content", {}).get("value")

        if "children" in item:
            result = _get_datapoint_value(item["children"], schema_id)
            if result is not None:
                return result
    return None


def _extract_all_datapoints(items: list) -> dict:
    """Recursively extract all datapoints from content structure"""
    datapoints = {}
    for item in items:
        if item.get("category") == "datapoint":
            schema_id = item.get("schema_id")
            value = item.get("content", {}).get("value")
            datapoints[schema_id] = value

        if "children" in item:
            datapoints.update(_extract_all_datapoints(item["children"]))

    return datapoints


def _extract_multivalue(items: list, multivalue_schema_id: str) -> list[dict[Any, Any]] | None:
    """Extract items from a multivalue field by schema_id"""
    for item in items:
        if item.get("category") == "multivalue" and item.get("schema_id") == multivalue_schema_id:
            result: list[dict[Any, Any]] = []
            for tuple_item in item.get("children", []):
                if tuple_item.get("category") == "tuple":
                    item_data: dict[Any, Any] = {}
                    for datapoint in tuple_item.get("children", []):
                        if datapoint.get("category") == "datapoint":
                            schema_id = datapoint.get("schema_id")
                            value = datapoint.get("content", {}).get("value")
                            item_data[schema_id] = value
                    result.append(item_data)
            return result

        if "children" in item:
            nested_result = _extract_multivalue(item["children"], multivalue_schema_id)
            if nested_result is not None:
                return nested_result

    return None


@tool
def parse_annotation_content(
    annotation_content_json: str, operation: str = "extract_all_datapoints", **kwargs: Any
) -> str:
    """Parse Rossum annotation content to extract datapoints and line items.

    This tool provides utilities for parsing annotation content structure.
    Use this instead of writing manual parsing code in your scripts.

    Args:
        annotation_content_json: JSON string of annotation content (list of items).
            Get this from: json.dumps(annotation.content) where annotation is from get_annotation
        operation: Parsing operation to perform. Available:
            - 'extract_all_datapoints': Extract all datapoints into {schema_id: value} dict
            - 'get_datapoint_value': Get single datapoint value by schema_id (requires: schema_id)
            - 'extract_line_items': Extract line items from multivalue field (requires: multivalue_schema_id)
            - 'extract_multivalue': Extract any multivalue field by schema_id (requires: multivalue_schema_id)
        kwargs: Additional arguments based on operation:
            - schema_id: For 'get_datapoint_value' operation
            - multivalue_schema_id: For 'extract_line_items' or 'extract_multivalue' operations

    Returns:
        JSON string with parsed data. Use json.loads() to parse.

    Examples:
        # Extract all datapoints
        result = parse_annotation_content(json.dumps(annotation.content), 'extract_all_datapoints')
        all_fields = json.loads(result)  # {'sender_name': 'Acme', 'amount_total': '1500.00', ...}

        # Get single datapoint value
        result = parse_annotation_content(
            json.dumps(annotation.content),
            'get_datapoint_value',
            schema_id='sender_name'
        )
        sender = json.loads(result)  # {'value': 'Acme Corp'}

        # Extract line items
        result = parse_annotation_content(
            json.dumps(annotation.content),
            'extract_line_items',
            multivalue_schema_id='line_items'
        )
        line_items = json.loads(result)  # [{'item_description': 'Item 1', 'item_amount_total': '100'}, ...]
    """
    try:
        content = json.loads(annotation_content_json)

        match operation:
            case "extract_all_datapoints":
                result = _extract_all_datapoints(content)
                return json.dumps(result, indent=2)

            case "get_datapoint_value":
                schema_id = kwargs.get("schema_id")
                if not schema_id:
                    return json.dumps(
                        {"error": "Missing required argument 'schema_id' for operation 'get_datapoint_value'"}
                    )
                value = _get_datapoint_value(content, schema_id)
                return json.dumps({"schema_id": schema_id, "value": value}, indent=2)

            case "extract_line_items" | "extract_multivalue":
                multivalue_schema_id = kwargs.get("multivalue_schema_id")
                if not multivalue_schema_id:
                    return json.dumps(
                        {"error": f"Missing required argument 'multivalue_schema_id' for operation '{operation}'"}
                    )
                multivalue_result = _extract_multivalue(content, multivalue_schema_id)
                return json.dumps(multivalue_result if multivalue_result is not None else [], indent=2)

            case _:
                return json.dumps(
                    {
                        "error": f"Unknown operation: {operation}. Available: extract_all_datapoints, get_datapoint_value, extract_line_items, extract_multivalue"
                    }
                )

    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON in annotation_content_json: {e!s}"})
    except Exception as e:
        return json.dumps({"error": f"Parsing error: {e!s}"})


async def _execute_operation(operation: str, arguments: dict[str, Any]) -> str:
    """Execute Rossum MCP operation via stdio client."""
    server_params = StdioServerParameters(
        command="rossum-mcp",
        args=[],
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
