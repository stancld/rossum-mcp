# Rossum MCP Server

<div align="center">

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-mcp/)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![Rossum SDK](https://img.shields.io/badge/Rossum-SDK-orange.svg)](https://github.com/rossumai/rossum-sdk)

</div>

A Model Context Protocol (MCP) server that provides tools for uploading documents and retrieving annotations using the Rossum API. Built with Python and the official [rossum-sdk](https://github.com/rossumai/rossum-sdk).

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

### Engine Management
- **create_engine**: Create a new engine (extractor or splitter)
- **update_engine**: Update engine settings including learning and training queues
- **create_engine_field**: Create engine fields and link them to schemas

## Prerequisites

- Python 3.10 or higher
- Rossum account with API credentials
- A Rossum queue ID

## Installation

### Install from source

```bash
git clone https://github.com/stancld/rossum-mcp.git
cd rossum-mcp/rossum_mcp
pip install -e .
```

### Install with extras

```bash
pip install -e ".[all]"  # All extras (docs, tests)
pip install -e ".[docs]"  # Documentation only
pip install -e ".[tests]"  # Testing only
```

### Set up environment variables

```bash
export ROSSUM_API_TOKEN="your-api-token"
export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"  # or your organization's base URL
```

## Usage

### Running the MCP Server

Start the server using:
```bash
python server.py
```

Or using the installed script:
```bash
rossum-mcp
```

### Using with MCP Clients

Configure your MCP client to use this server. For example, in Claude Desktop's config:

```json
{
  "mcpServers": {
    "rossum": {
      "command": "python",
      "args": ["/path/to/rossum-mcp/rossum_mcp/server.py"],
      "env": {
        "ROSSUM_API_TOKEN": "your-api-token",
        "ROSSUM_API_BASE_URL": "https://api.elis.rossum.ai/v1"
      }
    }
  }
}
```

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

### Single Document Upload

1. Upload a document using `upload_document`
2. Get the annotation ID using `list_annotations`
3. Check annotation status using `get_annotation`
4. Wait until status is `to_review`, `confirmed`, or `exported`

### Document Upload with Field Updates

1. Upload a document using `upload_document`
2. Get the annotation ID using `list_annotations`
3. Wait until status is `importing` or `to_review`
4. Start the annotation using `start_annotation` (moves to 'reviewing')
5. Get annotation content using `get_annotation` with `sideloads=['content']`
6. Update field values using `bulk_update_annotation_fields` with datapoint IDs from content
7. Confirm the annotation using `confirm_annotation` (moves to 'confirmed')

### Bulk Document Upload

1. Upload all documents in bulk using `upload_document` for each file
2. Check status of all annotations using `list_annotations`
3. Monitor until all documents finish processing

### Create Queue with Engine

1. Create a schema using `create_schema` with sections and datapoints
2. Create an engine using `create_engine` with type 'extractor' or 'splitter'
3. Create engine fields using `create_engine_field` for each schema field
4. Create a queue using `create_queue` linking the schema and engine
5. Optionally update engine training queues using `update_engine`

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
