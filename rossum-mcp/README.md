# Rossum MCP Server

<div align="center">

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-mcp/)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![MCP Tools](https://img.shields.io/badge/MCP_Tools-32-blue.svg)](#available-tools)
[![Rossum API](https://img.shields.io/badge/Rossum-API-orange.svg)](https://github.com/rossumai/rossum-api)

</div>

A Model Context Protocol (MCP) server that provides tools for uploading documents and retrieving annotations using the Rossum API. Built with Python and the official [rossum-api](https://github.com/rossumai/rossum-api).

## Features

### Document Processing
- **upload_document**: Upload a document to Rossum for processing
- **get_annotation**: Retrieve annotation data for a previously uploaded document
- **list_annotations**: List all annotations for a queue with optional filtering
- **start_annotation**: Start annotation to move it to 'reviewing' status
- **bulk_update_annotation_fields**: Bulk update annotation field values using JSON Patch operations
- **confirm_annotation**: Confirm annotation to move it to 'confirmed' status

### Queue & Schema Management
- **get_queue**: Retrieve queue details including schema_id
- **get_schema**: Retrieve schema details and content
- **get_queue_schema**: Retrieve complete schema for a queue in a single call
- **get_queue_engine**: Retrieve engine information for a queue
- **create_queue**: Create a new queue with schema and optional engine assignment
- **create_schema**: Create a new schema with sections and datapoints
- **update_queue**: Update queue settings including automation thresholds
- **update_schema**: Update schema with field-level automation thresholds

### Workspace Management
- **get_workspace**: Retrieve workspace details by ID
- **list_workspaces**: List all workspaces with optional filtering
- **create_workspace**: Create a new workspace

### Engine Management
- **get_engine**: Retrieve engine details by ID
- **list_engines**: List all engines with optional filters
- **create_engine**: Create a new engine (extractor or splitter)
- **update_engine**: Update engine settings including learning and training queues
- **create_engine_field**: Create engine fields and link them to schemas
- **get_engine_fields**: Retrieve engine fields for a specific engine or all engine fields

### Extensions & Rules
- **get_hook**: Get hook/extension details
- **list_hooks**: List webhooks and serverless functions (extensions)
- **create_hook**: Create webhooks or serverless function hooks for custom logic
- **get_rule**: Get business rule details
- **list_rules**: List business rules with trigger conditions and actions

### Relations Management
- **get_relation**: Retrieve relation details by ID
- **list_relations**: List all relations between annotations (edit, attachment, duplicate)
- **get_document_relation**: Retrieve document relation details by ID
- **list_document_relations**: List all document relations (export, einvoice)

## Prerequisites

- Python 3.12 or higher
- Rossum account with API credentials
- A Rossum queue ID

## Installation

### Docker (Recommended)

```bash
git clone https://github.com/stancld/rossum-mcp.git
cd rossum-mcp

# Set up environment variables
export ROSSUM_API_TOKEN="your-api-token"
export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
export ROSSUM_MCP_MODE="read-write"  # Optional: "read-only" or "read-write" (default)

# Run the MCP server
docker-compose up rossum-agent
```

<details>
<summary>Install from source (alternative)</summary>

```bash
git clone https://github.com/stancld/rossum-mcp.git
cd rossum-mcp/rossum-mcp
uv sync
```

Install with extras:
```bash
uv sync --extra all  # All extras (docs, tests)
uv sync --extra docs  # Documentation only
uv sync --extra tests  # Testing only
```

</details>

### Environment Variables

- **ROSSUM_API_TOKEN** (required): Your Rossum API authentication token
- **ROSSUM_API_BASE_URL** (required): Base URL for the Rossum API
- **ROSSUM_MCP_MODE** (optional): Controls which tools are available
  - `read-write` (default): All tools available (GET, LIST, CREATE, UPDATE operations)
  - `read-only`: Only read operations available (GET and LIST operations only)

#### Read-Only vs Read-Write Mode

When `ROSSUM_MCP_MODE` is set to `read-only`, only read operations are available:
- **Annotations:** `get_annotation`, `list_annotations`
- **Queues:** `get_queue`, `get_queue_schema`, `get_queue_engine`
- **Schemas:** `get_schema`
- **Engines:** `get_engine`, `list_engines`, `get_engine_fields`
- **Hooks:** `get_hook`, `list_hooks`
- **Rules:** `get_rule`, `list_rules`
- **Relations:** `get_relation`, `list_relations`
- **Document Relations:** `get_document_relation`, `list_document_relations`
- **Workspaces:** `get_workspace`, `list_workspaces`

All CREATE, UPDATE, and UPLOAD operations are disabled in read-only mode for security purposes.

## Usage

<details>
<summary>Running the MCP Server</summary>

Start the server using:
```bash
python server.py
```

Or using the installed script:
```bash
rossum-mcp
```

</details>

<details>
<summary>Claude Desktop Configuration</summary>

Configure your MCP client to use this server. In Claude Desktop's config:

**Read-write mode:**
```json
{
  "mcpServers": {
    "rossum": {
      "command": "python",
      "args": ["/path/to/rossum-mcp/rossum-mcp/rossum_mcp/server.py"],
      "env": {
        "ROSSUM_API_TOKEN": "your-api-token",
        "ROSSUM_API_BASE_URL": "https://api.elis.rossum.ai/v1",
        "ROSSUM_MCP_MODE": "read-write"
      }
    }
  }
}
```

**Read-only mode:**
```json
{
  "mcpServers": {
    "rossum-readonly": {
      "command": "python",
      "args": ["/path/to/rossum-mcp/rossum-mcp/rossum_mcp/server.py"],
      "env": {
        "ROSSUM_API_TOKEN": "your-api-token",
        "ROSSUM_API_BASE_URL": "https://api.elis.rossum.ai/v1",
        "ROSSUM_MCP_MODE": "read-only"
      }
    }
  }
}
```

</details>

## Available Tools

### Document Processing

#### upload_document

Uploads a document to Rossum for processing. Returns a task ID. Use `list_annotations` to get the annotation ID.

**Parameters:**
- `file_path` (string, required): Absolute path to the document file
- `queue_id` (integer, required): Rossum queue ID where the document should be uploaded

**Returns:**
```json
{
  "task_id": "12345",
  "task_status": "created",
  "queue_id": 12345,
  "message": "Document upload initiated. Use `list_annotations` to find the annotation ID for this queue."
}
```

#### get_annotation

Retrieves annotation data for a previously uploaded document. Use this to check the status of a document.

**Parameters:**
- `annotation_id` (integer, required): The annotation ID obtained from list_annotations
- `sideloads` (array, optional): List of sideloads to include. Use `['content']` to fetch annotation content with datapoints

**Returns:**
```json
{
  "id": "12345",
  "status": "to_review",
  "url": "https://elis.rossum.ai/api/v1/annotations/12345",
  "schema": "67890",
  "modifier": "11111",
  "document": "22222",
  "content": [...],
  "created_at": "2024-01-01T00:00:00Z",
  "modified_at": "2024-01-01T00:00:00Z"
}
```

#### list_annotations

Lists all annotations for a queue with optional filtering. Useful for checking the status of multiple uploaded documents.

**Parameters:**
- `queue_id` (integer, required): Rossum queue ID to list annotations from
- `status` (string, optional): Filter by annotation status (default: 'importing,to_review,confirmed,exported')

**Returns:**
```json
{
  "count": 42,
  "results": [
    {
      "id": "12345",
      "status": "to_review",
      "url": "https://elis.rossum.ai/api/v1/annotations/12345",
      "document": "67890",
      "created_at": "2024-01-01T00:00:00Z",
      "modified_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### start_annotation

Starts an annotation to move it from 'importing' to 'reviewing' status. This is required before you can update annotation fields.

**Parameters:**
- `annotation_id` (integer, required): Rossum annotation ID to start

**Returns:**
```json
{
  "annotation_id": 12345,
  "message": "Annotation 12345 started successfully. Status changed to 'reviewing'."
}
```

#### bulk_update_annotation_fields

Bulk update annotation field values using JSON Patch operations. This is the correct way to update annotation field values. Must be called after `start_annotation`.

**Parameters:**
- `annotation_id` (integer, required): Rossum annotation ID to update
- `operations` (array, required): List of JSON Patch operations with format:
  ```json
  [
    {
      "op": "replace",
      "id": 1234,
      "value": {
        "content": {
          "value": "new_value",
          "page": 1,
          "position": [x, y, w, h]
        }
      }
    }
  ]
  ```

**Important:** Use the numeric datapoint `id` from `annotation.content`, NOT the `schema_id`.

**Returns:**
```json
{
  "annotation_id": 12345,
  "operations_count": 1,
  "message": "Annotation 12345 updated with 1 operations successfully."
}
```

#### confirm_annotation

Confirms an annotation to move it to 'confirmed' status. Can be called after `bulk_update_annotation_fields`.

**Parameters:**
- `annotation_id` (integer, required): Rossum annotation ID to confirm

**Returns:**
```json
{
  "annotation_id": 12345,
  "message": "Annotation 12345 confirmed successfully. Status changed to 'confirmed'."
}
```

### Queue & Schema Management

#### get_queue

Retrieves queue details including the schema_id.

**Parameters:**
- `queue_id` (integer, required): Rossum queue ID to retrieve

#### get_schema

Retrieves schema details including the schema content/structure.

**Parameters:**
- `schema_id` (integer, required): Rossum schema ID to retrieve

#### get_queue_schema

Retrieves the complete schema for a queue in a single call. This is the recommended way to get a queue's schema.

**Parameters:**
- `queue_id` (integer, required): Rossum queue ID

#### get_queue_engine

Retrieves the complete engine information for a given queue in a single call.

**Parameters:**
- `queue_id` (integer, required): Rossum queue ID

#### create_queue

Creates a new queue with schema and optional engine assignment.

**Parameters:**
- `name` (string, required): Name of the queue to create
- `workspace_id` (integer, required): Workspace ID where the queue should be created
- `schema_id` (integer, required): Schema ID to assign to the queue
- `engine_id` (integer, optional): Optional engine ID to assign for document processing
- Additional optional parameters for automation, locale, training, etc.

#### update_queue

Updates an existing queue's settings including automation thresholds.

**Parameters:**
- `queue_id` (integer, required): Queue ID to update
- `queue_data` (object, required): Dictionary containing queue fields to update

#### create_schema

Creates a new schema with sections and datapoints.

**Parameters:**
- `name` (string, required): Schema name
- `content` (array, required): Schema content array containing sections with datapoints. Must follow Rossum schema structure with sections containing children.

**Example content structure:**
```json
[
  {
    "category": "section",
    "id": "document_info",
    "label": "Document Information",
    "children": [
      {
        "category": "datapoint",
        "id": "document_type",
        "label": "Document Type",
        "type": "enum",
        "rir_field_names": [],
        "constraints": {"required": false},
        "options": [
          {"value": "invoice", "label": "Invoice"},
          {"value": "receipt", "label": "Receipt"}
        ]
      }
    ]
  }
]
```

**Returns:**
```json
{
  "id": 12345,
  "name": "My Schema",
  "url": "https://elis.rossum.ai/api/v1/schemas/12345",
  "content": [...],
  "message": "Schema 'My Schema' created successfully with ID 12345"
}
```

#### update_schema

Updates an existing schema, typically used to set field-level automation thresholds.

**Parameters:**
- `schema_id` (integer, required): Schema ID to update
- `schema_data` (object, required): Dictionary containing schema fields to update

### Engine Management

#### get_engine

Retrieves detailed information about a specific engine by its ID.

**Parameters:**
- `engine_id` (integer, required): Engine ID to retrieve

**Returns:**
```json
{
  "id": 12345,
  "name": "Invoice Extractor",
  "url": "https://elis.rossum.ai/api/v1/engines/12345",
  "type": "extractor",
  "learning_enabled": true,
  "training_queues": ["https://elis.rossum.ai/api/v1/queues/100", "https://elis.rossum.ai/api/v1/queues/200"],
  "description": "Extracts invoice data",
  "agenda_id": "agenda-123",
  "organization": "https://elis.rossum.ai/api/v1/organizations/10",
  "message": "Engine 'Invoice Extractor' (ID 12345) retrieved successfully"
}
```

**Example usage:**
```python
# Get engine details
engine = get_engine(engine_id=12345)
```

#### list_engines

Lists all engines with optional filtering.

**Parameters:**
- `id` (integer, optional): Filter by engine ID
- `engine_type` (string, optional): Filter by engine type ('extractor' or 'splitter')
- `agenda_id` (string, optional): Filter by agenda ID

**Returns:**
```json
{
  "count": 2,
  "results": [
    {
      "id": 12345,
      "name": "My Engine",
      "url": "https://elis.rossum.ai/api/v1/engines/12345",
      "type": "extractor",
      "learning_enabled": true,
      "training_queues": ["https://elis.rossum.ai/api/v1/queues/100"],
      "description": "Engine description",
      "agenda_id": "abc123",
      "organization": "https://elis.rossum.ai/api/v1/organizations/123"
    }
  ],
  "message": "Retrieved 2 engine(s)"
}
```

**Example usage:**
```python
# List all engines
all_engines = list_engines()

# List specific engine by ID
engine = list_engines(id=12345)

# List extractors only
extractors = list_engines(engine_type="extractor")

# List engines by agenda
agenda_engines = list_engines(agenda_id="abc123")
```

#### create_engine

Creates a new engine for document processing.

**Parameters:**
- `name` (string, required): Engine name
- `organization_id` (integer, required): Organization ID where the engine should be created
- `engine_type` (string, required): Engine type - either 'extractor' or 'splitter'

**Returns:**
```json
{
  "id": 12345,
  "name": "My Engine",
  "url": "https://elis.rossum.ai/api/v1/engines/12345",
  "type": "extractor",
  "organization": "https://elis.rossum.ai/api/v1/organizations/123",
  "message": "Engine 'My Engine' created successfully with ID 12345"
}
```

#### update_engine

Updates an existing engine's settings including learning and training queues.

**Parameters:**
- `engine_id` (integer, required): Engine ID to update
- `engine_data` (object, required): Dictionary containing engine fields to update
  - `name` (string): Engine name
  - `description` (string): Engine description
  - `learning_enabled` (boolean): Enable/disable learning
  - `training_queues` (array): List of queue URLs for training

**Example:**
```json
{
  "learning_enabled": true,
  "training_queues": [
    "https://elis.rossum.ai/api/v1/queues/12345",
    "https://elis.rossum.ai/api/v1/queues/67890"
  ]
}
```

**Returns:**
```json
{
  "id": 12345,
  "name": "My Engine",
  "url": "https://elis.rossum.ai/api/v1/engines/12345",
  "type": "extractor",
  "learning_enabled": true,
  "training_queues": [...],
  "description": "Engine description",
  "message": "Engine 'My Engine' (ID 12345) updated successfully"
}
```

#### get_hook

Retrieves details of a specific hook/extension by its ID.

**Parameters:**
- `hook_id` (integer, required): Hook ID

**Returns:**
```json
{
  "id": 12345,
  "name": "Validation Hook",
  "url": "https://elis.rossum.ai/api/v1/hooks/12345",
  "type": "webhook",
  "active": true,
  "queues": ["https://elis.rossum.ai/api/v1/queues/100"],
  "events": ["annotation_status", "annotation_content"],
  "config": {
    "url": "https://example.com/webhook",
    "secret": "***"
  },
  "settings": {},
  "extension_source": "rossum_store"
}
```

**Example usage:**
```python
# Get hook details
hook = get_hook(hook_id=12345)
```

#### list_hooks

Lists all hooks/extensions configured in your organization. Hooks (also called extensions) are webhooks or serverless functions that respond to Rossum events.

**Parameters:**
- `queue_id` (integer, optional): Filter hooks by queue ID
- `active` (boolean, optional): Filter by active status (true for active hooks, false for inactive)

**Returns:**
```json
{
  "count": 2,
  "results": [
    {
      "id": 12345,
      "name": "Validation Hook",
      "url": "https://elis.rossum.ai/api/v1/hooks/12345",
      "type": "webhook",
      "active": true,
      "queues": ["https://elis.rossum.ai/api/v1/queues/100"],
      "events": ["annotation_status", "annotation_content"],
      "config": {
        "url": "https://example.com/webhook",
        "secret": "***"
      },
      "extension_source": "rossum_store"
    }
  ]
}
```

**Example usage:**
```python
# List all hooks
all_hooks = list_hooks()

# List hooks for a specific queue
queue_hooks = list_hooks(queue_id=12345)

# List only active hooks
active_hooks = list_hooks(active=True)

# List inactive hooks for a queue
inactive_queue_hooks = list_hooks(queue_id=12345, active=False)
```

#### create_hook

Creates a new hook (webhook or serverless function). Hooks respond to Rossum events and can be used for custom validation, data enrichment, or integration with external systems.

**Parameters:**
- `name` (string, required): Hook name
- `type` (string, required): Hook type - either 'webhook' or 'function'
- `queues` (array, optional): List of queue URLs to attach the hook to. If not provided, hook applies to all queues
  - Format: `["https://api.elis.rossum.ai/v1/queues/12345"]`
- `events` (array, optional): List of events that trigger the hook. Common events:
  - `annotation_content.initialize` - When annotation is first created
  - `annotation_content.confirm` - When annotation is confirmed
  - `annotation_content.export` - When annotation is exported
  - `annotation_status` - When annotation status changes
  - `annotation_content` - When annotation content changes
  - `datapoint_value` - When individual field value changes
- `config` (object, optional): Hook configuration
  - For webhook: `{"url": "https://example.com/webhook"}`
  - For function: `{"runtime": "python3.12", "function": "import json\ndef rossum_hook_request_handler(payload):\n    return {}"}`
- `settings` (object, optional): Specific settings included in the payload when executing the hook
- `secret` (string, optional): Secret key for securing webhook requests

**Returns:**
```json
{
  "id": 12345,
  "name": "My Hook",
  "url": "https://elis.rossum.ai/api/v1/hooks/12345",
  "enabled": true,
  "queues": ["https://elis.rossum.ai/api/v1/queues/100"],
  "events": ["annotation_content.initialize"],
  "config": {"runtime": "python3.12", "function": "..."},
  "settings": {"custom_key": "custom_value"},
  "message": "Hook 'My Hook' created successfully with ID 12345"
}
```

**Example usage:**
```python
# Create a serverless function hook
create_hook(
    name="Splitting & Sorting",
    type="function",
    queues=["https://api.elis.rossum.ai/v1/queues/12345"],
    events=["annotation_content.initialize", "annotation_content.confirm"],
    config={"runtime": "python3.12", "function": "import json\ndef rossum_hook_request_handler(payload):\n    return {}"},
    settings={"sorting_queues": {"A": 1, "B": 2}}
)

# Create a webhook hook
create_hook(
    name="External Validation",
    type="webhook",
    queues=["https://api.elis.rossum.ai/v1/queues/12345"],
    events=["annotation_content.confirm"],
    config={"url": "https://example.com/validate"},
    secret="webhook_secret_123"
)
```

#### create_engine_field

Creates a new engine field and links it to schemas. Engine fields define what data the engine extracts and must be created for each field in the schema when setting up an engine.

**Parameters:**
- `engine_id` (integer, required): Engine ID to which this field belongs
- `name` (string, required): Field name (slug format, max 50 chars)
- `label` (string, required): Human-readable label (max 100 chars)
- `field_type` (string, required): Field type - 'string', 'number', 'date', or 'enum'
- `schema_ids` (array, required): List of schema IDs to link this engine field to (at least one required)
- `tabular` (boolean, optional): Whether this field is in a table (default: false)
- `multiline` (string, optional): Multiline setting - 'true', 'false', or '' (default: 'false')
- `subtype` (string, optional): Optional field subtype (max 50 chars)
- `pre_trained_field_id` (string, optional): Optional pre-trained field ID (max 50 chars)

**Returns:**
```json
{
  "id": 12345,
  "name": "invoice_number",
  "label": "Invoice Number",
  "url": "https://elis.rossum.ai/api/v1/engine_fields/12345",
  "type": "string",
  "engine": "https://elis.rossum.ai/api/v1/engines/123",
  "tabular": false,
  "multiline": "false",
  "schema_ids": [456, 789],
  "message": "Engine field 'Invoice Number' created successfully with ID 12345 and linked to 2 schema(s)"
}
```

#### get_engine_fields

Retrieves engine fields for a specific engine or all engine fields.

**Parameters:**
- `engine_id` (integer, optional): Engine ID to filter fields by. If not provided, retrieves all engine fields.

**Returns:**
```json
{
  "count": 2,
  "results": [
    {
      "id": 12345,
      "url": "https://elis.rossum.ai/api/v1/engine_fields/12345",
      "engine": "https://elis.rossum.ai/api/v1/engines/123",
      "name": "invoice_number",
      "label": "Invoice Number",
      "type": "string",
      "subtype": null,
      "tabular": false,
      "multiline": "false",
      "pre_trained_field_id": null,
      "schemas": ["https://elis.rossum.ai/api/v1/schemas/456"]
    },
    {
      "id": 12346,
      "url": "https://elis.rossum.ai/api/v1/engine_fields/12346",
      "engine": "https://elis.rossum.ai/api/v1/engines/123",
      "name": "invoice_date",
      "label": "Invoice Date",
      "type": "date",
      "subtype": null,
      "tabular": false,
      "multiline": "false",
      "pre_trained_field_id": null,
      "schemas": ["https://elis.rossum.ai/api/v1/schemas/456"]
    }
  ]
}
```

**Example usage:**
```python
# Get all engine fields for a specific engine
engine_fields = get_engine_fields(engine_id=123)

# Get all engine fields
all_fields = get_engine_fields()
```

### Rules Management

#### get_rule

Retrieves details of a specific business rule by its ID.

**Parameters:**
- `rule_id` (integer, required): Rule ID

**Returns:**
```json
{
  "id": 12345,
  "name": "Auto-calculate Total",
  "url": "https://elis.rossum.ai/api/v1/rules/12345",
  "enabled": true,
  "organization": "https://elis.rossum.ai/api/v1/organizations/100",
  "schema": "https://elis.rossum.ai/api/v1/schemas/200",
  "trigger_condition": "field.amount_total.changed",
  "created_by": "https://elis.rossum.ai/api/v1/users/300",
  "created_at": "2024-01-01T00:00:00Z",
  "modified_by": "https://elis.rossum.ai/api/v1/users/300",
  "modified_at": "2024-01-01T00:00:00Z",
  "rule_template": null,
  "synchronized_from_template": false,
  "actions": [
    {
      "id": 54321,
      "type": "set_datapoint_value",
      "payload": {
        "datapoint_id": "tax_amount",
        "value": "field.amount_total.value * 0.2"
      },
      "event": "trigger",
      "enabled": true
    }
  ]
}
```

**Example usage:**
```python
# Get rule details
rule = get_rule(rule_id=12345)
```

#### list_rules

Lists all business rules configured in your organization. Rules define custom business logic with trigger conditions (TxScript formulas) and actions that execute when conditions are met.

**Parameters:**
- `schema_id` (integer, optional): Filter rules by schema ID
- `organization_id` (integer, optional): Filter rules by organization ID
- `enabled` (boolean, optional): Filter by enabled status (true for enabled rules, false for disabled)

**Returns:**
```json
{
  "count": 2,
  "results": [
    {
      "id": 12345,
      "name": "Auto-calculate Total",
      "url": "https://elis.rossum.ai/api/v1/rules/12345",
      "enabled": true,
      "organization": "https://elis.rossum.ai/api/v1/organizations/100",
      "schema": "https://elis.rossum.ai/api/v1/schemas/200",
      "trigger_condition": "field.amount_total.changed",
      "created_by": "https://elis.rossum.ai/api/v1/users/300",
      "created_at": "2024-01-01T00:00:00Z",
      "modified_by": "https://elis.rossum.ai/api/v1/users/300",
      "modified_at": "2024-01-01T00:00:00Z",
      "rule_template": null,
      "synchronized_from_template": false,
      "actions": [
        {
          "id": 54321,
          "type": "set_datapoint_value",
          "payload": {
            "datapoint_id": "tax_amount",
            "value": "field.amount_total.value * 0.2"
          },
          "event": "trigger",
          "enabled": true
        }
      ]
    }
  ]
}
```

**Example usage:**
```python
# List all rules
all_rules = list_rules()

# List rules for a specific schema
schema_rules = list_rules(schema_id=12345)

# List only enabled rules
enabled_rules = list_rules(enabled=True)

# List enabled rules for a specific organization
org_enabled_rules = list_rules(organization_id=100, enabled=True)
```

### Relations Management

#### get_relation

Retrieves details of a specific relation by its ID. Relations introduce common relations between annotations.

**Parameters:**
- `relation_id` (integer, required): Relation ID

**Returns:**
```json
{
  "id": 12345,
  "type": "duplicate",
  "key": "abc123def456",
  "parent": "https://elis.rossum.ai/api/v1/annotations/100",
  "annotations": [
    "https://elis.rossum.ai/api/v1/annotations/100",
    "https://elis.rossum.ai/api/v1/annotations/101"
  ],
  "url": "https://elis.rossum.ai/api/v1/relations/12345"
}
```

**Example usage:**
```python
# Get relation details
relation = get_relation(relation_id=12345)
```

#### list_relations

Lists all relations between annotations with optional filters. Relations introduce common relations between annotations:
- **edit**: Created after editing annotation in user interface (rotation or split of the document)
- **attachment**: One or more documents are attachments to another document
- **duplicate**: Created after importing the same document that already exists in Rossum

**Parameters:**
- `id` (integer, optional): Filter by relation ID
- `type` (string, optional): Filter by relation type ('edit', 'attachment', 'duplicate')
- `parent` (integer, optional): Filter by parent annotation ID
- `key` (string, optional): Filter by relation key
- `annotation` (integer, optional): Filter by annotation ID

**Returns:**
```json
{
  "count": 2,
  "results": [
    {
      "id": 12345,
      "type": "duplicate",
      "key": "abc123def456",
      "parent": "https://elis.rossum.ai/api/v1/annotations/100",
      "annotations": [
        "https://elis.rossum.ai/api/v1/annotations/100",
        "https://elis.rossum.ai/api/v1/annotations/101"
      ],
      "url": "https://elis.rossum.ai/api/v1/relations/12345"
    },
    {
      "id": 12346,
      "type": "edit",
      "key": null,
      "parent": "https://elis.rossum.ai/api/v1/annotations/200",
      "annotations": [
        "https://elis.rossum.ai/api/v1/annotations/201",
        "https://elis.rossum.ai/api/v1/annotations/202"
      ],
      "url": "https://elis.rossum.ai/api/v1/relations/12346"
    }
  ]
}
```

**Example usage:**
```python
# List all relations
all_relations = list_relations()

# List duplicate relations
duplicate_relations = list_relations(type="duplicate")

# List relations for a specific parent annotation
parent_relations = list_relations(parent=12345)

# List relations containing a specific annotation
annotation_relations = list_relations(annotation=12345)
```

#### get_document_relation

Retrieves details of a specific document relation by its ID. Document relations introduce additional relations between annotations and documents.

**Parameters:**
- `document_relation_id` (integer, required): Document relation ID

**Returns:**
```json
{
  "id": 12345,
  "type": "export",
  "annotation": "https://elis.rossum.ai/api/v1/annotations/100",
  "key": "exported_file_key",
  "documents": [
    "https://elis.rossum.ai/api/v1/documents/200",
    "https://elis.rossum.ai/api/v1/documents/201"
  ],
  "url": "https://elis.rossum.ai/api/v1/document_relations/12345"
}
```

**Example usage:**
```python
# Get document relation details
doc_relation = get_document_relation(document_relation_id=12345)
```

#### list_document_relations

Lists all document relations with optional filters. Document relations introduce additional relations between annotations and documents:
- **export**: Documents generated from exporting an annotation
- **einvoice**: Electronic invoice documents associated with an annotation

**Parameters:**
- `id` (integer, optional): Filter by document relation ID
- `type` (string, optional): Filter by relation type ('export', 'einvoice')
- `annotation` (integer, optional): Filter by annotation ID
- `key` (string, optional): Filter by relation key
- `documents` (integer, optional): Filter by document ID

**Returns:**
```json
{
  "count": 2,
  "results": [
    {
      "id": 12345,
      "type": "export",
      "annotation": "https://elis.rossum.ai/api/v1/annotations/100",
      "key": "exported_file_key",
      "documents": [
        "https://elis.rossum.ai/api/v1/documents/200",
        "https://elis.rossum.ai/api/v1/documents/201"
      ],
      "url": "https://elis.rossum.ai/api/v1/document_relations/12345"
    },
    {
      "id": 12346,
      "type": "einvoice",
      "annotation": "https://elis.rossum.ai/api/v1/annotations/102",
      "key": null,
      "documents": [
        "https://elis.rossum.ai/api/v1/documents/300"
      ],
      "url": "https://elis.rossum.ai/api/v1/document_relations/12346"
    }
  ]
}
```

**Example usage:**
```python
# List all document relations
all_doc_relations = list_document_relations()

# List export-type document relations
export_relations = list_document_relations(type="export")

# List document relations for a specific annotation
annotation_doc_relations = list_document_relations(annotation=100)

# List document relations containing a specific document
document_relations = list_document_relations(documents=200)
```

## Annotation Status Workflow

When a document is uploaded, the annotation progresses through various states:

1. **importing** - Initial state after upload. Document is being processed.
2. **to_review** - Extraction complete, ready for user validation.
3. **reviewing** - Annotation is being reviewed (triggered by `start_annotation`). This state is required before you can update annotation fields.
4. **confirmed** - The annotation has been validated and confirmed (via `confirm_annotation`).
5. **exporting** - The annotation is being exported.
6. **exported** - Final state for successfully processed documents.

Other possible states include: `created`, `failed_import`, `split`, `in_workflow`, `rejected`, `failed_export`, `postponed`, `deleted`, `purged`.

**Important Notes:**
- After uploading documents, agents should wait for annotations to transition from `importing` to `to_review` (or later states) before considering them fully processed.
- To update annotation field values, you must first call `start_annotation` to move the annotation to 'reviewing' status.
- After updating fields with `bulk_update_annotation_fields`, you can call `confirm_annotation` to move to 'confirmed' status.

## Example Workflows

<details>
<summary>Single Document Upload</summary>

1. Upload a document using `upload_document`
2. Get the annotation ID using `list_annotations`
3. Check annotation status using `get_annotation`
4. Wait until status is `to_review`, `confirmed`, or `exported`

</details>

<details>
<summary>Document Upload with Field Updates</summary>

1. Upload a document using `upload_document`
2. Get the annotation ID using `list_annotations`
3. Wait until status is `importing` or `to_review`
4. Start the annotation using `start_annotation` (moves to 'reviewing')
5. Get annotation content using `get_annotation` with `sideloads=['content']`
6. Update field values using `bulk_update_annotation_fields` with datapoint IDs from content
7. Confirm the annotation using `confirm_annotation` (moves to 'confirmed')

</details>

<details>
<summary>Bulk Document Upload</summary>

1. Upload all documents in bulk using `upload_document` for each file
2. Check status of all annotations using `list_annotations`
3. Monitor until all documents finish processing

</details>

<details>
<summary>Create Queue with Engine</summary>

1. Create a schema using `create_schema` with sections and datapoints
2. Create an engine using `create_engine` with type 'extractor' or 'splitter'
3. Create engine fields using `create_engine_field` for each schema field
4. Create a queue using `create_queue` linking the schema and engine
5. Optionally update engine training queues using `update_engine`

</details>

## Error Handling

The server provides detailed error messages for common issues:
- Missing API token
- File not found
- Upload failures
- API errors

## License

MIT License - see LICENSE file for details

## Resources

- [Rossum API Documentation](https://elis.rossum.ai/api/docs/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Rossum SDK](https://github.com/rossumai/rossum-sdk)
- [Main Repository](https://github.com/stancld/rossum-mcp)
