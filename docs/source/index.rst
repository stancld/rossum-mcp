Rossum MCP Server Documentation
=================================

.. toctree::
   :maxdepth: 2
   :caption: Getting Started:

   installation
   usage
   workflow

.. toctree::
   :maxdepth: 2
   :caption: Reference:

   api
   mcp_reference

.. toctree::
   :maxdepth: 2
   :caption: Examples:

   examples

Welcome to Rossum MCP Server
-----------------------------

**AI-powered Rossum orchestration: Document workflows conversationally, debug pipelines automatically, and configure automation through natural language.**

A Model Context Protocol (MCP) server and AI agent toolkit for the Rossum intelligent document processing platform. Transforms complex workflow setup, debugging, and configuration into natural language conversations.

Built with Python and the official `rossum-sdk <https://github.com/rossumai/rossum-sdk>`_.

Vision & Roadmap
----------------

This project enables three progressive levels of AI-powered Rossum orchestration:

1. **📝 Workflow Documentation** *(Current Focus)* - Conversationally document Rossum setups, analyze existing workflows, and generate comprehensive configuration reports through natural language prompts
2. **🔍 Automated Debugging** *(In Progress)* - Automatically diagnose pipeline issues, identify misconfigured hooks, detect schema problems, and suggest fixes through intelligent analysis
3. **🤖 Agentic Configuration** *(Planned)* - Fully autonomous setup and optimization of Rossum workflows - from queue creation to engine training to hook deployment - guided only by high-level business requirements

Features
--------

The MCP server provides **32 tools** organized into six categories:

**Document Processing**

* **upload_document** - Upload documents for AI extraction
* **get_annotation** - Retrieve extracted data and status
* **list_annotations** - List all annotations with filtering
* **start_annotation** - Start annotation for field updates
* **bulk_update_annotation_fields** - Update field values with JSON Patch
* **confirm_annotation** - Confirm and finalize annotations

**Queue & Schema Management**

* **get_queue**, **get_schema**, **get_queue_schema** - Retrieve configuration
* **get_queue_engine** - Get engine information
* **create_queue**, **create_schema** - Create new queues and schemas
* **update_queue**, **update_schema** - Configure automation thresholds

**Workspace Management**

* **get_workspace** - Retrieve workspace details by ID
* **list_workspaces** - List all workspaces with optional filtering
* **create_workspace** - Create a new workspace

**Engine Management**

* **list_engines** - List all engines with optional filters
* **create_engine** - Create extraction or splitting engines
* **update_engine** - Configure learning and training queues
* **create_engine_field** - Define engine fields and link to schemas
* **get_engine_fields** - Retrieve engine fields for a specific engine or all fields

**Extensions & Rules**

* **get_hook** - Get hook/extension details
* **list_hooks** - List webhooks and extensions
* **create_hook** - Create webhooks or serverless function hooks
* **get_rule** - Get business rule details
* **list_rules** - List business rules with trigger conditions and actions

**Relations Management**

* **get_relation** - Retrieve relation details by ID
* **list_relations** - List all relations between annotations (edit, attachment, duplicate)
* **get_document_relation** - Retrieve document relation details by ID
* **list_document_relations** - List all document relations (export, einvoice)

**AI Agent Toolkit**

The ``rossum_agent`` package provides additional capabilities:

* File system tools for document management
* Data visualization and plotting tools (bar, line, pie, scatter, heatmap charts)
* Hook analysis tools for understanding workflow dependencies and execution flow
* Integration with AI agent frameworks (smolagents)
* CLI and Streamlit web interfaces
* See the :doc:`examples` section for complete workflows

Quick Start
-----------

**Prerequisites:** Python 3.12+, Rossum account with API credentials

.. code-block:: bash

   git clone https://github.com/stancld/rossum-mcp.git
   cd rossum-mcp

   # Install both packages with all features
   uv sync --extra all --no-install-project

   # Set up environment variables
   export ROSSUM_API_TOKEN="your-api-token"
   export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
   export ROSSUM_MCP_MODE="read-write"  # Optional: "read-only" or "read-write" (default)

Run the MCP server:

.. code-block:: bash

   rossum-mcp

Run the AI agent:

.. code-block:: bash

   # CLI interface
   rossum-agent

   # Streamlit web UI
   streamlit run rossum-agent/rossum_agent/app.py

   # Or run with Docker Compose
   docker-compose up rossum-agent

For detailed installation options, see :doc:`installation`

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
