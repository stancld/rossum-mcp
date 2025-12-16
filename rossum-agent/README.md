# Rossum Agent

<div align="center">

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-mcp/)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Anthropic](https://img.shields.io/badge/Anthropic-Claude-blueviolet.svg)](https://www.anthropic.com/)

</div>

AI agent for Rossum document processing. Built with Anthropic Claude and designed to work seamlessly with the Rossum MCP server.

## Features

### Agent Capabilities
- **Rossum Integration**: Connect to Rossum MCP server for document processing
- **File Output**: Write reports, documentation, and analysis results to files
- **Claude Code Execution**: Leverage Claude's native code execution for data analysis, plotting, and complex computations
- **Image Input Support**: Attach images (PNG, JPEG, GIF, WebP) to messages for visual context and analysis

### User Interfaces
- **CLI**: Command-line interface for interactive agent conversations
- **Streamlit UI**: Web-based interface for a more visual experience

## Prerequisites

- Python 3.10 or higher
- Rossum MCP server (optional, for document processing features)
- Rossum account with API credentials (if using Rossum features)

## Installation

### Install from source

```bash
git clone https://github.com/stancld/rossum-mcp.git
cd rossum-mcp/rossum_agent
uv sync
```

### Install with extras

```bash
uv sync --extra all  # All extras (streamlit, docs, tests)
uv sync --extra streamlit  # Streamlit UI only
uv sync --extra docs  # Documentation only
uv sync --extra tests  # Testing only
```

### Set up environment variables

If using Rossum features:
```bash
export ROSSUM_API_TOKEN="your-api-token"
export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
```

## Usage

### Running the Agent (CLI)

Start the interactive agent using:
```bash
rossum-agent
```

Or run directly:
```bash
python -m rossum_agent.main
```

### Running the Streamlit UI

If you installed with the streamlit extra:
```bash
streamlit run rossum_agent/app.py
```

### Using in Python Scripts

```python
import os
from rossum_agent.agent import create_agent

# Set Bedrock model (optional, uses default if not set)
os.environ["LLM_MODEL_ID"] = "bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0"

# Create an agent (requires AWS credentials configured)
agent = create_agent()

# Use the agent
result = agent.run("Analyze the hooks on queue 12345 and explain their execution order")
```

## Available Tools

### File System Tools

#### write_file
Write text or markdown content to a file. Use this to save documentation, reports, diagrams, or any text output.

**Parameters:**
- `filename` (string): The name of the file to create (e.g., 'report.md', 'hooks.txt')
- `content` (string): The text content to write to the file

### Knowledge Base Tools

#### search_knowledge_base
Search the Rossum Knowledge Base for documentation about extensions, hooks, and configurations.

**Parameters:**
- `query` (string, required): Search query. Be specific - include extension names, error messages, or feature names. Examples: 'document splitting extension', 'duplicate handling configuration', 'webhook timeout error'.
- `user_query` (string, optional): The original user question for context. Pass the user's full question here so Opus can tailor the analysis to address their specific needs.

**Returns:** JSON with search results containing title, URL, and analyzed content from the knowledge base.

**Use cases:**
- Finding documentation about Rossum extensions
- Troubleshooting error messages
- Understanding hook configurations and behaviors

### Hook Analysis Tools

#### evaluate_python_hook
Execute Rossum function hook Python code against test annotation/schema data for debugging. This tool runs hook code in a restricted sandbox to verify logic without making actual API calls.

**Parameters:**
- `code` (string, required): Full Python source containing a `rossum_hook_request_handler(payload)` function
- `annotation_json` (string, required): JSON string of the annotation object (get from `get_annotation` MCP tool)
- `schema_json` (string, optional): JSON string of the schema object (get from `get_schema` MCP tool)

**Returns:** JSON with structure:
```json
{
  "status": "success" | "error" | "invalid_input",
  "result": "<return value from handler>",
  "stdout": "<captured print statements>",
  "stderr": "<captured stderr>",
  "exception": {"type": "...", "message": "...", "traceback": "..."} | null,
  "elapsed_ms": 5.123
}
```

**Limitations:**
- No imports allowed (sandboxed environment)
- No file I/O (`open()` is blocked)
- Limited builtins (safe subset for data manipulation)

#### debug_hook
**Expert-level hook debugging with Claude Opus sub-agent.** This tool combines code execution with deep reasoning from Claude Opus 4 to provide comprehensive debugging analysis.

**How it works:**
1. Executes the hook code against test data (using `evaluate_python_hook`)
2. Sends code, data, and execution results to Claude Opus 4 for analysis
3. Returns expert debugging insights, root cause analysis, and fix suggestions

**Parameters:**
- `code` (string, required): Full Python source containing a `rossum_hook_request_handler(payload)` function
- `annotation_json` (string, required): JSON string of the annotation object
- `schema_json` (string, optional): JSON string of the schema object

**Returns:** JSON with structure:
```json
{
  "execution": {
    "status": "success" | "error",
    "result": "<return value>",
    "exception": {...} | null
  },
  "analysis": "<Opus expert analysis with debugging insights and fixes>",
  "elapsed_ms": 2500.0
}
```

**Use cases:**
- Complex hook logic that's failing with unclear errors
- Understanding what a hook does and how to fix it
- Getting best practice recommendations for hook code

### Rossum MCP Tools

When configured with the Rossum MCP server, the agent can use all MCP tools including:
- Upload documents to Rossum
- Monitor processing status
- Retrieve and parse annotation data
- Manage queues, schemas, hooks, and engines

See the [MCP Server README](../rossum-mcp/README.md) for the complete list of available MCP tools.

## Real-World Use Case

Imagine you have 30 invoices to process for a board meeting in 10 minutes. With Rossum Agent, you can:

1. Upload all 30 invoices in bulk to Rossum
2. Wait for automatic AI extraction
3. Aggregate data across all documents
4. Generate analysis and reports

All with a simple conversational prompt. See the [main repository](https://github.com/stancld/rossum-mcp) for complete examples.

## Example Commands

Once the agent is running, you can say things like:

- "Upload all invoices from /path/to/invoices to Rossum queue 12345"
- "Analyze the hooks on queue 12345 and explain their execution order"
- "List all annotations in queue 12345 and summarize their status"
- "Create a report documenting the schema for queue 12345"

## Configuration

The agent uses a configuration file at `rossum_agent/assets/agent_config.yaml`. You can customize:

- Model settings
- Tool availability
- System prompts and instructions
- Memory settings

## Architecture

```
┌─────────────┐
│    User     │
│  Interface  │
│ (CLI/Web)   │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ Rossum Agent    │
│ (Claude)        │
├─────────────────┤
│ • Write File    │
│ • MCP Tools     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────┐
│  Rossum MCP     │─────▶│  Rossum API  │
│    Server       │      └──────────────┘
└─────────────────┘
```

## Error Handling

The agent provides clear error messages for:
- File not found errors
- Invalid data formats
- API connection issues
- Tool execution failures

## License

MIT License - see LICENSE file for details

## Resources

- [Anthropic Claude Documentation](https://docs.anthropic.com/)
- [Rossum API Documentation](https://elis.rossum.ai/api/docs/)
- [Main Repository](https://github.com/stancld/rossum-mcp)
- [Full Documentation](https://stancld.github.io/rossum-mcp/)
