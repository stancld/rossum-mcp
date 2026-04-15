# Rossum Agent

<div align="center">

**AI agent for Rossum document processing. Debug hooks, deploy configs, and automate workflows conversationally — powered by Claude on AWS Bedrock.**

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-agents/)
[![Python](https://img.shields.io/pypi/pyversions/rossum-agent.svg)](https://pypi.org/project/rossum-agent/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI - rossum-agent](https://img.shields.io/pypi/v/rossum-agent?label=rossum-agent)](https://pypi.org/project/rossum-agent/)
[![Coverage](https://codecov.io/gh/rossumai/rossum-agents/branch/master/graph/badge.svg?flag=rossum-agent)](https://codecov.io/gh/rossumai/rossum-agents)

[![Rossum API](https://img.shields.io/badge/Rossum-API-orange.svg)](https://github.com/rossumai/rossum-api)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![Claude Opus 4.6](https://img.shields.io/badge/Claude-Opus_4.6-blueviolet.svg)](https://www.anthropic.com/claude/opus)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

</div>

> [!NOTE]
> This is not an official Rossum project. It is a community-developed integration built on top of the Rossum API, not a product (yet).

The agent wraps [rossum-mcp](../rossum-mcp) with internal tools, a skills system, prompt caching, and change tracking. Interfaces: REST API, Python SDK.

## Architecture

```
rossum-agent-api / Python SDK
  → create_agent(mcp_connection)
       → System Prompt + Skills System
       → Internal Tools
            write_file, search_knowledge_base, search_elis_docs,
            run_jq, run_grep, execute_python,
            patch_schema_with_subagent, generate_mock_pdf,
            load_skill, create_task, update_task, list_tasks,
            ask_user_question
       → Rossum MCP Server (30 tools)
            → Rossum API
```

The agent is a Claude Opus 4.6 loop on AWS Bedrock. Each turn loads the system prompt, auto-selects relevant MCP tool categories based on message keywords, and streams back reasoning + content + tool calls via the AI SDK UI Message Stream v1 wire protocol.

## Quick Start

```bash
# Set environment variables
export ROSSUM_API_TOKEN="your-api-token"
export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
export AWS_PROFILE="default"  # For Bedrock

# Install and run
uv pip install rossum-agent[api]
rossum-agent-api
```

Or run from source:

```bash
git clone https://github.com/rossumai/rossum-agents.git
cd rossum-agents/rossum-agent

uv sync --extra all        # All extras (api, docs, tests)
rossum-agent-api --reload
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ROSSUM_API_TOKEN` | Yes | Rossum API authentication token |
| `ROSSUM_API_BASE_URL` | Yes | Base URL (e.g., `https://api.elis.rossum.ai/v1`) |
| `AWS_PROFILE` | Yes | AWS profile for Bedrock access |
| `AWS_REGION` | No | AWS region for Bedrock (default: `us-east-1`) |
| `AWS_BEDROCK_MODEL_ARN` | No | Custom ARN for the Opus model |
| `AWS_BEDROCK_MODEL_ARN_SMALL` | No | Custom ARN for the Haiku model |
| `ROSSUM_MCP_MODE` | No | MCP mode: `read-write` (default) or `read-only` |
| `ROSSUM_AGENT_PERSONA` | No | Agent persona: `default` or `cautious` |
| `ADDITIONAL_ALLOWED_ROSSUM_HOSTS` | No | Comma-separated regex patterns for additional allowed API hosts |

<details>
<summary><strong>Optional infrastructure variables</strong></summary>

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_HOST` | `localhost` | PostgreSQL host for chat storage |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `rossum_agent` | PostgreSQL database name |
| `POSTGRES_USER` | `rossum` | PostgreSQL user |
| `POSTGRES_PASSWORD` | `rossum` | PostgreSQL password |
| `VALKEY_HOST` | `localhost` | Valkey host for change tracking |
| `VALKEY_PORT` | `6379` | Valkey port |
| `VALKEY_PASSWORD` | — | Valkey authentication password |
| `SLACK_BOT_TOKEN` | — | Slack bot token for report integration |
| `SLACK_CHANNEL` | — | Slack channel for posting reports |

</details>

## Usage

### REST API

```bash
# Development (uvicorn)
rossum-agent-api --host 0.0.0.0 --port 8000 --reload

# Production (gunicorn)
rossum-agent-api --server gunicorn --host 0.0.0.0 --port 8000 --workers 4
```

| Option | Description |
|--------|-------------|
| `--server` | Backend: `uvicorn` (default) or `gunicorn` |
| `--host` | Host to bind to (default: `127.0.0.1`) |
| `--port` | Port to listen on (default: `8000`) |
| `--workers` | Number of worker processes (default: `1`) |
| `--reload` | Enable auto-reload (uvicorn only) |

API docs available at `/api/docs` (Swagger) and `/api/redoc`.

### Python SDK

```python
import asyncio
from rossum_agent.agent import create_agent
from rossum_agent.rossum_mcp_integration.connection import connect_mcp_server

async def main():
    mcp_connection = await create_mcp_connection()
    agent = await create_agent(mcp_connection=mcp_connection)

    async for step in agent.run("List all queues"):
        if step.final_answer:
            print(step.final_answer)

asyncio.run(main())
```

## Available Tools

The agent provides internal tools and access to 30 MCP tools via dynamic loading.

<details>
<summary><strong>Internal tools</strong></summary>

| Category | Tools |
|----------|-------|
| File & Memory | `write_file` · `search_knowledge_base` · `search_elis_docs` |
| Data | `run_jq` · `run_grep` |
| Execution | `execute_python` |
| Schema | `patch_schema_with_subagent` |
| Skills | `load_skill` |
| Document Testing | `generate_mock_pdf` |
| Task Tracking | `create_task` · `update_task` · `list_tasks` |
| User Interaction | `ask_user_question` |

</details>

<details>
<summary><strong>Dynamic MCP tool loading</strong></summary>

Tools are loaded on-demand to reduce context usage. Categories are auto-loaded based on keywords in the user's message:

| Category | Description |
|----------|-------------|
| `annotations` | Upload, retrieve, update, confirm documents |
| `queues` | Create, configure, list queues |
| `schemas` | Define, modify field structures |
| `engines` | Extraction and splitting engines |
| `hooks` | Extensions and webhooks |
| `email_templates` | Automated email responses |
| `document_relations` | Export/einvoice links |
| `relations` | Annotation relations |
| `rules` | Schema validation rules |
| `users` | User and role management |
| `workspaces` | Workspace management |

</details>

## REST API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/health` | Health check |
| `POST /api/v1/chats` | Create new chat |
| `GET /api/v1/chats` | List all chats |
| `GET /api/v1/chats/{id}` | Get chat details |
| `DELETE /api/v1/chats/{id}` | Delete chat |
| `POST /api/v1/chats/{id}/messages` | Send message (streaming) |
| `PUT /api/v1/chats/{id}/feedback` | Submit feedback for a turn |
| `GET /api/v1/chats/{id}/feedback` | Get all feedback for a chat |
| `DELETE /api/v1/chats/{id}/feedback/{turn}` | Remove feedback |
| `GET /api/v1/chats/{id}/files` | List files |
| `GET /api/v1/chats/{id}/files/{name}` | Download file |
| `GET /api/v1/commands` | List available slash commands |

Streaming uses AI SDK UI Message Stream v1 (`x-vercel-ai-ui-message-stream: v1`). MCP mode and persona can be set at chat creation or overridden per message.

## License

MIT License - see [LICENSE](../LICENSE) for details.

## Resources

- [Full Documentation](https://stancld.github.io/rossum-agents/)
- [API Reference](https://stancld.github.io/rossum-agents/api-reference/)
- [MCP Server README](../rossum-mcp/README.md)
- [Rossum API Documentation](https://rossum.app/api/docs/)
- [Main Repository](https://github.com/rossumai/rossum-agents)
