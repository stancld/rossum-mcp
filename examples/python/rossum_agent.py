#!/usr/bin/env python3
"""Rossum Document Processing Agent

AI agent that interacts with the Rossum MCP server to upload and process documents.

Usage:
    python rossum_agent.py

Environment Variables:
    ROSSUM_API_TOKEN: Rossum API authentication token
    ROSSUM_API_BASE_URL: Rossum API base URL
    LLM_API_BASE_URL: LLM API endpoint URL
    LLM_MODEL_ID: (Optional) LLM model identifier
"""

import argparse
import importlib.resources
import os
import sys

import yaml
from file_system_tools import get_file_info, list_files, read_file
from plot_tools import plot_data
from rossum_agent_tools import parse_annotation_content, rossum_mcp_tool
from smolagents import CodeAgent, LiteLLMModel

# Constants
DEFAULT_LLM_MODEL = "openai/Qwen/Qwen3-Next-80B-A3B-Instruct-FP8"


def create_agent(stream_outputs: bool = False) -> CodeAgent:
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
- rossum_mcp_tool, parse_annotation_content, list_files, read_file, get_file_info

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

IMPORTANT: Parsing Annotation Content and Datapoints:
Use the 'parse_annotation_content' tool to extract datapoints and line items from annotations.
DO NOT write manual parsing code - use the tool instead.

CRITICAL FOR LINE ITEMS:
- Use 'extract_line_items' operation to get line items as a LIST
- DO NOT use 'extract_all_datapoints' for line items - it flattens the structure and loses line item grouping!
- 'extract_all_datapoints' only keeps the LAST value of each field, destroying the line item associations

When you get an annotation with `content` sideload:
- annotation['content'] is a list representing the document structure
- Use parse_annotation_content tool to extract data efficiently

RECOMMENDED APPROACH - Use parse_annotation_content tool:
```python
import json
from rossum_api.models.annotation import Annotation

# Get annotation with content sideload
ann_json = rossum_mcp_tool('get_annotation', json.dumps({'annotation_id': 12345, 'sideloads': ['content']}))
annotation = Annotation(**json.loads(ann_json))

# Extract all datapoints at once
all_fields_json = parse_annotation_content(json.dumps(annotation.content), 'extract_all_datapoints')
all_fields = json.loads(all_fields_json)
# Result: {'sender_name': 'Acme Corp', 'amount_total': '1500.00', ...}

# Extract single datapoint
sender_json = parse_annotation_content(
    json.dumps(annotation.content),
    'get_datapoint_value',
    schema_id='sender_name'
)
sender_data = json.loads(sender_json)
sender_name = sender_data['value']

# Extract line items (multivalue field) - CRITICAL: USE extract_line_items!
# WARNING: DO NOT use 'extract_all_datapoints' for line items - it will lose the grouping!
line_items_json = parse_annotation_content(
    json.dumps(annotation.content),
    'extract_line_items',  # Use THIS operation for line items!
    multivalue_schema_id='line_items'
)
line_items = json.loads(line_items_json)
# Result: [{'item_description': 'Item 1', 'item_amount_total': '100'}, ...]

# Process each line item individually
for item in line_items:
    desc = item.get('item_description')
    amount_str = item.get('item_amount_total', '0')
    # Clean amount string (remove spaces, convert to float)
    amount = float(amount_str.replace(' ', '').replace(',', '')) if amount_str else 0.0
    print(f"Description: {desc}, Amount: {amount}")
```

Common Field Schema IDs in Invoice Schemas:
- 'document_id' or 'invoice_id': Invoice number
- 'sender_name' or 'vendor_name': Supplier/vendor name
- 'date_issue' or 'invoice_date': Invoice date
- 'amount_total' or 'total_amount': Total amount
- 'currency': Currency code
- 'line_items': Multivalue containing line items (inside 'line_items_section')
  - Common children: 'item_description', 'item_quantity', 'item_amount_total', 'item_rate'

IMPORTANT: Always check if field exists before accessing:
- Use .get() method to avoid KeyError
- Remember: datapoint['content']['value'], NOT datapoint['value']
- Check if value is None or empty string
- Some fields may not be extracted or confirmed yet
"""

    prompt_templates["system_prompt"] += "\n" + custom_instructions

    return CodeAgent(
        tools=[rossum_mcp_tool, parse_annotation_content, list_files, read_file, get_file_info, plot_data],
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
        stream_outputs=stream_outputs,
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-hardcoded-prompt", action="store_true")
    parser.add_argument("--stream-outputs", action="store_true")
    return parser.parse_args()


def main(args: argparse.Namespace) -> None:
    """Main entry point - run interactive agent CLI."""
    print("🤖 Rossum Invoice Processing Agent")
    print("=" * 50)

    _check_env_vars()

    print("\n🔧 Initializing agent...")
    agent = create_agent(args.stream_outputs)

    print("\n" + "=" * 50)
    print("Agent ready! You can now give instructions.")
    print("Example: 'Upload all invoices from the data folder'")
    print("Type 'quit' to exit")
    print("=" * 50 + "\n")

    if args.use_hardcoded_prompt:
        prompt = """1. Upload all invoices from `/Users/daniel.stancl/projects/rossum-mcp/examples/data` folder to Rossum to the queue 3901094.
    - Do not include documents from `knowledge` folder.
2. Once you send all annotations, wait for a few seconds.
3. Then, start checking annotation status. Once all are imported, return a list of all annotations_urls
4. Fetch the schema for the target queue.
5. Identify the schema field IDs for:
    - Line item description field
    - Line item total amount field
6. Retrieve all annotations in 'to_review' state from queue 3901094
7. For each document:
    - Extract all line items
    - Create a dictionary mapping {item_description: item_amount_total}
    - If multiple line items share the same description, sum their amounts
    - Print result for each document
8. Aggregate across all documents: sum amounts for each unique description
9. Return the final dictionary: {description: total_amount_across_all_docs}
10. Using the retrieved data, generate bar plot displaying revenue by services. Sort it in descending order. Store it interactive `revenue.html`.

Proceed step-by-step and show intermediate results after each major step."""

        agent.run(prompt)

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
    main(parse_args())
