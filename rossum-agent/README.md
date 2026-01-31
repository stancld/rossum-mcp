# Rossum Agent

<div align="center">

**AI agent for Rossum document processing. Debug hooks, deploy configs, and automate workflows conversationally.**

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-agents/)
[![Python](https://img.shields.io/pypi/pyversions/rossum-agent.svg)](https://pypi.org/project/rossum-agent/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI - rossum-agent](https://img.shields.io/pypi/v/rossum-agent?label=rossum-agent)](https://pypi.org/project/rossum-agent/)
[![Coverage](https://codecov.io/gh/stancld/rossum-agents/branch/master/graph/badge.svg?flag=rossum-agent)](https://codecov.io/gh/stancld/rossum-agents)

[![Rossum API](https://img.shields.io/badge/Rossum-API-orange.svg)](https://github.com/rossumai/rossum-api)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![Claude Opus 4.5](https://img.shields.io/badge/Claude-Opus_4.5-blueviolet.svg)](https://www.anthropic.com/claude/opus)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

</div>

> [!NOTE]
> Community-developed integration (not official Rossum). Follows semantic versioning from 1.0.0.

## Features

| Capability | Description |
|------------|-------------|
| **Rossum MCP Integration** | Full access to 50 MCP tools for document processing |
| **Hook Debugging** | Sandboxed execution with Opus sub-agent analysis |
| **Deployment Tools** | Pull, push, diff, copy configs across environments |
| **Knowledge Base Search** | AI-powered Rossum documentation search |
| **Multi-Environment** | Spawn connections to different Rossum environments |
| **Skills System** | Load domain-specific workflows on demand |

**Interfaces:** Streamlit UI, REST API, Python SDK

## Quick Start

```bash
# Set environment variables
export ROSSUM_API_TOKEN="your-api-token"
export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
export AWS_PROFILE="default"  # For Bedrock

# Run the agent
uv pip install rossum-agent[streamlit]
uv cache clean rossum-agent  # Re-init if upgrading
rossum-agent
```

Or with Docker:
```bash
docker-compose up rossum-agent
# Open http://localhost:8501
```

## Installation

```bash
git clone https://github.com/stancld/rossum-agents.git
cd rossum-mcp/rossum-agent
uv sync
```

**With extras:**
```bash
uv sync --extra all        # All extras (api, streamlit, docs, tests)
uv sync --extra api        # REST API (FastAPI, Redis)
uv sync --extra streamlit  # Streamlit UI only
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ROSSUM_API_TOKEN` | Yes | Rossum API authentication token |
| `ROSSUM_API_BASE_URL` | Yes | Base URL (e.g., `https://api.elis.rossum.ai/v1`) |
| `AWS_PROFILE` | Yes | AWS profile for Bedrock access |
| `AWS_DEFAULT_REGION` | No | AWS region (default: `us-east-1`) |
| `REDIS_HOST` | No | Redis host for chat persistence |
| `REDIS_PORT` | No | Redis port (default: `6379`) |

## Usage

### Streamlit UI

```bash
rossum-agent
# Or: streamlit run rossum_agent/streamlit_app/app.py
```

### REST API

```bash
rossum-agent-api --host 0.0.0.0 --port 8000
```

### Python SDK

```python
import asyncio
from rossum_agent.agent import create_agent
from rossum_agent.rossum_mcp_integration import create_mcp_connection

async def main():
    mcp_connection = await create_mcp_connection()
    agent = await create_agent(mcp_connection=mcp_connection)

    async for step in agent.run("List all queues"):
        if step.final_answer:
            print(step.final_answer)

asyncio.run(main())
```

## Available Tools

The agent provides internal tools and access to 50+ MCP tools via dynamic loading.

<details>
<summary><strong>Internal Tools</strong></summary>

**File & Knowledge:**
- `write_file` - Save reports, documentation, analysis results
- `search_knowledge_base` - Search Rossum docs with AI analysis

**Hook Analysis:**
- `evaluate_python_hook` - Execute hooks in sandboxed environment
- `debug_hook` - Expert debugging with Opus sub-agent

**Schema:**
- `patch_schema_with_subagent` - Safe schema modifications via Opus

**Deployment:**
- `deploy_pull` - Pull configs from organization
- `deploy_diff` - Compare local vs remote
- `deploy_push` - Push local changes
- `deploy_copy_org` - Copy entire organization
- `deploy_copy_workspace` - Copy single workspace
- `deploy_compare_workspaces` - Compare two workspaces
- `deploy_to_org` - Deploy to target organization

**Multi-Environment:**
- `spawn_mcp_connection` - Connect to different Rossum environment
- `call_on_connection` - Call tools on spawned connection
- `close_connection` - Close spawned connection

**Skills:**
- `load_skill` - Load domain-specific workflows (`rossum-deployment`, `hook-debugging`)

</details>

<details>
<summary><strong>Dynamic MCP Tool Loading</strong></summary>

Tools are loaded on-demand to reduce context usage. Use `load_tool_category` to load tools by category:

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

Categories are auto-loaded based on keywords in the user's message.

</details>

## Architecture

```mermaid
flowchart TB
    subgraph UI["User Interface"]
        S[Streamlit UI]
        A[REST API]
    end

    subgraph Agent["Rossum Agent (Claude Bedrock)"]
        IT[Internal Tools]
        DT[Deploy Tools]
        MT[Spawn MCP Tools]
        SK[Skills System]
    end

    subgraph MCP["Rossum MCP Server"]
        Tools[50 MCP Tools]
    end

    API[Rossum API]

    UI --> Agent
    Agent --> MCP
    MCP --> API
```

<details>
<summary><strong>REST API Endpoints</strong></summary>

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/health` | Health check |
| `GET /api/v1/chats` | List all chats |
| `POST /api/v1/chats` | Create new chat |
| `GET /api/v1/chats/{id}` | Get chat details |
| `DELETE /api/v1/chats/{id}` | Delete chat |
| `POST /api/v1/chats/{id}/messages` | Send message (SSE) |
| `GET /api/v1/chats/{id}/files` | List files |
| `GET /api/v1/chats/{id}/files/{name}` | Download file |

API docs: `/api/docs` (Swagger) or `/api/redoc`

</details>

## License

MIT License - see [LICENSE](../LICENSE) for details.

## Resources

- [Full Documentation](https://stancld.github.io/rossum-agents/)
- [MCP Server README](../rossum-mcp/README.md)
- [Rossum API Documentation](https://rossum.app/api/docs/)
- [Main Repository](https://github.com/stancld/rossum-agents)
