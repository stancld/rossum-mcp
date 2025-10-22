# Rossum Streamlit App

Web interface for the Rossum Document Processing Agent using Streamlit.

## Features

- 🎨 **Interactive Web UI** - Chat-based interface for interacting with the Rossum agent
- 🤖 **LiteLLM Integration** - Connect to any LLM provider supported by LiteLLM
- 📊 **Document Processing** - Upload, process, and analyze documents through Rossum API
- 💡 **Example Prompts** - Quick access to common tasks and workflows
- ⚙️ **Configurable** - Adjust model settings and API endpoints through the UI

## Installation

Install the package with Streamlit support:

```bash
pip install -e .[streamlit]
```

Or install Streamlit separately if you already have rossum-mcp installed:

```bash
pip install streamlit
```

## Environment Setup

Set the required environment variables:

```bash
export ROSSUM_API_TOKEN="your-api-token"
export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
export LLM_API_BASE_URL="http://your-llm-endpoint"
export LLM_MODEL_ID="openai/Qwen/Qwen3-Next-80B-A3B-Instruct-FP8"  # Optional
```

## Usage

Run the Streamlit app from the project root:

```bash
streamlit run examples/python/streamlit_app/app.py
```

The app will open in your default browser at `http://localhost:8501`.

## Features Overview

### Sidebar

- **Environment Status**: Shows if required environment variables are configured
- **Model Settings**: Configure LLM model ID and API endpoint
- **Quick Actions**: Reset conversation and clear chat history
- **Example Prompts**: Pre-configured prompts for common tasks

### Main Interface

- **Chat Interface**: Conversational interface for giving instructions to the agent
- **Message History**: View previous messages and agent responses
- **File Detection**: Automatically detects when agent generates files (HTML, PNG, etc.)

## Example Tasks

### Upload and Process Documents

```
Upload all invoices from /path/to/folder to queue 12345 and wait for processing
```

### Retrieve Schema

```
Get the schema for queue 12345 and show me the field structure
```

### Extract and Aggregate Data

```
Fetch all annotations from queue 12345 in to_review state, extract line items,
and aggregate amounts by description
```

### Generate Visualizations

```
Extract revenue data from queue 12345 and create an interactive bar chart
showing revenue by service category
```

## Architecture

The Streamlit app:

1. **Connects to LiteLLM** - Uses the same LiteLLM configuration as the CLI agent
2. **Reuses Agent Tools** - Leverages all tools from `rossum_agent.py` in the same directory
3. **Session Management** - Maintains conversation history in Streamlit session state
4. **Error Handling** - Provides user-friendly error messages for common issues

## Comparison with CLI Agent

| Feature | CLI (`rossum_agent.py`) | Streamlit (`app.py`) |
|---------|------------------------|----------------------|
| Interface | Command-line | Web browser |
| Interaction | Text input/output | Chat interface |
| History | Terminal scrollback | Persistent in UI |
| Examples | Hardcoded prompts | Interactive buttons |
| Configuration | Environment only | UI + Environment |

## Troubleshooting

### Missing Environment Variables

If you see errors about missing environment variables, ensure all required variables are set:

```bash
export ROSSUM_API_TOKEN="..."
export ROSSUM_API_BASE_URL="..."
export LLM_API_BASE_URL="..."
```

### Agent Initialization Failed

Check that:
1. LLM endpoint is accessible
2. Model ID is correct
3. Required dependencies are installed (`pip install -e .[streamlit]`)

### Import Errors

Ensure you're running from the project root directory:

```bash
cd /path/to/rossum-mcp
streamlit run examples/python/streamlit_app/app.py
```

## Development

To modify the app:

1. Edit `examples/python/streamlit_app/app.py`
2. Streamlit will auto-reload when you save changes
3. Test with various prompts and edge cases

## License

MIT License - see LICENSE file for details
