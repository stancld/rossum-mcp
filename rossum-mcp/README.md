# Rossum MCP Server

<div align="center">

**MCP server for AI-powered Rossum document processing. Fully typed tools with Pydantic models, StrEnum parameters, and unified APIs — built for agents.**

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-agents/)
[![Python](https://img.shields.io/pypi/pyversions/rossum-mcp.svg)](https://pypi.org/project/rossum-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI - rossum-mcp](https://img.shields.io/pypi/v/rossum-mcp?label=rossum-mcp)](https://pypi.org/project/rossum-mcp/)

[![Coverage](https://codecov.io/gh/stancld/rossum-agents/branch/master/graph/badge.svg?flag=rossum-mcp)](https://codecov.io/gh/stancld/rossum-agents)
[![CodeQL](https://github.com/stancld/rossum-agents/actions/workflows/codeql.yaml/badge.svg)](https://github.com/stancld/rossum-agents/actions/workflows/codeql.yaml)
[![Snyk Security](https://github.com/stancld/rossum-agents/actions/workflows/snyk.yaml/badge.svg)](https://github.com/stancld/rossum-agents/actions/workflows/snyk.yaml)
[![CodeFactor](https://www.codefactor.io/repository/github/stancld/rossum-agents/badge)](https://www.codefactor.io/repository/github/stancld/rossum-agents)

[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![Fully Typed](https://img.shields.io/badge/Fully_Typed-Pydantic_%2B_Enums-blue.svg)](#available-tools)
[![Rossum API](https://img.shields.io/badge/Rossum-API-orange.svg)](https://github.com/rossumai/rossum-api)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

</div>

> [!NOTE]
> This is not an official Rossum project. It is a community-developed integration built on top of the Rossum API, not a product (yet).

This MCP server exposes only the **public Rossum API**. Internal tooling is part of [rossum-agent](../rossum-agent) and not available here.

## Demo

Rossum MCP in action with Claude Code:

<div align="center">

![Demo](assets/claude_code_demo.gif)

</div>

## Architecture

```
rossum-mcp CLI / uvx
  → run.py::main()
       → RossumMCPServer.Config.from_env()       # reads env vars
       → RossumMCPServer(config)
            → AsyncRossumAPIClient(token, base_url)
            → _create_app() → FastMCP instance
                 register_discovery_tools(mcp, mode)
                 register_get_tools(mcp, client)
                 register_search_tools(mcp, client)
                 register_create_tools(mcp, client, base_url)
                 register_update_tools(mcp, client, base_url)
                 register_delete_tools(mcp, client)
                 if READ_ONLY: mcp.disable(tags={"write"})
            → server.run()                        # stdio transport
```

The server is a single FastMCP app. Each tool layer (get, search, create, update, delete, discovery) is a registration function that decorates async handlers with `@mcp.tool()`. Tags (`read`, `write`, `queues`, `schemas`, ...) drive discoverability and the read-only mode.

## Quick Start

Set the required environment variables:

```bash
export ROSSUM_API_TOKEN="your-api-token"
export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
```

Then use the installed package or run from source.

Install and run:

```bash
uv pip install rossum-mcp
rossum-mcp
```

Or run from source:

```bash
git clone https://github.com/stancld/rossum-agents.git
cd rossum-agents/rossum-mcp

uv sync
python -m rossum_mcp.run
```

## Claude Desktop Configuration

Configure Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json` on Mac):

```json
{
  "mcpServers": {
    "rossum": {
      "command": "uvx",
      "args": ["rossum-mcp"],
      "env": {
        "ROSSUM_API_TOKEN": "${ROSSUM_API_TOKEN}",
        "ROSSUM_API_BASE_URL": "${ROSSUM_API_BASE_URL}",
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
| `ROSSUM_MCP_LOG_LEVEL` | No | Logging level (default: `INFO`) |

### Read-Only Mode

Set `ROSSUM_MCP_MODE=read-only` to disable all CREATE, UPDATE, DELETE, and UPLOAD operations. Only GET and LIST operations will be available.

To change the mode, restart the server with a different `ROSSUM_MCP_MODE` environment variable.

## Available Tools

Fully typed with Pydantic models, `StrEnum` parameters, and unified APIs — 30 tools across 13 categories.

<details>
<summary><strong>All 30 tools</strong></summary>

| Category | Tools |
|----------|-------|
| Read | `get` · `search` |
| Delete | `delete` |
| Documents | `upload_document` · `get_annotation_content` · `start_annotation` · `bulk_update_annotation_fields` · `confirm_annotation` · `copy_annotations` |
| Queues | `create_queue_from_template` · `update_queue` |
| Schemas | `patch_schema` · `get_schema_tree_structure` · `prune_schema_fields` |
| Engines | `create_engine` · `update_engine` · `create_engine_field` · `get_engine_fields` |
| Hooks | `create_hook` · `update_hook` · `create_hook_from_template` · `test_hook` |
| Rules | `create_rule` · `patch_rule` |
| Workspaces | `create_workspace` |
| Users | `create_user` · `update_user` |
| Email | `create_email_template` |
| Mode | `get_mcp_mode` |
| Discovery | `list_tool_categories` |

</details>

For parameters and examples, see [TOOLS.md](TOOLS.md).

## License

MIT License - see [LICENSE](../LICENSE) for details.

## Resources

- [Tools Reference](TOOLS.md)
