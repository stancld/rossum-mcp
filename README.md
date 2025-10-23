# Rossum MCP Server

<div align="center">

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-mcp/)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![Rossum SDK](https://img.shields.io/badge/Rossum-SDK-orange.svg)](https://github.com/rossumai/rossum-sdk)
[![codecov](https://codecov.io/gh/stancld/rossum-mcp/branch/master/graph/badge.svg)](https://codecov.io/gh/stancld/rossum-mcp)

</div>

A Model Context Protocol (MCP) server that provides tools for uploading documents and retrieving annotations using the Rossum API. Built with Python and the official [rossum-sdk](https://github.com/rossumai/rossum-sdk).

## Real-World Use Case 📊

Imagine you have a board meeting in 10 minutes ⏰ and you forgot to process 30 invoices for one of your contractors. You need an aggregation for them - **fast**. With Rossum MCP, you can:

1. 📤 **Upload all 30 invoices in bulk** to your Rossum queue
2. 🤖 **Wait for automatic processing** - AI extracts all data from every invoice
3. 📈 **Aggregate the data** - automatically sum up all line items across documents
4. 🎨 **Generate a presentable visualization** - create an interactive bar chart showing revenue by service

All of this happens in minutes, with a simple conversational prompt. No manual data entry, no spreadsheets, no panic. Just upload, process, and present. ✨

### Example: From Chaos to Chart 🚀

**This real-world example was achieved using the efficient Qwen 3 Next 80B A3B model.**

Starting from a folder full of unprocessed invoices:

```
/examples/data/
├── 📄 invoice_001.pdf
├── 📄 invoice_002.pdf
├── ...
└── 📄 invoice_030.pdf
```

With a single prompt (see [examples/PROMPT.md](examples/PROMPT.md)), the agent:
- ⬆️ Uploads all documents to Rossum
- 👀 Monitors processing status automatically
- 🔍 Extracts and aggregates line items by description
- 📊 Generates an interactive HTML chart ([`revenue.html`](revenue.html))

Result: You walk into your meeting with a professional visualization showing exactly how much revenue each service generated across all 30 invoices. 🎯

<div align="center">
  <img src="revenue.png" alt="Revenue by Services Chart" width="800">
</div>

The generated chart is fully interactive (built with Plotly) - hover over bars to see exact values, zoom, pan, and export as needed. Perfect for presentations. 💼

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

This repository contains two separate packages:
- **rossum-mcp**: MCP server for Rossum SDK interactions
- **rossum-agent**: AI agent with tools for data manipulation and visualization

Each package can be installed independently or together for full functionality.

### Install MCP Server Only

```bash
git clone https://github.com/stancld/rossum-mcp.git
cd rossum-mcp/rossum_mcp
pip install -e .
```

With extras:
```bash
pip install -e ".[all]"  # All extras (docs, tests)
pip install -e ".[docs]"  # Documentation only
pip install -e ".[tests]"  # Testing only
```

See [rossum_mcp/README.md](rossum_mcp/README.md) for detailed MCP server documentation.

### Install Agent Only

```bash
git clone https://github.com/stancld/rossum-mcp.git
cd rossum-mcp/rossum_agent
pip install -e .
```

With extras:
```bash
pip install -e ".[all]"  # All extras (streamlit, docs, tests)
pip install -e ".[streamlit]"  # Streamlit UI only
pip install -e ".[docs]"  # Documentation only
pip install -e ".[tests]"  # Testing only
```

See [rossum_agent/README.md](rossum_agent/README.md) for detailed agent documentation.

### Install Both Packages (Development)

For full development with both packages:

```bash
git clone https://github.com/stancld/rossum-mcp.git
cd rossum-mcp
pip install -e "rossum_mcp[all]" -e "rossum_agent[all]"
```

This provides the complete toolkit for document processing, AI agents, and visualizations

### Set up environment variables:
```bash
export ROSSUM_API_TOKEN="your-api-token"
export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"  # or your organization's base URL
```

## Usage

### Running the MCP Server

Start the server using:
```bash
cd rossum_mcp
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
      "args": ["/path/to/rossum-mcp/server.py"],
      "env": {
        "ROSSUM_API_TOKEN": "your-api-token",
        "ROSSUM_API_BASE_URL": "https://api.elis.rossum.ai/v1"
      }
    }
  }
}
```

### Using the Rossum Agent

The `rossum-agent` package provides a complete AI agent with tools for data manipulation and visualization:

```bash
# Install the agent package
cd rossum_agent
pip install -e ".[all]"

# Run the CLI agent
rossum-agent

# Or run the Streamlit UI
streamlit run app.py
```

The agent includes:
- File system tools (read, list files)
- Plotting tools (bar charts, line charts, scatter plots, etc.)
- Rossum integration (when MCP server is running)
- Interactive CLI and web interfaces

See [rossum_agent/README.md](rossum_agent/README.md) for detailed agent documentation and [examples/](examples/) for complete working examples.

### Available Tools

#### 1. upload_document

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

#### 2. get_annotation

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

#### 3. list_annotations

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

#### 4. get_queue

Retrieves queue details including the schema_id. Use this to get the schema_id for use with get_schema.

**Parameters:**
- `queue_id` (integer, required): Rossum queue ID to retrieve

**Returns:**
```json
{
  "id": "12345",
  "name": "Invoices",
  "url": "https://elis.rossum.ai/api/v1/queues/12345",
  "schema_id": "67890",
  "workspace": "11111",
  "inbox": "22222",
  "created_at": "2024-01-01T00:00:00Z",
  "modified_at": "2024-01-01T00:00:00Z"
}
```

#### 5. get_schema

Retrieves schema details including the schema content/structure. Use get_queue first to obtain the schema_id.

**Parameters:**
- `schema_id` (integer, required): Rossum schema ID to retrieve

**Returns:**
```json
{
  "id": "67890",
  "name": "Invoice Schema",
  "url": "https://elis.rossum.ai/api/v1/schemas/67890",
  "content": [...]
}
```

#### 6. get_queue_schema

Retrieves the complete schema for a queue in a single call. This is the recommended way to get a queue's schema.

**Parameters:**
- `queue_id` (integer, required): Rossum queue ID

**Returns:**
```json
{
  "queue_id": "12345",
  "queue_name": "Invoices",
  "schema_id": "67890",
  "schema_name": "Invoice Schema",
  "schema_url": "https://elis.rossum.ai/api/v1/schemas/67890",
  "schema_content": [...]
}
```

#### 7. get_queue_engine

Retrieves the complete engine information for a given queue in a single call. Returns engine type (dedicated, generic, or standard) and details.

**Parameters:**
- `queue_id` (integer, required): Rossum queue ID

**Returns:**
```json
{
  "queue_id": "12345",
  "queue_name": "Invoices",
  "engine_id": 67890,
  "engine_name": "My Engine",
  "engine_url": "https://elis.rossum.ai/api/v1/engines/67890",
  "engine_type": "dedicated"
}
```

#### 8. create_queue

Creates a new queue with schema and optional engine assignment. Allows full configuration of queue settings including automation and training.

**Parameters:**
- `name` (string, required): Name of the queue to create
- `workspace_id` (integer, required): Workspace ID where the queue should be created
- `schema_id` (integer, required): Schema ID to assign to the queue
- `engine_id` (integer, optional): Optional engine ID to assign for document processing
- `inbox_id` (integer, optional): Optional inbox ID to assign
- `connector_id` (integer, optional): Optional connector ID to assign
- `locale` (string, optional): Queue locale (default: "en_GB")
- `automation_enabled` (boolean, optional): Enable automation (default: false)
- `automation_level` (string, optional): Automation level - "never", "always", etc. (default: "never")
- `training_enabled` (boolean, optional): Enable training (default: true)

**Returns:**
```json
{
  "id": "12345",
  "name": "My New Queue",
  "url": "https://elis.rossum.ai/api/v1/queues/12345",
  "workspace": "https://elis.rossum.ai/api/v1/workspaces/11111",
  "schema": "https://elis.rossum.ai/api/v1/schemas/67890",
  "engine": "https://elis.rossum.ai/api/v1/engines/54321",
  "inbox": null,
  "connector": null,
  "locale": "en_GB",
  "automation_enabled": false,
  "automation_level": "never",
  "training_enabled": true,
  "message": "Queue 'My New Queue' created successfully with ID 12345"
}
```

#### 9. update_queue

Updates an existing queue's settings including automation thresholds. Use this to configure automation settings like enabling automation, setting automation level, and defining the default confidence score threshold.

**Parameters:**
- `queue_id` (integer, required): Queue ID to update
- `queue_data` (object, required): Dictionary containing queue fields to update. Common fields:
  - `name` (string): Queue name
  - `automation_enabled` (boolean): Enable/disable automation
  - `automation_level` (string): "never", "always", "confident", etc.
  - `default_score_threshold` (float): Default confidence threshold 0.0-1.0 (e.g., 0.90 for 90%)
  - `locale` (string): Queue locale
  - `training_enabled` (boolean): Enable/disable training

**Returns:**
```json
{
  "id": "12345",
  "name": "Updated Queue",
  "url": "https://elis.rossum.ai/api/v1/queues/12345",
  "automation_enabled": true,
  "automation_level": "confident",
  "default_score_threshold": 0.90,
  "locale": "en_GB",
  "training_enabled": true,
  "message": "Queue 'Updated Queue' (ID 12345) updated successfully"
}
```

#### 10. update_schema

Updates an existing schema, typically used to set field-level automation thresholds. Field-level thresholds override the queue's default_score_threshold.

**Workflow:**
1. First get the schema using `get_queue_schema`
2. Modify the `content` array by adding/updating `score_threshold` properties on specific fields
3. Call this tool with the modified content

**Parameters:**
- `schema_id` (integer, required): Schema ID to update
- `schema_data` (object, required): Dictionary containing schema fields to update. Typically contains:
  - `content` (array): Full schema content array where each field can have a `score_threshold` property (float 0.0-1.0)

**Best Practices:**
- Use higher thresholds (0.95-0.98) for critical fields like amounts and IDs
- Use lower thresholds (0.80-0.90) for less critical fields

**Returns:**
```json
{
  "id": "67890",
  "name": "Invoice Schema",
  "url": "https://elis.rossum.ai/api/v1/schemas/67890",
  "content": [...],
  "message": "Schema 'Invoice Schema' (ID 67890) updated successfully"
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
Response: { task_id: "67890", task_status: "created", message: "..." }
```

2. Get the annotation ID:
```
Use list_annotations with:
- queue_id: "12345"
Find your document in the results by creation time
```

3. Check annotation status:
```
Use get_annotation with:
- annotation_id: "67890" (from list_annotations)
Check status field - wait until it's "to_review", "confirmed", or "exported"
```

### Bulk Document Upload

For agents uploading multiple documents:

1. Upload all documents in bulk:
```
For each file:
  Use upload_document with file_path and queue_id
  Store returned task_ids
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

## Package Documentation

- [rossum_mcp/README.md](rossum_mcp/README.md) - MCP server documentation
- [rossum_agent/README.md](rossum_agent/README.md) - AI agent documentation
- [examples/README.md](examples/README.md) - Usage examples and guides

## Resources

- [Full Documentation](https://stancld.github.io/rossum-mcp/)
- [Rossum API Documentation](https://elis.rossum.ai/api/docs/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Rossum SDK](https://github.com/rossumai/rossum-sdk)
- [Smolagents](https://github.com/huggingface/smolagents)
