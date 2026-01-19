# Rossum MCP Server & Rossum Agent

<div align="center">

**AI-powered Rossum orchestration: Document workflows conversationally, debug pipelines automatically, and configure automation through natural language.**

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-agents/)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/downloads/)
[![PyPI - rossum-mcp](https://img.shields.io/pypi/v/rossum-mcp?label=rossum-mcp)](https://pypi.org/project/rossum-mcp/)
[![PyPI - rossum-deploy](https://img.shields.io/pypi/v/rossum-deploy?label=rossum-deploy)](https://pypi.org/project/rossum-deploy/)
[![MCP Tools](https://img.shields.io/badge/MCP_Tools-50-blue.svg)](#available-tools)

[![codecov](https://codecov.io/gh/stancld/rossum-agents/branch/master/graph/badge.svg)](https://codecov.io/gh/stancld/rossum-agents)
[![CodeQL](https://github.com/stancld/rossum-agents/actions/workflows/codeql.yaml/badge.svg)](https://github.com/stancld/rossum-agents/actions/workflows/codeql.yaml)
[![Snyk Security](https://github.com/stancld/rossum-agents/actions/workflows/snyk.yaml/badge.svg)](https://github.com/stancld/rossum-agents/actions/workflows/snyk.yaml)
[![CodeFactor](https://www.codefactor.io/repository/github/stancld/rossum-agents/badge)](https://www.codefactor.io/repository/github/stancld/rossum-agents)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Rossum API](https://img.shields.io/badge/Rossum-API-orange.svg)](https://github.com/rossumai/rossum-api)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![Claude Opus 4.5](https://img.shields.io/badge/Claude-Opus_4.5-blueviolet.svg)](https://www.anthropic.com/claude/opus)

</div>

Conversational AI toolkit for the Rossum intelligent document processing platform. Transforms complex workflow setup, debugging, and configuration into natural language conversations through a Model Context Protocol (MCP) server and specialized AI agent.

> [!NOTE]
> Community-developed integration (not official Rossum). Early stage - breaking changes expected.

## ✨ What Can You Do?

<details>
<summary><strong>Example 1: Aurora Splitting & Sorting Demo</strong></summary>

Set up a complete document splitting and sorting pipeline with training queues, splitter engine, automated hooks, and intelligent routing:

```md
1. Create three new queues in workspace `1777693` - Air Waybills, Certificates of Origin, Invoices.
2. Set up the schema with a single enum field on each queue with a name Document type (`document_type`).
3. Upload documents from folders air_waybill, certificate_of_origin, invoice in `examples/data/splitting_and_sorting/knowledge` to corresponding queues.
4. Annotate all uploaded documents with a correct Document type, and confirm the annotation.
    - Beware document types are air_waybill, invoice and certificate_of_origin (lower-case, underscores).
    - IMPORTANT: After confirming all annotations, double check, that all are confirmed/exported, and fix those that are not.
5. Create three new queues in workspace `1777693` - Air Waybills Test, Certificates of Origin Test, Invoices Test.
6. Set up the schema with a single enum field on each queue with a name Document type (`document_type`).
7. Create a new engine in organization `1`, with type = 'splitter'.
8. Configure engine training queues to be - Air Waybills, Certificates of Origin, Invoices.
    - DO NOT copy knowledge.
    - Update Engine object.
9. Create a new schema that will be the same as the schema from the queue `3885208`.
10. Create a new queue (with splitting UI feature flag!) with the created engine and schema in the same workspace called: Inbox.
11. Create a python function-based the **`Splitting & Sorting`** hook on the new inbox queue with this settings:
    **Functionality**: Automatically splits multi-document uploads into separate annotations and routes them to appropriate queues.
    Split documents should be routed to the following queues: Air Waybills Test, Certificates of Origin Test, Invoices Test

    **Trigger Events**:
    - annotation_content.initialize (suggests split to user)
    - annotation_content.confirm (performs actual split)
    - annotation_content.export (performs actual split)

    **How it works**: Python code

    **Settings**:
    - sorting_queues: Maps document types to target queue IDs for routing
    - max_blank_page_words: Threshold for blank page detection (pages with fewer words are considered blank)
12. Upload 10 documents from `examples/data/splitting_and_sorting/testing` folder to inbox queues.
```

**What This Demonstrates:**

- **Queue Orchestration**: Creates 7 queues (3 training + 3 test + 1 inbox) with consistent schemas
- **Knowledge Warmup**: Uploads and annotates 90 training documents to teach the engine
- **Splitter Engine**: Configures an AI engine to detect document boundaries and types
- **Hook Automation**: Sets up a sophisticated webhook that automatically:

  - Splits multi-document PDFs into individual annotations
  - Removes blank pages intelligently
  - Routes split documents to correct queues by type
  - Suggests splits on initialization and executes on confirmation

- **End-to-End Testing**: Validates the entire pipeline with test documents

This example showcases the agent's ability to orchestrate complex workflows involving multiple queues, engines, schemas, automated hooks with custom logic, and intelligent document routing - all from a single conversational prompt.

</details>

<details>
<summary><strong>Example 2: Hook Analysis & Documentation</strong></summary>

Automatically analyze and document all hooks/extensions configured on a queue:

```md
Briefly explain the functionality of every hook based on description and/or code one by one for a queue `2042843`.

Store output in extension_explanation.md
```

**What This Does:**
- Lists all hooks/extensions on the specified queue
- Analyzes each hook's description and code
- Generates clear, concise explanations of functionality
- Documents trigger events and settings
- Saves comprehensive documentation to a markdown file

This example shows how the agent can analyze existing automation to help teams understand their configured workflows.

</details>

<details>
<summary><strong>Example 3: Queue Setup with Knowledge Warmup</strong></summary>

Create a new queue, warm it up with training documents, and test automation performance:

```md
1. Create a new queue in the same namespace as queue `3904204`
2. Set up the same schema field as queue `3904204`
3. Update schema so that everything with confidence > 90% will be automated
4. Rename the queue to: MCP Air Waybills
5. Copy the queue knowledge from `3904204`
6. Return the queue status to check the queue status
7. Upload all documents from `examples/data/splitting_and_sorting/knowledge/air_waybill`
   to the new queue
8. Wait until all annotations are processed
9. Finally, return queue URL and an automation rate (exported documents)
```

**Result:**

```json
{
  "queue_url": "https://api.elis.rossum.ai/v1/queues/3920572",
  "queue_id": 3920572,
  "queue_name": "MCP Air Waybills",
  "total_documents": 30,
  "exported_documents": 26,
  "to_review_documents": 4,
  "automation_rate_percent": 86.7
}
```

The agent automatically creates the queue, uploads documents, monitors processing, and calculates automation performance - achieving **86.7% automation rate** from just 30 training documents.

</details>

## 📦 Repository Structure

This repository contains four standalone Python packages:

- **[rossum-mcp/](rossum-mcp/)** - MCP server for Rossum API integration with AI assistants
- **[rossum-agent/](rossum-agent/)** - Specialized AI agent toolkit with Streamlit UI
- **[rossum-agent-client/](rossum-agent-client/)** - Typed Python client for the Rossum Agent API
- **[rossum-deploy/](rossum-deploy/)** - Minimalistic pull/diff/push deployment tool (lightweight alternative to [deployment-manager](https://github.com/rossumai/deployment-manager))

Each package can be installed and used independently or together for complete functionality.

## 🚀 Quick Start

```bash
# Clone and run with Docker
git clone https://github.com/stancld/rossum-agents.git && cd rossum-mcp
echo "ROSSUM_API_TOKEN=your-token" > .env
echo "ROSSUM_API_BASE_URL=https://api.elis.rossum.ai/v1" >> .env
docker-compose up rossum-agent
# Open http://localhost:8501
```

## 📦 Installation & Usage

**Prerequisites**: Python 3.12+, [Rossum account](https://rossum.ai/) with [API credentials](https://rossum.app/api/docs/#authentication)

### 🐳 Docker Compose (Recommended)

**Best for**: Local development and quick testing

```bash
git clone https://github.com/stancld/rossum-agents.git
cd rossum-mcp

# Create .env file with required variables
cat > .env << EOF
ROSSUM_API_TOKEN=your-api-token
ROSSUM_API_BASE_URL=https://api.elis.rossum.ai/v1
ROSSUM_MCP_MODE=read-write
AWS_PROFILE=default
AWS_DEFAULT_REGION=us-east-1
EOF

# Run the agent with Streamlit UI
docker-compose up rossum-agent
```

Access the application at **http://localhost:8501**

#### With Redis Logging

For production-like monitoring locally:

**All systems:**
```bash
# Start with logging stack
docker-compose up rossum-agent redis
```

**ARM Mac (M1/M2/M3):**
```bash
# Start ARM-compatible services
docker-compose up rossum-agent-mac redis
```

Access points:
- **Application**: http://localhost:8501
- **Redis**: localhost:6379

View logs with:
```bash
redis-cli LRANGE logs:$(date +%Y-%m-%d) 0 -1
```

---

### 📦 From Source

**Best for**: Development, customization, contributing

```bash
git clone https://github.com/stancld/rossum-agents.git
cd rossum-mcp

# Install all packages with all features
uv sync --all-extras

# Set up environment variables
export ROSSUM_API_TOKEN="your-api-token"
export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
export ROSSUM_MCP_MODE="read-write"

# Run the agent
rossum-agent                                    # CLI interface
uv run streamlit run rossum_agent/app.py        # Web UI
```

For individual package details, see [rossum-mcp/README.md](rossum-mcp/README.md), [rossum-agent/README.md](rossum-agent/README.md), and [rossum-deploy/README.md](rossum-deploy/README.md).

---

### 💬 MCP Server with Claude Desktop

**Best for**: Interactive use with Claude Desktop

Configure Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json` on Mac):

```json
{
  "mcpServers": {
    "rossum": {
      "command": "python",
      "args": ["/path/to/rossum-mcp/rossum_mcp/server.py"],
      "env": {
        "ROSSUM_API_TOKEN": "your-api-token",
        "ROSSUM_API_BASE_URL": "https://api.elis.rossum.ai/v1",
        "ROSSUM_MCP_MODE": "read-write"
      }
    }
  }
}
```

Or run standalone: `rossum-mcp`

---

### 🤖 AI Agent Interfaces

```bash
# Docker (recommended for local)
docker-compose up rossum-agent

# CLI interface (from source)
rossum-agent

# Streamlit web UI (from source)
uv run streamlit run rossum_agent/app.py
```

> **AWS Bedrock Note:** The Streamlit UI uses AWS Bedrock by default. Configure AWS credentials:
> ```bash
> export AWS_PROFILE=default
> export AWS_DEFAULT_REGION=us-east-1
> ```
> Or mount credentials in Docker: `~/.aws:/root/.aws:ro`

The agent includes file writing tools and Rossum integration via MCP. See [examples/](examples/) for complete workflows.

## 🧠 Agent Skills & Sub-Agents

The Rossum Agent includes specialized capabilities for complex workflows:

<details>
<summary><strong>Show skills and sub-agents</strong></summary>

**Skills** - Domain-specific instructions loaded on-demand via `load_skill`:

| Skill | Purpose |
|-------|---------|
| `rossum-deployment` | Deploy configuration changes safely via sandbox with before/after diff |
| `hook-debugging` | Identify and fix hook issues using knowledge base and Opus sub-agent |
| `schema-patching` | Add, update, or remove individual schema fields |
| `schema-pruning` | Remove unwanted fields from schema in one call |
| `organization-setup` | Set up Rossum for new customers with regional templates |
| `ui-settings` | Update queue UI settings without corrupting structure |

**Sub-Agents** - Opus-powered components for complex iterative tasks:

| Sub-Agent | Invoked Via | Purpose |
|-----------|-------------|---------|
| Hook Debug | `debug_hook(hook_id, annotation_id)` | Iterative hook debugging with sandboxed code execution |
| Knowledge Base | `search_knowledge_base(query)` | Search Rossum docs with Opus-powered analysis |
| Schema Patching | `patch_schema_with_subagent(schema_id, changes)` | Programmatic bulk schema modifications |

See the [full documentation](https://stancld.github.io/rossum-agents/skills_and_subagents.html) for details.

</details>

## 🔌 MCP Tools

The MCP server provides **50 tools** for document processing, queue/schema management, hooks, engines, and more.

| Category | Tools | Description |
|----------|-------|-------------|
| Document Processing | 6 | Upload, retrieve, update, confirm annotations |
| Queue Management | 8 | Create, configure, list queues |
| Schema Management | 7 | Define and modify field structures |
| Engine Management | 6 | Extraction and splitting engines |
| Extensions & Rules | 9 | Webhooks, serverless functions, rules |
| Other | 14 | Workspaces, users, relations, email templates |

See [rossum-mcp/README.md](rossum-mcp/README.md) for the tool list and [rossum-mcp/TOOLS.md](rossum-mcp/TOOLS.md) for detailed API documentation.

## 📚 Documentation

- **[Full Documentation](https://stancld.github.io/rossum-agents/)** - Complete guides and API reference
- **[MCP Server README](rossum-mcp/README.md)** - MCP server setup and tools
- **[Agent README](rossum-agent/README.md)** - Agent toolkit and UI usage
- **[Deploy README](rossum-deploy/README.md)** - Deployment tool usage
- **[Examples](examples/)** - Sample workflows and use cases

## 🔗 Resources

- [Rossum API](https://rossum.app/api/docs/) - Official API documentation
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP specification
- [Rossum SDK](https://github.com/rossumai/rossum-sdk) - Python SDK
- [Deployment Manager (PRD2)](https://github.com/rossumai/deployment-manager) - Full-featured deployment CLI


## 🛠️ Development

```bash
# Install with all development dependencies
pip install -e rossum-mcp[all] -e rossum-agent[all]

# Run tests
pytest

# Run regression tests (validates agent behavior)
pytest regression_tests/ -v -s

# Lint and type check
pre-commit run --all-files
```

See [regression_tests/README.md](regression_tests/README.md) for the agent quality evaluation framework.

## 📄 License

MIT License - see [LICENSE](LICENSE) for details

## 🤝 Contributing

Contributions welcome! See individual package READMEs for development guidelines.
