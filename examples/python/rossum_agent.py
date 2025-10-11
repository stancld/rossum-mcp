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
- OUTPUT: Parse result with json.loads() to get a dict
- IMPORTANT: When getting annotations, deserialize the dict into Annotation object:
  from rossum_api.models.annotation import Annotation
  annotation = Annotation(**json.loads(ann_json))

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

IMPORTANT: Fetching N annotations from a queue:
When asked to fetch N annotations from a queue:
1. Call 'list_annotations' with the queue_id and optionally limit the results
2. Iterate through the returned annotations (up to N items)
3. For each annotation, perform required operations (extract data, process fields, etc.)

Example pattern:
```python
import json

# Fetch N annotations from a queue
annotations_json = rossum_mcp_tool('list_annotations', json.dumps({'queue_id': 12345}))
annotations_data = json.loads(annotations_json)

# Iterate through first N annotations
for annotation in annotations_data.get('results', [])[:N]:
    annotation_id = annotation['id']
    # Process each annotation as needed
    ann_json = rossum_mcp_tool('get_annotation', json.dumps({'annotation_id': annotation_id, 'sideloads': ['content']}))
    ann_data = json.loads(ann_json)
```

IMPORTANT: Accessing Annotation Content and Datapoints:
When you get an annotation with `content` as a sideload, the response includes a 'content' field.
This content is a LIST of items representing the document structure (sections, datapoints, multivalues).

Annotation Content Structure:
- annotation['content'] is a list of dictionaries
- Each dictionary has these key fields:
  * 'category': Type of item - 'section', 'datapoint', 'multivalue', or 'tuple'
  * 'schema_id': Schema identifier for the field
  * 'children': List of nested items (for section/multivalue/tuple categories)
  * 'content': Dict with actual value and metadata (for datapoint category only)

CRITICAL: Datapoint Values Are Nested in 'content' Field:
- For datapoints: value is at datapoint['content']['value']
- NOT at datapoint['value'] (this will fail!)
- The 'content' dict also contains: page, position, rir_confidence, etc.
- IMPORTANT: Use only those fields with rir_confidence >= 0.6

Accessing Field Values - RECOMMENDED APPROACH:
```python
import json
from rossum_api.models.annotation import Annotation

# Get annotation with content sideload
ann_json = rossum_mcp_tool('get_annotation', json.dumps({'annotation_id': 12345, 'sideloads': ['content']}))
annotation = Annotation(**json.loads(ann_json))
content = annotation.content

# Method 1: Recursive search for datapoint by schema_id (RECOMMENDED)
def get_datapoint_value(items, schema_id):
    '''Recursively search for a datapoint value by schema_id'''
    for item in items:
        # Check if this is the datapoint we're looking for
        if item.get('category') == 'datapoint' and item.get('schema_id') == schema_id:
            return item.get('content', {}).get('value')

        # Recursively search in children (sections, multivalues, tuples)
        if 'children' in item:
            result = get_datapoint_value(item['children'], schema_id)
            if result is not None:
                return result
    return None

# Get single field values
sender_name = get_datapoint_value(content, 'sender_name')
invoice_date = get_datapoint_value(content, 'date_issue')
total_amount = get_datapoint_value(content, 'amount_total')

# Method 2: Direct iteration for all datapoints in content
def extract_all_datapoints(items):
    '''Recursively extract all datapoints from content structure'''
    datapoints = {}
    for item in items:
        if item.get('category') == 'datapoint':
            schema_id = item.get('schema_id')
            value = item.get('content', {}).get('value')
            if (item.get('content', {}).get('rir_confidence') or 0.0) > 0.6:
                datapoints[schema_id] = value

        # Recurse into children
        if 'children' in item:
            datapoints.update(extract_all_datapoints(item['children']))

    return datapoints

all_fields = extract_all_datapoints(content)
print(all_fields)  # {'sender_name': 'Acme Corp', 'amount_total': '1500.00', ...}
```

Handling Complex Fields (Multivalue/Line Items):
```python
# Find multivalue field (e.g., line_items)
def get_line_items(content):
    '''Extract line items from annotation content'''
    for item in content:
        # Line items are in a section, then multivalue
        if item.get('category') == 'section' and item.get('schema_id') == 'line_items_section':
            for child in item.get('children', []):
                if child.get('category') == 'multivalue' and child.get('schema_id') == 'line_items':
                    # Each child of multivalue is a tuple (one line item)
                    line_items = []
                    for tuple_item in child.get('children', []):
                        if tuple_item.get('category') == 'tuple':
                            # Extract all datapoints from this tuple
                            item_data = {}
                            for datapoint in tuple_item.get('children', []):
                                if datapoint.get('category') == 'datapoint':
                                    schema_id = datapoint.get('schema_id')
                                    value = datapoint.get('content', {}).get('value')
                                    if (item.get('content', {}).get('rir_confidence') or 0.0) > 0.6:
                                        item_data[schema_id] = value
                            line_items.append(item_data)
                    return line_items
    return []

line_items = get_line_items(content)
for item in line_items:
    print(f"Description: {item.get('item_description')}, Amount: {item.get('item_amount')}")
```

Using Schema to Guide Extraction:
```python
# Get schema to know which fields to look for
import json
schema_json = rossum_mcp_tool('get_queue_schema', json.dumps({'queue_id': 12345}))
schema = json.loads(schema_json)
schema_content = schema.get('schema_content', [])

# Extract all datapoint schema_ids from schema (recursively)
def get_schema_field_ids(schema_items):
    field_ids = []
    for item in schema_items:
        if item.get('category') == 'datapoint':
            field_ids.append(item.get('id'))
        if 'children' in item:
            field_ids.extend(get_schema_field_ids(item['children']))
    return field_ids

field_ids = get_schema_field_ids(schema_content)

# Then fetch annotation and extract those specific fields
ann_json = rossum_mcp_tool('get_annotation', json.dumps({'annotation_id': 67890, 'sideloads': ['content']}))
annotation = Annotation(**json.loads(ann_json))

# Build result dict with all fields from schema
result = {}
for field_id in field_ids:
    result[field_id] = get_datapoint_value(annotation.content, field_id)
```

Common Field Schema IDs in Invoice Schemas:
- 'document_id' or 'invoice_id': Invoice number
- 'sender_name' or 'vendor_name': Supplier/vendor name
- 'date_issue' or 'invoice_date': Invoice date
- 'amount_total' or 'total_amount': Total amount
- 'currency': Currency code
- 'line_items': Multivalue containing line items (inside 'line_items_section')
  - Common children: 'item_description', 'item_quantity', 'item_amount', 'item_rate'

IMPORTANT: Always check if field exists before accessing:
- Use .get() method to avoid KeyError
- Remember: datapoint['content']['value'], NOT datapoint['value']
- Check if value is None or empty string
- Some fields may not be extracted or confirmed yet
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
            "rossum_api.models.annotation",
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
