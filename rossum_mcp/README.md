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

### Queue & Schema Management
- **get_queue**: Retrieve queue details including schema_id
- **get_schema**: Retrieve schema details and content
- **get_queue_schema**: Retrieve complete schema for a queue in a single call
- **get_queue_engine**: Retrieve engine information for a queue
- **create_queue**: Create a new queue with schema and optional engine assignment
- **update_queue**: Update queue settings including automation thresholds
- **update_schema**: Update schema with field-level automation thresholds

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

#### update_schema

Updates an existing schema, typically used to set field-level automation thresholds.

**Parameters:**
- `schema_id` (integer, required): Schema ID to update
- `schema_data` (object, required): Dictionary containing schema fields to update

## Annotation Status Workflow

When a document is uploaded, the annotation progresses through various states:

1. **importing** - Initial state after upload. Document is being processed.
2. **to_review** - Extraction complete, ready for user validation.
3. **reviewing** - A user is currently reviewing the annotation.
4. **confirmed** - The annotation has been validated and confirmed.
5. **exporting** - The annotation is being exported.
6. **exported** - Final state for successfully processed documents.

Other possible states include: `created`, `failed_import`, `split`, `in_workflow`, `rejected`, `failed_export`, `postponed`, `deleted`, `purged`.

**Important**: After uploading documents, agents should wait for annotations to transition from `importing` to `to_review` (or `confirmed`/`exported`) before considering them fully processed.

## Example Workflow

### Single Document Upload

1. Upload a document using `upload_document`
2. Get the annotation ID using `list_annotations`
3. Check annotation status using `get_annotation`
4. Wait until status is `to_review`, `confirmed`, or `exported`

### Bulk Document Upload

1. Upload all documents in bulk using `upload_document` for each file
2. Check status of all annotations using `list_annotations`
3. Monitor until all documents finish processing

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
