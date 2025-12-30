# Rossum MCP Server & Rossum Agent

<div align="center">

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-mcp/)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![MCP Tools](https://img.shields.io/badge/MCP_Tools-39-blue.svg)](#available-tools)
[![Rossum API](https://img.shields.io/badge/Rossum-API-orange.svg)](https://github.com/rossumai/rossum-api)
[![codecov](https://codecov.io/gh/stancld/rossum-mcp/branch/master/graph/badge.svg)](https://codecov.io/gh/stancld/rossum-mcp)
[![CodeQL](https://github.com/stancld/rossum-mcp/actions/workflows/codeql.yaml/badge.svg)](https://github.com/stancld/rossum-mcp/actions/workflows/codeql.yaml)
[![Snyk Security](https://github.com/stancld/rossum-mcp/actions/workflows/snyk.yaml/badge.svg)](https://github.com/stancld/rossum-mcp/actions/workflows/snyk.yaml)

**AI-powered Rossum orchestration: Document workflows conversationally, debug pipelines automatically, and configure automation through natural language.**

</div>

Conversational AI toolkit for the Rossum intelligent document processing platform. Transforms complex workflow setup, debugging, and configuration into natural language conversations through a Model Context Protocol (MCP) server and specialized AI agent.

## Vision & Roadmap

This project enables three progressive levels of AI-powered Rossum orchestration:

1. **📝 Workflow Documentation** *(In Progress)* - Conversationally document Rossum setups, analyze existing workflows, and generate comprehensive configuration reports through natural language prompts
2. **🔍 Automated Debugging** *(In Progress)* - Automatically diagnose pipeline issues, identify misconfigured hooks, detect schema problems, and suggest fixes through intelligent analysis
3. **🤖 Agentic Configuration** *(In Progress)* - Fully autonomous setup and optimization of Rossum workflows - from queue creation to engine training to hook deployment - guided only by high-level business requirements

> [!NOTE]
> This is not an official Rossum project. It is a community-developed integration built on top of the Rossum API.

> [!WARNING]
> This project is in early stage development. Breaking changes to both implementation and agent behavior are expected.

## What Can You Do?

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

This repository contains three standalone Python packages:

- **[rossum-mcp/](rossum-mcp/)** - MCP server for Rossum API integration with AI assistants
- **[rossum-agent/](rossum-agent/)** - Specialized AI agent toolkit with Streamlit UI
- **[rossum-deploy/](rossum-deploy/)** - Minimalistic pull/diff/push deployment tool (lightweight alternative to [deployment-manager](https://github.com/rossumai/deployment-manager))

Each package can be installed and used independently or together for complete functionality.

## 🚀 Installation & Usage

**Prerequisites**: Python 3.12+, Rossum account with API credentials

### 🐳 Docker Compose (Recommended)

**Best for**: Local development and quick testing

```bash
git clone https://github.com/stancld/rossum-mcp.git
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
git clone https://github.com/stancld/rossum-mcp.git
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

## Usage

### AI Agent Interfaces

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

## MCP Tools

The MCP server provides 39 tools organized into categories:

<details>
<summary><strong>Document Processing (6 tools)</strong></summary>

- `upload_document` - Upload documents for AI extraction
- `get_annotation` - Retrieve extracted data and status
- `list_annotations` - List all annotations with filtering
- `start_annotation` - Start annotation for field updates
- `bulk_update_annotation_fields` - Update field values with JSON Patch
- `confirm_annotation` - Confirm and finalize annotations

</details>

<details>
<summary><strong>Queue Management (5 tools)</strong></summary>

- `get_queue` - Retrieve queue details
- `get_queue_schema` - Retrieve queue schema in one call
- `get_queue_engine` - Get engine information
- `create_queue` - Create new queues
- `update_queue` - Configure automation thresholds

</details>

<details>
<summary><strong>Schema Management (4 tools)</strong></summary>

- `get_schema` - Retrieve schema details
- `create_schema` - Create new schemas
- `update_schema` - Configure field-level thresholds
- `patch_schema` - Add, update, or remove individual schema nodes

</details>

<details>
<summary><strong>Engine Management (6 tools)</strong></summary>

- `get_engine` - Retrieve engine details by ID
- `list_engines` - List all engines with optional filters
- `create_engine` - Create extraction or splitting engines
- `update_engine` - Configure learning and training queues
- `create_engine_field` - Define engine fields and link to schemas
- `get_engine_fields` - Retrieve engine fields for an engine

</details>

<details>
<summary><strong>Extensions & Rules (9 tools)</strong></summary>

- `get_hook` - Get hook/extension details
- `list_hooks` - List webhooks and extensions
- `create_hook` - Create new hooks/extensions
- `update_hook` - Update existing hook properties
- `list_hook_templates` - List available hook templates from Rossum Store
- `create_hook_from_template` - Create hook from a template
- `list_hook_logs` - List hook execution logs for debugging
- `get_rule` - Get business rule details
- `list_rules` - List validation rules

</details>

<details>
<summary><strong>Workspace Management (3 tools)</strong></summary>

- `get_workspace` - Retrieve workspace details
- `list_workspaces` - List all workspaces with filtering
- `create_workspace` - Create new workspaces

</details>

<details>
<summary><strong>User Management (3 tools)</strong></summary>

- `get_user` - Retrieve user details by ID
- `list_users` - List users with optional filtering
- `list_user_roles` - List all user roles (permission groups)

</details>

<details>
<summary><strong>Relations Management (4 tools)</strong></summary>

- `get_relation` - Retrieve annotation relation details
- `list_relations` - List relations (edit, attachment, duplicate)
- `get_document_relation` - Retrieve document relation details
- `list_document_relations` - List document relations (export, einvoice)

</details>

For detailed API documentation, parameters, and workflows, see the [full documentation](https://stancld.github.io/rossum-mcp/).

## 📚 Documentation

- **[Full Documentation](https://stancld.github.io/rossum-mcp/)** - Complete guides and API reference
- **[MCP Server README](rossum-mcp/README.md)** - MCP server setup and tools
- **[Agent README](rossum-agent/README.md)** - Agent toolkit and UI usage
- **[Deploy README](rossum-deploy/README.md)** - Deployment tool usage
- **[Examples](examples/)** - Sample workflows and use cases

## Resources

- [Rossum API](https://elis.rossum.ai/api/docs/) - Official API documentation
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
