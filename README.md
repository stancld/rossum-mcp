# Rossum MCP Server & Rossum Agent

<div align="center">

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-mcp/)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![Rossum SDK](https://img.shields.io/badge/Rossum-SDK-orange.svg)](https://github.com/rossumai/rossum-sdk)
[![codecov](https://codecov.io/gh/stancld/rossum-mcp/branch/master/graph/badge.svg)](https://codecov.io/gh/stancld/rossum-mcp)

**AI-powered Rossum orchestration: Document workflows conversationally, debug pipelines automatically, and configure automation through natural language.**

</div>

Conversational AI toolkit for the Rossum intelligent document processing platform. Transforms complex workflow setup, debugging, and configuration into natural language conversations through a Model Context Protocol (MCP) server and specialized AI agent.

## 📦 Repository Structure

This repository contains two standalone Python packages:

- **[rossum-mcp/](rossum-mcp/)** - MCP server for Rossum API integration with AI assistants
- **[rossum-agent/](rossum-agent/)** - Specialized AI agent toolkit with Streamlit UI

Each package can be installed and used independently or together for complete functionality.

## 🚀 Quick Start

### Installation

**Option 1: Install both packages (recommended)**
```bash
pip install -e rossum-mcp -e rossum-agent
```

**Option 2: Install individually**
```bash
# MCP server only
pip install -e rossum-mcp

# Agent toolkit only
pip install -e rossum-agent
```

### Configuration

1. Set up environment variables:
```bash
export ROSSUM_API_TOKEN="your_rossum_api_token"
export ROSSUM_API_BASE_URL="https://your-instance.rossum.app/api/v1"
```

2. Configure MCP server in Claude Desktop (see [rossum-mcp/README.md](rossum-mcp/README.md))

3. Run the Streamlit agent UI:
```bash
streamlit run rossum-agent/rossum_agent/streamlit_app.py
```

## Vision & Roadmap

This project enables three progressive levels of AI-powered Rossum orchestration:

1. **📝 Workflow Documentation** *(Current Focus)* - Conversationally document Rossum setups, analyze existing workflows, and generate comprehensive configuration reports through natural language prompts
2. **🔍 Automated Debugging** *(In Progress)* - Automatically diagnose pipeline issues, identify misconfigured hooks, detect schema problems, and suggest fixes through intelligent analysis
3. **🤖 Agentic Configuration** *(Planned)* - Fully autonomous setup and optimization of Rossum workflows - from queue creation to engine training to hook deployment - guided only by high-level business requirements

> [!NOTE]
> This is not an official Rossum project. It is a community-developed integration built on top of the Rossum API.

> [!WARNING]
> This project is in early stage development. Breaking changes to both implementation and agent behavior are expected.

## 📚 Documentation

- **[Full Documentation](https://stancld.github.io/rossum-mcp/)** - Complete guides and API reference
- **[MCP Server README](rossum-mcp/README.md)** - MCP server setup and tools
- **[Agent README](rossum-agent/README.md)** - Agent toolkit and UI usage
- **[Examples](examples/)** - Sample workflows and use cases

## 🛠️ Development

```bash
# Install with all development dependencies
pip install -e rossum-mcp[all] -e rossum-agent[all]

# Run tests
pytest

# Lint and type check
pre-commit run --all-files
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details

## 🤝 Contributing

Contributions welcome! See individual package READMEs for development guidelines.
