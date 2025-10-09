# Rossum MCP Server

A Model Context Protocol (MCP) server that provides tools for uploading documents and retrieving annotations using the Rossum API. Built with Python and the official [rossum-sdk](https://github.com/rossumai/rossum-sdk).

## Features

- **upload_document**: Upload a document to Rossum for processing
- **get_annotation**: Retrieve annotation data for a previously uploaded document
- **list_annotations**: List all annotations for a queue with optional filtering

## Prerequisites

- Python 3.10 or higher
- Rossum account with API credentials
- A Rossum queue ID

## Installation

1. Clone this repository or download the files

2. Install dependencies:
```bash
pip install -r requirements.txt
```

Or install as a package:
```bash
pip install -e .
```

3. Set up environment variables:
```bash
export ROSSUM_API_TOKEN="your-api-token"
export ROSSUM_API_BASE_URL="https://api.elis.develop.r8.lol/v1"  # or your organization's base URL
```

## Usage

### Running the MCP Server

Start the server using:
```bash
python server.py
```

### Using with MCP Clients

Configure your MCP client to use this server. For example, in Claude Desktop's config:

```json
{
  "mcpServers": {
    "rossum": {
      "command": "python",
      "args": ["/path/to/rossum-mcp/server.py"],
      "env": {
        "ROSSUM_API_TOKEN": "your-api-token",
        "ROSSUM_API_BASE_URL": "https://api.elis.develop.r8.lol/v1"
      }
    }
  }
}
```

### Using with Smolagents

The Python implementation makes it easy to use with smolagents, as both use Python and can share the `rossum_api` package:

```python
from smolagents import ToolCallingAgent, ManagedAgent

# Create a Rossum MCP agent
rossum_agent = ManagedAgent(
    agent=ToolCallingAgent(tools=[]),
    name="rossum",
    description="Upload and process documents using Rossum API"
)

# Use the agent
result = rossum_agent.run(
    "Upload the invoice.pdf to queue 12345 and wait for it to be processed"
)
```

### Available Tools

#### 1. upload_document

Uploads a document to Rossum for processing. The annotation will initially be in `importing` state.

**Parameters:**
- `file_path` (string, required): Absolute path to the document file
- `queue_id` (string, required): Rossum queue ID where the document should be uploaded

**Returns:**
```json
{
  "annotation_id": "12345",
  "document_id": "67890",
  "queue_id": "queue_id",
  "status": "uploaded"
}
```

#### 2. get_annotation

Retrieves annotation data for a previously uploaded document. Use this to check the status of a document.

**Parameters:**
- `annotation_id` (string, required): The annotation ID returned from upload_document

**Returns:**
```json
{
  "id": "12345",
  "status": "to_review",
  "url": "https://elis.rossum.ai/api/v1/annotations/12345",
  "document": "67890",
  "content": [...],
  "created_at": "2024-01-01T00:00:00Z",
  "modified_at": "2024-01-01T00:00:00Z"
}
```

#### 3. list_annotations

Lists all annotations for a queue with optional filtering. Useful for checking the status of multiple uploaded documents.

**Parameters:**
- `queue_id` (string, required): Rossum queue ID to list annotations from
- `status` (string, optional): Filter by annotation status (e.g., 'importing', 'to_review', 'confirmed', 'exported')
- `page_size` (number, optional): Number of results per page (default: 100)
- `ordering` (string, optional): Field to order by (e.g., '-created_at' for newest first)

**Returns:**
```json
{
  "count": 42,
  "next": "https://elis.rossum.ai/api/v1/annotations?page=2",
  "previous": null,
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

### Annotation Status Workflow

When a document is uploaded, the annotation progresses through various states:

1. **importing** - Initial state after upload. Document is being processed.
2. **to_review** - Extraction complete, ready for user validation.
3. **reviewing** - A user is currently reviewing the annotation.
4. **confirmed** - The annotation has been validated and confirmed.
5. **exporting** - The annotation is being exported.
6. **exported** - Final state for successfully processed documents.

Other possible states include: `created`, `failed_import`, `split`, `in_workflow`, `rejected`, `failed_export`, `postponed`, `deleted`, `purged`.

**Important**: After uploading documents, agents should wait for annotations to transition from `importing` to `to_review` (or `confirmed`/`exported`) before considering them fully processed. Use `get_annotation` to poll individual annotations or `list_annotations` to check the status of multiple documents in bulk.

## Example Workflow

### Single Document Upload

1. Upload a document:
```
Use upload_document with:
- file_path: "/path/to/invoice.pdf"
- queue_id: "12345"
Response: { annotation_id: "67890", ... }
```

2. Wait for processing and check status:
```
Use get_annotation with:
- annotation_id: "67890"
Check status field - wait until it's "to_review", "confirmed", or "exported"
```

### Bulk Document Upload

For agents uploading multiple documents:

1. Upload all documents in bulk:
```
For each file:
  Use upload_document with file_path and queue_id
  Store returned annotation_ids
```

2. Check status of all annotations:
```
Use list_annotations with:
- queue_id: "12345"
- status: "to_review" (or check all statuses)
- ordering: "-created_at"

This returns all annotations in the queue, allowing you to verify which documents have finished processing.
```

## Error Handling

The server provides detailed error messages for common issues:
- Missing API token
- File not found
- Upload failures
- API errors

## License

MIT License - see LICENSE file for details

## Contributing

Feel free to submit issues and pull requests.

## Resources

- [Rossum API Documentation](https://elis.rossum.ai/api/docs/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Rossum SDK](https://github.com/rossumai/rossum-sdk)
