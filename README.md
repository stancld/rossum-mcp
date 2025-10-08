# Rossum MCP Server

A simple Model Context Protocol (MCP) server that provides tools for uploading documents and retrieving annotations using the Rossum API.

## Features

- **upload_document**: Upload a document to Rossum for processing
- **get_annotation**: Retrieve annotation data for a previously uploaded document

## Prerequisites

- Node.js 18 or higher
- Rossum account with API credentials
- A Rossum queue ID

## Installation

1. Clone this repository or download the files

2. Install dependencies:
```bash
npm install
```

3. Set up environment variables:
```bash
export ROSSUM_API_TOKEN="your-api-token"
export ROSSUM_API_BASE_URL="your-organization-base-url"
```

## Usage

### Running the MCP Server

Start the server using:
```bash
npm start
```

Or directly:
```bash
node index.js
```

### Using with MCP Clients

Configure your MCP client to use this server. For example, in Claude Desktop's config:

```json
{
  "mcpServers": {
    "rossum": {
      "command": "node",
      "args": ["/path/to/rossum-mcp/index.js"],
      "env": {
        "ROSSUM_API_TOKEN": "your-api-token",
        "ROSSUM_API_BASE_URL": "your-organization-ase-url"
      }
    }
  }
}
```

### Available Tools

#### 1. upload_document

Uploads a document to Rossum for processing.

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

Retrieves annotation data for a previously uploaded document.

**Parameters:**
- `annotation_id` (string, required): The annotation ID returned from upload_document

**Returns:**
```json
{
  "id": "12345",
  "status": "importing",
  "url": "https://elis.rossum.ai/api/v1/annotations/12345",
  "document": "67890",
  "content": [...],
  "created_at": "2024-01-01T00:00:00Z",
  "modified_at": "2024-01-01T00:00:00Z"
}
```

## Example Workflow

1. Upload a document:
```
Use upload_document with:
- file_path: "/path/to/invoice.pdf"
- queue_id: "12345"
```

2. Get the annotation data:
```
Use get_annotation with:
- annotation_id: "67890" (from upload response)
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
