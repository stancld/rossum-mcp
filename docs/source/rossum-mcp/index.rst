Rossum MCP Server
==================

MCP server exposing 30+ typed tools for Rossum document processing. Built with `FastMCP <https://github.com/jlowin/fastmcp>`_ and the official `rossum-api <https://github.com/rossumai/rossum-api>`_ SDK.

Quick Start
-----------

.. tab-set::

   .. tab-item:: uvx (recommended)

      .. code-block:: bash

         uvx rossum-mcp

   .. tab-item:: pip

      .. code-block:: bash

         pip install rossum-mcp
         rossum-mcp

   .. tab-item:: From source

      .. code-block:: bash

         git clone https://github.com/stancld/rossum-agents.git
         cd rossum-agents/rossum-mcp
         uv sync

Configure environment variables:

.. code-block:: bash

   export ROSSUM_API_TOKEN="your-token"
   export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"

Verify installation:

.. code-block:: bash

   rossum-mcp  # Server starts on stdio

.. tip::

   For detailed client configuration (Claude Desktop, Cursor, etc.), see :doc:`configuration`.
