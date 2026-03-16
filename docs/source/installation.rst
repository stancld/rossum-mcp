Installation
============

Prerequisites
-------------

* Python 3.12+
* Rossum account with API credentials
* A Rossum queue ID

This repository contains five packages:

* **rossum_mcp**: MCP server for Rossum API interactions
* **rossum_agent**: AI agent with data manipulation and visualization tools
* **rossum_agent_client**: Typed Python client for the Rossum Agent API
* **rossum-agent-client-ts**: Typed TypeScript client for the Rossum Agent API
* **rossum_deploy**: Lightweight deployment tool (alternative to `deployment-manager <https://github.com/rossumai/deployment-manager>`_)

Installation Methods
--------------------

Installing MCP Server Only
^^^^^^^^^^^^^^^^^^^^^^^^^^^

To install only the MCP server:

.. code-block:: bash

   git clone https://github.com/stancld/rossum-agents.git
   cd rossum-mcp/rossum_mcp
   uv sync

With extras:

.. code-block:: bash

   uv sync --extra all  # Install all extras (docs, tests)
   uv sync --extra docs  # Install documentation dependencies
   uv sync --extra tests  # Install testing dependencies

Installing Agent Only
^^^^^^^^^^^^^^^^^^^^^

To install only the agent package:

.. code-block:: bash

   git clone https://github.com/stancld/rossum-agents.git
   cd rossum-mcp/rossum_agent
   uv sync

With extras:

.. code-block:: bash

   uv sync --extra all  # Install all extras (api, docs, tests)
   uv sync --extra tests  # Install testing dependencies

Installing Agent Client Only
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To install only the agent client package:

.. code-block:: bash

   git clone https://github.com/stancld/rossum-agents.git
   cd rossum-mcp/rossum-agent-client
   uv sync

With extras:

.. code-block:: bash

   uv sync --extra tests  # Install testing dependencies

Installing TypeScript Agent Client
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To install the TypeScript client:

.. code-block:: bash

   git clone https://github.com/stancld/rossum-agents.git
   cd rossum-agents/rossum-agent-client-ts
   npm install

To regenerate types from the OpenAPI spec:

.. code-block:: bash

   npm run generate

Installing Deploy Package Only
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To install only the deployment package:

.. code-block:: bash

   git clone https://github.com/stancld/rossum-agents.git
   cd rossum-mcp/rossum-deploy
   uv sync

With extras:

.. code-block:: bash

   uv sync --extra tests  # Install testing dependencies

Installing All Packages (Workspace)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For development work with all packages:

.. code-block:: bash

   git clone https://github.com/stancld/rossum-agents.git
   cd rossum-mcp
   uv sync --extra all --no-install-project

This installs all packages together with all dependencies.

From GitHub (Direct)
^^^^^^^^^^^^^^^^^^^^

Install directly from GitHub:

.. code-block:: bash

   # MCP server only
   uv pip install "git+https://github.com/stancld/rossum-agents.git#subdirectory=rossum_mcp"

   # Agent only
   uv pip install "git+https://github.com/stancld/rossum-agents.git#subdirectory=rossum_agent"

   # Agent client only
   uv pip install "git+https://github.com/stancld/rossum-agents.git#subdirectory=rossum-agent-client"

   # Deploy only
   uv pip install "git+https://github.com/stancld/rossum-agents.git#subdirectory=rossum-deploy"

   # All packages (workspace)
   uv pip install "git+https://github.com/stancld/rossum-agents.git"

Environment Variables
---------------------

Set up the required environment variables:

.. code-block:: bash

   export ROSSUM_API_TOKEN="your-api-token"
   export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
   export ROSSUM_MCP_MODE="read-write"  # Optional: "read-only" or "read-write" (default)

Configuration Options
^^^^^^^^^^^^^^^^^^^^^

* **ROSSUM_API_TOKEN** (required): Your Rossum API authentication token
* **ROSSUM_API_BASE_URL** (required): Base URL for the Rossum API
* **ROSSUM_MCP_MODE** (optional): Controls which tools are available

  * ``read-write`` (default): All tools available (GET, LIST, CREATE, UPDATE operations)
  * ``read-only``: Only read operations available (GET and LIST operations only)

Replace the base URL with your organization's Rossum instance URL if different.

Read-Only vs Read-Write Mode
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When ``ROSSUM_MCP_MODE`` is set to ``read-only``, only read-tagged tools are available:

* ``get`` - Retrieve any entity by ID
* ``search`` - Search/list entities with filters
* ``get_annotation_content`` - Fetch annotation extracted content
* ``get_schema_tree_structure`` - Get lightweight schema tree view
* ``get_engine_fields`` - Retrieve engine fields
* ``list_tool_categories`` / ``load_tool`` - Tool discovery and loading

All CREATE, UPDATE, and UPLOAD operations are disabled in read-only mode for security purposes.

Runtime Mode Switching
^^^^^^^^^^^^^^^^^^^^^^

Use ``get_mcp_mode`` to check the current operation mode:

.. code-block:: text

   User: What mode are we in?
   Assistant: [calls get_mcp_mode] → "read-only"

To change the mode, restart the server with a different ``ROSSUM_MCP_MODE`` environment variable.
