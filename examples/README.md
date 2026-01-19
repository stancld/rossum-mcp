# Rossum Examples

This folder contains practical examples and data for demonstrating the Rossum MCP server and AI agent capabilities.

## What's in this folder

- **data/**: Sample invoice files for testing document processing
- **QUEUE_SETUP.md**: Guide for setting up Rossum queues
- **SORTING_WARMUP.md**: Multi-queue setup with sorting engine
- **SPLITTING_AND_SORTING_DEMO.md**: Full S&S demo with training queues, inbox, and hooks
- **CREATE_SAS_INBOX.md**: Quick inbox setup for Splitting & Sorting
- **EXPLAIN_HOOKS.md**: Example for explaining hook/extension functionality
- **EXPLAIN_RULES_AND_ACTIONS.md**: Example for explaining rules and actions
- **README.md**: This file

## Using the Rossum Agent

The examples in this folder work with the `rossum-agent` package, which uses Anthropic Claude to create an AI agent that can interact with the Rossum MCP server to upload and process invoices.

### Features

- 🤖 AI-powered agent that understands natural language commands
- 📁 Automatic detection of invoice files in the data folder
- 🔄 Batch processing support
- 💬 Interactive CLI interface
- ✅ Proper error handling and user feedback

### Setup

1. **Install the Rossum Agent package:**

```bash
# From the repository root
cd rossum-agent
uv sync --extra all
```

2. **Set environment variables:**

```bash
export ROSSUM_API_TOKEN="your_rossum_api_token"
export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
```

3. **Add invoice files:**

Place your invoice files (PDF, PNG, JPG) in the `examples/data/` folder:

```bash
cp ~/my-invoices/*.pdf examples/data/
```

### Usage

Run the agent CLI:

```bash
# From anywhere after installation
rossum-agent
```

Or run the Streamlit UI:

```bash
# From the rossum_agent directory
cd rossum-agent
streamlit run app.py
```

### Example Commands

Once the agent is running, you can say things like:

- "Upload all invoices from examples/data folder to Rossum to queue <queue_id>."
- "Check the status of all annotations in queue <queue_id>."
- "List all annotations that are ready for review in queue <queue_id>."
- "Wait until all uploaded documents finish processing in queue <queue_id>."

### How it Works

1. **MCP Integration**: The agent connects to the Rossum MCP server to access document processing capabilities
2. **Tool Suite**: The agent has access to file writing tools and Rossum API operations via MCP
3. **Natural Language**: The agent interprets your commands and calls the appropriate tools automatically
4. **Batch Processing**: The agent can handle multiple files and operations intelligently

### Understanding Annotation States

When documents are uploaded to Rossum, they go through a processing workflow:

- **importing** → Initial state after upload. Document is being processed by Rossum.
- **to_review** → Extraction complete. Document is ready for validation.
- **confirmed** → Document has been validated and confirmed.
- **exported** → Optional (Final state for successfully processed documents).

**Best Practice for Bulk Uploads**:
1. Upload all documents using `upload_document`
2. Once all uploads complete, use `list_annotations` with the queue ID to check which documents have finished processing
3. Poll until all annotations reach `to_review`, `confirmed`, or `exported` status

### Architecture

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

## Troubleshooting

### "ROSSUM_API_TOKEN not set"
Make sure you've exported the environment variable:
```bash
export ROSSUM_API_TOKEN="your_token_here"
```

### "No invoice files found"
Add some PDF, PNG, or JPG files to the `examples/data/` folder.

### "Connection refused"
Ensure the Rossum MCP server is running. Start it with:
```bash
cd rossum_mcp
python server.py
```

Or use the installed script:
```bash
rossum-mcp
```

### Package installation issues
Make sure you have Python 3.12+ and install the agent package:
```bash
cd rossum-agent
uv sync --extra all
```

## License

MIT License - see [LICENSE](../LICENSE) file for details.

## Resources

- [Rossum Agent README](../rossum-agent/README.md)
- [Rossum MCP README](../rossum-mcp/README.md)
- [Full Documentation](https://stancld.github.io/rossum-agents/)
