# Rossum Agent

<div align="center">

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-mcp/)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Coverage](https://codecov.io/gh/stancld/rossum-mcp/branch/master/graph/badge.svg?flag=rossum-agent)](https://codecov.io/gh/stancld/rossum-mcp)

[![Rossum API](https://img.shields.io/badge/Rossum-API-orange.svg)](https://github.com/rossumai/rossum-api)
[![Anthropic](https://img.shields.io/badge/Anthropic-Claude-blueviolet.svg)](https://www.anthropic.com/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

</div>

AI agent for Rossum document processing. Built with Anthropic Claude and designed to work seamlessly with the Rossum MCP server.

> [!NOTE]
> This is not an official Rossum project. It is a community-developed integration built on top of the Rossum API.

> [!WARNING]
> This project is in early stage development. Breaking changes to both implementation and agent behavior are expected.

## Features

### Agent Capabilities
- **Rossum Integration**: Connect to Rossum MCP server for document processing
- **File Output**: Write reports, documentation, and analysis results to files
- **Knowledge Base Search**: Search the Rossum Knowledge Base with AI-powered analysis
- **Hook Debugging**: Debug Python function hooks with sandboxed execution and Opus sub-agent
- **Deployment Tools**: Pull, push, diff, and copy Rossum configurations across environments
- **Multi-Environment Support**: Spawn MCP connections to different Rossum environments
- **Skills System**: Load domain-specific skills for specialized workflows

### User Interfaces
- **Streamlit UI**: Web-based interface for interactive agent conversations
- **REST API**: FastAPI-based API for programmatic access and custom integrations

## Prerequisites

- Python 3.12 or higher
- AWS credentials configured (for Bedrock access to Claude models)
- Rossum account with API credentials (if using Rossum features)

## Installation

### Install from source

```bash
git clone https://github.com/stancld/rossum-mcp.git
cd rossum-mcp/rossum-agent
uv sync
```

### Install with extras

```bash
uv sync --extra all        # All extras (api, streamlit, docs, tests)
uv sync --extra api        # REST API (FastAPI, Redis, etc.)
uv sync --extra streamlit  # Streamlit UI only
uv sync --extra docs       # Documentation only
uv sync --extra tests      # Testing only
```

### Set up environment variables

```bash
# Required for AWS Bedrock
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="eu-central-1"

# Required for Rossum features
export ROSSUM_API_TOKEN="your-api-token"
export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"

# Optional: Redis for chat persistence (API mode)
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
```

## Usage

### Running the Streamlit UI

```bash
rossum-agent
```

Or run directly:
```bash
streamlit run rossum_agent/streamlit_app/app.py
```

### Running the REST API

```bash
rossum-agent-api
```

With options:
```bash
rossum-agent-api --host 0.0.0.0 --port 8000 --reload
```

### Using in Python Scripts

```python
import asyncio
from rossum_agent.agent import create_agent
from rossum_agent.rossum_mcp_integration import create_mcp_connection

async def main():
    # Create MCP connection to Rossum
    mcp_connection = await create_mcp_connection()

    # Create the agent
    agent = await create_agent(
        mcp_connection=mcp_connection,
        system_prompt="You are a helpful Rossum assistant."
    )

    # Run the agent
    async for step in agent.run("List all queues in my organization"):
        if step.thinking:
            print(step.thinking)
        if step.final_answer:
            print(step.final_answer)

asyncio.run(main())
```

## Available Tools

### File System Tools

#### write_file
Write text or markdown content to a file. Use this to save documentation, reports, or analysis results.

**Parameters:**
- `filename` (string): The name of the file to create (e.g., 'report.md', 'analysis.json')
- `content` (string): The content to write to the file

### Knowledge Base Tools

#### search_knowledge_base
Search the Rossum Knowledge Base for documentation about extensions, hooks, and configurations. Results are analyzed by Claude Opus for relevance.

**Parameters:**
- `query` (string, required): Search query. Be specific - include extension names, error messages, or feature names.
- `user_query` (string, optional): The original user question for context.

### Hook Analysis Tools

#### evaluate_python_hook
Execute Rossum function hook Python code against test annotation/schema data in a sandboxed environment.

**Parameters:**
- `code` (string, required): Full Python source containing a `rossum_hook_request_handler(payload)` function
- `annotation_json` (string, required): JSON string of the annotation object
- `schema_json` (string, optional): JSON string of the schema object

**Sandbox Environment:**
- Available modules: `collections`, `datetime`, `decimal`, `functools`, `itertools`, `json`, `math`, `re`, `string`
- No imports or external I/O allowed

#### debug_hook
Expert-level hook debugging with Claude Opus sub-agent. This is the primary tool for debugging Python function hooks.

**Parameters:**
- `hook_id` (string, required): The hook ID to debug
- `annotation_id` (string, required): The annotation ID to use for testing
- `schema_id` (string, optional): Schema ID if schema context is needed

The tool fetches hook code and annotation data, executes the hook, and uses Opus to analyze errors and suggest fixes.

### Schema Tools

#### patch_schema_with_subagent
Safely patch Rossum schemas using a Claude Opus sub-agent. The sub-agent fetches the schema, applies changes one at a time, and verifies only requested fields are present.

**Parameters:**
- `schema_id` (string, required): The schema ID to patch
- `changes` (string, required): JSON array of changes. Each change object should have:
  - `action`: "add" or "remove" (default: "add")
  - `id`: Field ID (schema_id)
  - `parent_section`: Section ID to add field to (for "add")
  - `type`: Field type (string, number, date, enum)
  - `label`: Field label (optional, defaults to id)

**Features:**
- Max 3 patches before re-fetching schema to ensure consistency
- Verifies only requested fields are present after patching
- Supports formula fields and enum options

### Deployment Tools

#### deploy_pull
Pull Rossum configuration objects from an organization to local files.

**Parameters:**
- `org_id` (int, required): Organization ID to pull from
- `workspace_path` (string, optional): Path to workspace directory
- `api_base_url` (string, optional): API base URL for target environment
- `token` (string, optional): API token for target environment

#### deploy_diff
Compare local workspace files with remote Rossum configuration.

**Parameters:**
- `workspace_path` (string, optional): Path to workspace directory

#### deploy_push
Push local changes to Rossum.

**Parameters:**
- `dry_run` (bool, optional): Only show what would be pushed
- `force` (bool, optional): Push even if there are conflicts
- `workspace_path` (string, optional): Path to workspace directory

#### deploy_copy_org
Copy all objects from source organization to target organization.

**Parameters:**
- `source_org_id` (int, required): Source organization ID
- `target_org_id` (int, required): Target organization ID
- `target_api_base` (string, optional): Target API base URL
- `target_token` (string, optional): Target API token
- `workspace_path` (string, optional): Path to workspace directory

#### deploy_copy_workspace
Copy a single workspace and all its objects to target organization.

**Parameters:**
- `source_workspace_id` (int, required): Source workspace ID
- `target_org_id` (int, required): Target organization ID
- `target_api_base` (string, optional): Target API base URL
- `target_token` (string, optional): Target API token
- `workspace_path` (string, optional): Path to workspace directory

#### deploy_compare_workspaces
Compare two local workspaces to see differences between source and target.

**Parameters:**
- `source_workspace_path` (string, required): Path to source workspace
- `target_workspace_path` (string, required): Path to target workspace
- `id_mapping_path` (string, optional): Path to ID mapping JSON from copy operations

#### deploy_to_org
Deploy local configuration changes to a target organization.

**Parameters:**
- `target_org_id` (int, required): Target organization ID
- `target_api_base` (string, optional): Target API base URL
- `target_token` (string, optional): Target API token
- `dry_run` (bool, optional): Only show what would be deployed
- `workspace_path` (string, optional): Path to workspace directory

### Multi-Environment Tools

#### spawn_mcp_connection
Spawn a new MCP connection to a different Rossum environment.

**Parameters:**
- `connection_id` (string, required): Unique identifier for this connection
- `api_token` (string, required): API token for the target environment
- `api_base_url` (string, required): API base URL for the target environment
- `mcp_mode` (string, optional): "read-only" or "read-write" (default)

#### call_on_connection
Call a tool on a spawned MCP connection.

**Parameters:**
- `connection_id` (string, required): The spawned connection identifier
- `tool_name` (string, required): Name of the MCP tool to call
- `arguments` (string, required): JSON string of arguments

#### close_connection
Close a spawned MCP connection.

**Parameters:**
- `connection_id` (string, required): The connection to close

### Skills Tools

#### load_skill
Load a specialized skill that provides domain-specific instructions and workflows.

**Parameters:**
- `name` (string, required): The skill slug (e.g., "rossum-deployment", "hook-debugging")

**Available Skills:**
- `rossum-deployment`: Deployment workflow instructions
- `hook-debugging`: Hook debugging best practices

### Rossum MCP Tools

When configured with the Rossum MCP server, the agent can use all MCP tools including:
- Upload documents to Rossum
- Monitor processing status
- Retrieve and parse annotation data
- Manage queues, schemas, hooks, and engines

See the [MCP Server README](../rossum-mcp/README.md) for the complete list of available MCP tools.

## Testing Framework

The package includes a regression testing framework for agent behavior:

```python
from rossum_agent.testing import (
    RegressionTestCase,
    SuccessCriteria,
    TokenBudget,
    ToolExpectation,
    ToolMatchMode,
    run_regression_test,
)

test_case = RegressionTestCase(
    name="list_queues",
    prompt="List all queues",
    success_criteria=SuccessCriteria(
        required_tools=[
            ToolExpectation(name="list_queues", match_mode=ToolMatchMode.EXACT)
        ]
    ),
    token_budget=TokenBudget(max_input=50000, max_output=10000),
)

result = await run_regression_test(agent, test_case)
```

## Architecture

```
┌─────────────────────┐
│    User Interface   │
│  (Streamlit / API)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Rossum Agent      │
│   (Claude Bedrock)  │
├─────────────────────┤
│ • Internal Tools    │
│ • Deploy Tools      │
│ • Spawn MCP Tools   │
│ • Skills System     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐      ┌──────────────┐
│   Rossum MCP        │─────▶│  Rossum API  │
│     Server          │      └──────────────┘
└─────────────────────┘
```

## REST API Endpoints

The API provides the following endpoints:

- `GET /api/v1/health` - Health check
- `GET /api/v1/chats` - List all chats
- `POST /api/v1/chats` - Create a new chat
- `GET /api/v1/chats/{chat_id}` - Get chat details
- `DELETE /api/v1/chats/{chat_id}` - Delete a chat
- `POST /api/v1/chats/{chat_id}/messages` - Send a message (SSE streaming)
- `GET /api/v1/chats/{chat_id}/files` - List files in a chat
- `GET /api/v1/chats/{chat_id}/files/{filename}` - Download a file

API documentation is available at `/api/docs` (Swagger UI) and `/api/redoc` (ReDoc).

## License

MIT License - see LICENSE file for details

## Resources

- [Anthropic Claude Documentation](https://docs.anthropic.com/)
- [Rossum API Documentation](https://elis.rossum.ai/api/docs/)
- [Main Repository](https://github.com/stancld/rossum-mcp)
- [Full Documentation](https://stancld.github.io/rossum-mcp/)
