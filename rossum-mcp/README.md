# Rossum MCP Server

<div align="center">

**MCP server for AI-powered Rossum document processing. 50 tools for queues, schemas, hooks, engines, and more.**

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-agents/)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI - rossum-mcp](https://img.shields.io/pypi/v/rossum-mcp?label=rossum-mcp)](https://pypi.org/project/rossum-mcp/)
[![Coverage](https://codecov.io/gh/stancld/rossum-agents/branch/master/graph/badge.svg?flag=rossum-mcp)](https://codecov.io/gh/stancld/rossum-agents)
[![MCP Tools](https://img.shields.io/badge/MCP_Tools-50-blue.svg)](#available-tools)

[![Rossum API](https://img.shields.io/badge/Rossum-API-orange.svg)](https://github.com/rossumai/rossum-api)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

</div>

> [!NOTE]
> This is not an official Rossum project. It is a community-developed integration built on top of the Rossum API.

> [!WARNING]
> This project is in early stage development. Breaking changes to both implementation and agent behavior are expected.

## Quick Start

```bash
# Set environment variables
export ROSSUM_API_TOKEN="your-api-token"
export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"

# Run the MCP server
pip install rossum-mcp
rossum-mcp
```

Or run from source:

```bash
git clone https://github.com/stancld/rossum-agents.git
cd rossum-mcp/rossum-mcp
uv sync
python rossum_mcp/server.py
```

## Claude Desktop Configuration

Configure Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json` on Mac):

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

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ROSSUM_API_TOKEN` | Yes | Your Rossum API authentication token |
| `ROSSUM_API_BASE_URL` | Yes | Base URL for the Rossum API |
| `ROSSUM_MCP_MODE` | No | `read-write` (default) or `read-only` |

### Read-Only Mode

Set `ROSSUM_MCP_MODE=read-only` to disable all CREATE, UPDATE, and UPLOAD operations. Only GET and LIST operations will be available.

## Available Tools

The server provides **50 tools** organized into categories:

| Category | Tools | Description |
|----------|-------|-------------|
| **Document Processing** | 6 | Upload documents, retrieve/update/confirm annotations |
| **Queue Management** | 8 | Create, configure, and list queues |
| **Schema Management** | 7 | Define and modify field structures |
| **Engine Management** | 6 | Configure extraction and splitting engines |
| **Extensions & Rules** | 9 | Webhooks, serverless functions, business rules |
| **Workspace Management** | 3 | Organize queues into workspaces |
| **User Management** | 3 | List users and roles |
| **Relations** | 4 | Annotation and document relations |
| **Email Templates** | 3 | Automated email responses |
| **Tool Discovery** | 1 | Dynamic tool loading |

<details>
<summary><strong>Tool List by Category</strong></summary>

**Document Processing:**
`upload_document`, `get_annotation`, `list_annotations`, `start_annotation`, `bulk_update_annotation_fields`, `confirm_annotation`

**Queue Management:**
`get_queue`, `list_queues`, `get_queue_schema`, `get_queue_engine`, `create_queue`, `create_queue_from_template`, `get_queue_template_names`, `update_queue`

**Schema Management:**
`get_schema`, `list_schemas`, `create_schema`, `update_schema`, `patch_schema`, `get_schema_tree_structure`, `prune_schema_fields`

**Engine Management:**
`get_engine`, `list_engines`, `create_engine`, `update_engine`, `create_engine_field`, `get_engine_fields`

**Extensions & Rules:**
`get_hook`, `list_hooks`, `create_hook`, `update_hook`, `list_hook_templates`, `create_hook_from_template`, `list_hook_logs`, `get_rule`, `list_rules`

**Workspace Management:**
`get_workspace`, `list_workspaces`, `create_workspace`

**User Management:**
`get_user`, `list_users`, `list_user_roles`

**Relations:**
`get_relation`, `list_relations`, `get_document_relation`, `list_document_relations`

**Email Templates:**
`get_email_template`, `list_email_templates`, `create_email_template`

**Tool Discovery:**
`list_tool_categories`

</details>

For detailed API documentation with parameters and examples, see [TOOLS.md](TOOLS.md).

## Annotation Workflow

Documents progress through these states:

```
importing → to_review → reviewing → confirmed → exporting → exported
```

**Key points:**
- Wait for `to_review` before processing
- Call `start_annotation` before updating fields
- Call `confirm_annotation` to finalize

## Example Workflows

### Upload and Monitor

```python
# 1. Upload document
upload_document(file_path="/path/to/invoice.pdf", queue_id=12345)

# 2. Get annotation ID
annotations = list_annotations(queue_id=12345)

# 3. Check status
annotation = get_annotation(annotation_id=annotations[0].id)
```

### Update Fields

```python
# 1. Start annotation (moves to 'reviewing')
start_annotation(annotation_id=12345)

# 2. Get content with field IDs
annotation = get_annotation(annotation_id=12345, sideloads=['content'])

# 3. Update fields using datapoint IDs
bulk_update_annotation_fields(
    annotation_id=12345,
    operations=[{"op": "replace", "id": 67890, "value": {"content": {"value": "INV-001"}}}]
)

# 4. Confirm
confirm_annotation(annotation_id=12345)
```

## License

MIT License - see [LICENSE](../LICENSE) file for details.

## Resources

- [Full Documentation](https://stancld.github.io/rossum-agents/)
- [Tools Reference](TOOLS.md)
- [Rossum API Documentation](https://elis.rossum.ai/api/docs/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Main Repository](https://github.com/stancld/rossum-agents)
