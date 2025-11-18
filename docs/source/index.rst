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

A Model Context Protocol (MCP) server and AI agent toolkit for intelligent document processing with Rossum.
Upload documents, extract data with AI, and create visualizations - all through simple conversational prompts.

Built with Python and the official `rossum-sdk <https://github.com/rossumai/rossum-sdk>`_.

Features
--------

The MCP server provides **20 tools** organized into four categories:

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

**Engine Management**

* **create_engine** - Create extraction or splitting engines
* **update_engine** - Configure learning and training queues
* **create_engine_field** - Define engine fields and link to schemas

**Extensions & Rules**

* **list_hooks** - List webhooks and extensions
* **create_hook** - Create webhooks or serverless function hooks
* **list_rules** - List business rules with trigger conditions and actions

**AI Agent Toolkit**

The ``rossum_agent`` package provides additional capabilities:

* File system tools for document management
* Data visualization and plotting tools (bar, line, pie, scatter, heatmap charts)
* Integration with AI agent frameworks (smolagents)
* CLI and Streamlit web interfaces
* See the :doc:`examples` section for complete workflows

Quick Start
-----------

**Prerequisites:** Python 3.10+, Rossum account with API credentials

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
   streamlit run rossum_agent/app.py

For detailed installation options, see :doc:`installation`

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
