# Rossum Agent

<div align="center">

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-mcp/)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Smolagents](https://img.shields.io/badge/Smolagents-compatible-green.svg)](https://github.com/huggingface/smolagents)

</div>

AI agent package for Rossum document processing with tools for data manipulation and visualization. Built with [smolagents](https://github.com/huggingface/smolagents) and designed to work seamlessly with the Rossum MCP server.

## Features

### Agent Tools
- **File System Tools**: Read, write, and list files from the filesystem
- **Plotting Tools**: Create interactive charts and visualizations with Plotly
- **Internal Tools**: Sleep, execute code, and manage agent operations
- **Rossum Integration**: Connect to Rossum MCP server for document processing

### Visualization Capabilities
- Interactive bar charts, line charts, scatter plots
- Pie charts and histograms
- Box plots and heatmaps
- Customizable colors, labels, and layouts
- Export to HTML or PNG formats

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
pip install -e .
```

### Install with extras

```bash
pip install -e ".[all]"  # All extras (streamlit, docs, tests)
pip install -e ".[streamlit]"  # Streamlit UI only
pip install -e ".[docs]"  # Documentation only
pip install -e ".[tests]"  # Testing only
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
from smolagents import CodeAgent, LiteLLMModel
from rossum_agent.agent import create_agent

# Create an agent
agent = create_agent(
    model_id="anthropic/claude-3-5-sonnet-20241022",
    additional_tools=[]  # Add any custom tools here
)

# Use the agent
result = agent.run(
    "Create a bar chart showing sales by region: "
    "North: 100, South: 150, East: 120, West: 130"
)
```

## Available Tools

### File System Tools

#### read_file
Read contents of a file from the filesystem.

**Parameters:**
- `file_path` (string): Path to the file to read

#### write_file
Write text or markdown content to a file.

**Parameters:**
- `file_path` (string): Path to the file to write
- `content` (string): Text content to write
- `overwrite` (bool, optional): Whether to overwrite existing file (default: True)

#### list_files
List files in a directory.

**Parameters:**
- `directory_path` (string): Path to the directory
- `pattern` (string, optional): Glob pattern to filter files

#### get_file_info
Get metadata about a file or directory.

**Parameters:**
- `path` (string): Path to the file or directory

### Plotting Tools

#### plot_bar_chart
Create an interactive bar chart.

**Parameters:**
- `data` (dict): Data for plotting (e.g., `{"A": 10, "B": 20}`)
- `title` (string, optional): Chart title
- `x_label` (string, optional): X-axis label
- `y_label` (string, optional): Y-axis label
- `output_path` (string, optional): Path to save the chart

#### plot_line_chart
Create an interactive line chart.

**Parameters:**
- `data` (dict): Data for plotting with x and y values
- Additional styling parameters

#### plot_scatter
Create an interactive scatter plot.

**Parameters:**
- `x_data` (list): X-axis values
- `y_data` (list): Y-axis values
- Additional styling parameters

#### plot_pie_chart
Create an interactive pie chart.

**Parameters:**
- `data` (dict): Data for plotting
- Additional styling parameters

### Internal Tools

#### sleep_tool
Pause execution for a specified duration.

**Parameters:**
- `seconds` (int): Number of seconds to sleep

#### execute_code
Execute Python code safely.

**Parameters:**
- `code` (string): Python code to execute

### Rossum Integration

When configured with the Rossum MCP server, the agent can:
- Upload documents to Rossum
- Monitor processing status
- Retrieve and parse annotation data
- Aggregate and visualize extracted data

See the [main repository](https://github.com/stancld/rossum-mcp) for examples of using the agent with Rossum.

## Real-World Use Case

Imagine you have 30 invoices to process for a board meeting in 10 minutes. With Rossum Agent, you can:

1. Upload all 30 invoices in bulk to Rossum
2. Wait for automatic AI extraction
3. Aggregate data across all documents
4. Generate a presentable visualization

All with a simple conversational prompt. See the [main repository](https://github.com/stancld/rossum-mcp) for a complete example with a real-world revenue chart.

## Example Commands

Once the agent is running, you can say things like:

- "Create a bar chart showing revenue by product: Product A: 1000, Product B: 1500, Product C: 1200"
- "Read the file at /path/to/data.json and create a line chart from the data"
- "List all CSV files in /path/to/data/ directory"
- "Upload all invoices from /path/to/invoices to Rossum queue 12345" (requires Rossum MCP server)

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
│ (Smolagents)    │
├─────────────────┤
│ • File Tools    │
│ • Plot Tools    │
│ • Internal Tools│
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

- [Smolagents Documentation](https://github.com/huggingface/smolagents)
- [Rossum API Documentation](https://elis.rossum.ai/api/docs/)
- [Main Repository](https://github.com/stancld/rossum-mcp)
- [Full Documentation](https://stancld.github.io/rossum-mcp/)
