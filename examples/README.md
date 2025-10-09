# Rossum MCP Server Examples

This folder contains practical examples demonstrating how to use the Rossum MCP server.

## Python Agent Example

The Python example uses [smolagents](https://github.com/huggingface/smolagents) to create an AI agent that can interact
with your Rossum MCP server to upload and process invoices.

### Features

- 🤖 AI-powered agent that understands natural language commands
- 📁 Automatic detection of invoice files in the data folder
- 🔄 Batch processing support
- 💬 Interactive CLI interface
- ✅ Proper error handling and user feedback

### Setup

1. **Install Python dependencies:**

```bash
cd examples/python
pip install -r requirements.txt
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

Run the agent:

```bash
cd examples/python
python agent.py
```

### Example Commands

Once the agent is running, you can say things like:

- "Upload all invoices from /Users/daniel.stancl/projects/rossum-mcp/examples/data folder to Rossum to the queue <queue_id>."

### How it Works

1. **MCP Integration**: The agent uses the MCP (Model Context Protocol) client to communicate with your Rossum MCP server
2. **Tool Wrapping**: The Rossum API tools are exposed to the AI agent via smolagents' tool interface
3. **Natural Language**: The agent interprets your commands and calls the appropriate tools
4. **Batch Processing**: The agent can handle multiple files intelligently

### Architecture

```
┌─────────────┐
│   User      │
│  Commands   │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Smolagents     │
│   AI Agent      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  MCP Client     │
│  (stdio)        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Rossum MCP     │
│    Server       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Rossum API     │
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
Ensure the Rossum MCP server is accessible. The agent expects to run it via:
```bash
node ../../index.js
```

### Python package issues
Make sure you have Python 3.8+ and install dependencies:
```bash
pip install -r python/requirements.txt
```
