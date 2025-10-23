# Rossum Examples

This folder contains practical examples and data for demonstrating the Rossum MCP server and AI agent capabilities.

## What's in this folder

- **data/**: Sample invoice files for testing document processing
- **DATA_INSIGHT.md**: Documentation of the data aggregation example
- **QUEUE_SETUP.md**: Guide for setting up Rossum queues
- **README.md**: This file

## Using the Rossum Agent

The examples in this folder work with the `rossum-agent` package, which uses [smolagents](https://github.com/huggingface/smolagents) to create an AI agent that can interact with the Rossum MCP server to upload and process invoices.

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
cd rossum_agent
pip install -e ".[all]"
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
cd rossum_agent
streamlit run app.py
```

### Example Commands

Once the agent is running, you can say things like:

- "Upload all invoices from /Users/daniel.stancl/projects/rossum-mcp/examples/data folder to Rossum to the queue <queue_id>."
- "Check the status of all annotations in queue <queue_id>."
- "List all annotations that are ready for review in queue <queue_id>."
- "Wait until all uploaded documents finish processing in queue <queue_id>."

### How it Works

1. **MCP Integration**: The agent connects to the Rossum MCP server to access document processing capabilities
2. **Tool Suite**: The agent has access to file system tools, plotting tools, and Rossum API operations
3. **Natural Language**: The agent interprets your commands and calls the appropriate tools automatically
4. **Batch Processing**: The agent can handle multiple files and operations intelligently
5. **Visualization**: The agent can create interactive charts from extracted data using Plotly

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
│ (Smolagents)    │
├─────────────────┤
│ • File Tools    │
│ • Plot Tools    │
│ • Rossum Tools  │
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
Make sure you have Python 3.10+ and install the agent package:
```bash
cd rossum_agent
pip install -e ".[all]"
```
