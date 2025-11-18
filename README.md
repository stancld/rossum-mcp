# Rossum MCP Server & Rossum Agent

<div align="center">

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-mcp/)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![Rossum SDK](https://img.shields.io/badge/Rossum-SDK-orange.svg)](https://github.com/rossumai/rossum-sdk)
[![codecov](https://codecov.io/gh/stancld/rossum-mcp/branch/master/graph/badge.svg)](https://codecov.io/gh/stancld/rossum-mcp)

</div>

A Model Context Protocol (MCP) server and AI agent toolkit for intelligent document processing with Rossum. Upload documents, extract data with AI, and create visualizations - all through simple conversational prompts.

> [!NOTE]
> This is not an official Rossum project. It is a community-developed integration built on top of the Rossum API.

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
<summary><strong>Example 3: Bulk Processing & Visualization</strong></summary>

Process multiple invoices and generate revenue analysis charts through a single conversational prompt:

```md
1. Upload all invoices from `/path/to/examples/data` folder to Rossum queue 3901094
   - Do not include documents from `knowledge` folder
2. Once you send all annotations, wait for a few seconds
3. Then, start checking annotation status. Once all are imported, return a list of all annotations_urls
4. Fetch the schema for the target queue
5. Identify the schema field IDs for:
   - Line item description field
   - Line item total amount field
6. Retrieve all annotations in 'to_review' state from queue 3901094
7. For each document:
   - Extract all line items
   - Create a dictionary mapping {item_description: item_amount_total}
   - If multiple line items share the same description, sum their amounts
   - Print result for each document
8. Aggregate across all documents: sum amounts for each unique description
9. Return the final dictionary: {description: total_amount_across_all_docs}
10. Using the retrieved data, generate bar plot displaying revenue by services.
    Sort it in descending order. Store it interactive `revenue.html`.
```

<div align="center">
  <img src="revenue.png" alt="Revenue by Services Chart" width="700">
</div>

**Result:** Automatically processes 30 invoices and generates an interactive visualization showing revenue breakdown by service category.

See the [complete example](examples/PROMPT.md) for the full prompt and results.

</details>

<details>
<summary><strong>Example 4: Queue Setup with Knowledge Warmup</strong></summary>

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

## Installation

**Prerequisites**: Python 3.10+, Rossum account with API credentials

This repository contains two packages:
- **rossum_mcp**: MCP server for Rossum API interactions
- **rossum_agent**: AI agent with data manipulation and visualization tools

### Docker (Recommended)

```bash
git clone https://github.com/stancld/rossum-mcp.git
cd rossum-mcp

# Set up environment variables
export ROSSUM_API_TOKEN="your-api-token"
export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
export ROSSUM_MCP_MODE="read-write"  # Optional: "read-only" or "read-write" (default)

# Run the agent with Streamlit UI
docker-compose up rossum-agent
```

<details>
<summary>Install from source (alternative)</summary>

```bash
git clone https://github.com/stancld/rossum-mcp.git
cd rossum-mcp

# Install both packages with all features
uv sync --extra all --no-install-project

# Set up environment variables
export ROSSUM_API_TOKEN="your-api-token"
export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
export ROSSUM_MCP_MODE="read-write"  # Optional: "read-only" or "read-write" (default)
```

For individual package installation or other options, see [rossum_mcp/README.md](rossum_mcp/README.md) and [rossum_agent/README.md](rossum_agent/README.md).

</details>

## Usage

### AI Agent

```bash
# Docker (recommended)
docker-compose up rossum-agent

# CLI interface
rossum-agent

# Streamlit web UI
uv run streamlit run rossum_agent/app.py
```

> **Note:** The Streamlit UI is currently hard-coded for AWS Bedrock usage. You need to configure AWS credentials:
> ```bash
> export AWS_ACCESS_KEY_ID="your-access-key"
> export AWS_SECRET_ACCESS_KEY="your-secret-key"
> export AWS_DEFAULT_REGION="your-region"  # e.g., us-east-1
> ```

The agent includes file system tools, plotting capabilities, and Rossum integration. See [examples/](examples/) for complete workflows.

<details>
<summary>MCP Server with Claude Desktop</summary>

Configure Claude Desktop to use the MCP server:

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

</details>

<details>
<summary>Running with Elasticsearch Logging and Kibana UI</summary>

To run the application locally with Elasticsearch logging and Kibana UI for monitoring:

**Standard (amd64) systems:**
```bash
# Set the required encryption key (32+ random characters)
export XPACK_ENCRYPTEDSAVEDOBJECTS_ENCRYPTIONKEY="your-32-character-encryption-key-here"

# Start the agent with Kibana UI
docker-compose up rossum-agent kibana
```

**ARM Mac alternative:**
```bash
# Set the required encryption key (32+ random characters)
export XPACK_ENCRYPTEDSAVEDOBJECTS_ENCRYPTIONKEY="your-32-character-encryption-key-here"

# Start the ARM-compatible services
docker-compose up rossum-agent-mac kibana-mac
```

> **Note:** The `XPACK_ENCRYPTEDSAVEDOBJECTS_ENCRYPTIONKEY` environment variable must be specified before starting Kibana. This key is used to encrypt saved objects in Kibana and must be at least 32 characters long.

Once running:
- **Application UI**: http://localhost:8501
- **Kibana Dashboard**: http://localhost:5601
- **Elasticsearch**: http://localhost:9200

The services include health checks and will wait for Elasticsearch to be fully ready before starting the dependent services.

</details>

## MCP Tools

The MCP server provides 20 tools organized into five categories:

**Document Processing (6 tools)**
- `upload_document` - Upload documents for AI extraction
- `get_annotation` - Retrieve extracted data and status
- `list_annotations` - List all annotations with filtering
- `start_annotation` - Start annotation for field updates
- `bulk_update_annotation_fields` - Update field values with JSON Patch
- `confirm_annotation` - Confirm and finalize annotations

**Queue Management (5 tools)**
- `get_queue` - Retrieve queue details
- `get_queue_schema` - Retrieve queue schema in one call
- `get_queue_engine` - Get engine information
- `create_queue` - Create new queues
- `update_queue` - Configure automation thresholds

**Schema Management (3 tools)**
- `get_schema` - Retrieve schema details
- `create_schema` - Create new schemas
- `update_schema` - Configure field-level thresholds

**Engine Management (3 tools)**
- `create_engine` - Create extraction or splitting engines
- `update_engine` - Configure learning and training queues
- `create_engine_field` - Define engine fields and link to schemas

**Automation Management (3 tools)**
- `list_hooks` - List webhooks and extensions
- `create_hook` - Create new hooks/extensions
- `list_rules` - List validation rules

For detailed API documentation, parameters, and workflows, see the [full documentation](https://stancld.github.io/rossum-mcp/).

## Documentation

- [Full Documentation](https://stancld.github.io/rossum-mcp/) - Complete API reference and guides
- [MCP Server](rossum_mcp/README.md) - Server setup and configuration
- [AI Agent](rossum_agent/README.md) - Agent features and interfaces
- [Examples](examples/README.md) - Working examples and tutorials

## Resources

- [Rossum API](https://elis.rossum.ai/api/docs/) - Official API documentation
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP specification
- [Rossum SDK](https://github.com/rossumai/rossum-sdk) - Python SDK
- [Smolagents](https://github.com/huggingface/smolagents) - Agent framework

## License

MIT License - see [LICENSE](LICENSE) for details. Contributions welcome via issues and pull requests.
