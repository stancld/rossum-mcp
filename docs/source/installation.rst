Installation
============

Prerequisites
-------------

* Python 3.10 or higher
* Rossum account with API credentials
* A Rossum queue ID

This repository contains three packages:

* **rossum_mcp**: MCP server for Rossum API interactions
* **rossum_agent**: AI agent with data manipulation and visualization tools
* **rossum_deploy**: Lightweight deployment tool (alternative to `deployment-manager <https://github.com/rossumai/deployment-manager>`_)

Installation Methods
--------------------

Installing MCP Server Only
^^^^^^^^^^^^^^^^^^^^^^^^^^^

To install only the MCP server:

.. code-block:: bash

   git clone https://github.com/stancld/rossum-mcp.git
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

   git clone https://github.com/stancld/rossum-mcp.git
   cd rossum-mcp/rossum_agent
   uv sync

With extras:

.. code-block:: bash

   uv sync --extra all  # Install all extras (streamlit, docs, tests)
   uv sync --extra streamlit  # Install Streamlit UI
   uv sync --extra tests  # Install testing dependencies

Installing Deploy Package Only
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To install only the deployment package:

.. code-block:: bash

   git clone https://github.com/stancld/rossum-mcp.git
   cd rossum-mcp/rossum-deploy
   uv sync

With extras:

.. code-block:: bash

   uv sync --extra tests  # Install testing dependencies

Installing All Packages (Workspace)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For development work with all packages:

.. code-block:: bash

   git clone https://github.com/stancld/rossum-mcp.git
   cd rossum-mcp
   uv sync --extra all --no-install-project

This installs all packages together with all dependencies.

From GitHub (Direct)
^^^^^^^^^^^^^^^^^^^^

Install directly from GitHub:

.. code-block:: bash

   # MCP server only
   uv pip install "git+https://github.com/stancld/rossum-mcp.git#subdirectory=rossum_mcp"

   # Agent only
   uv pip install "git+https://github.com/stancld/rossum-mcp.git#subdirectory=rossum_agent"

   # Deploy only
   uv pip install "git+https://github.com/stancld/rossum-mcp.git#subdirectory=rossum-deploy"

   # All packages (workspace)
   uv pip install "git+https://github.com/stancld/rossum-mcp.git"

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

When ``ROSSUM_MCP_MODE`` is set to ``read-only``, only the following tools are available:

* ``get_annotation`` - Retrieve annotation data
* ``list_annotations`` - List annotations for a queue
* ``get_queue`` - Retrieve queue details
* ``get_schema`` - Retrieve schema details
* ``get_queue_schema`` - Retrieve queue schema in one call
* ``get_queue_engine`` - Retrieve engine information
* ``list_hooks`` - List webhooks/extensions

All CREATE, UPDATE, and UPLOAD operations are disabled in read-only mode for security purposes.
