Configuration
=============

Environment Variables
---------------------

.. list-table::
   :header-rows: 1
   :widths: 30 10 60

   * - Variable
     - Required
     - Description
   * - ``ROSSUM_API_TOKEN``
     - Yes
     - Rossum API authentication token
   * - ``ROSSUM_API_BASE_URL``
     - Yes
     - API endpoint, e.g. ``https://api.elis.rossum.ai/v1``
   * - ``ROSSUM_MCP_MODE``
     - No
     - ``read-write`` (default) or ``read-only``
   * - ``ROSSUM_MCP_LOG_LEVEL``
     - No
     - Server log level (default: ``INFO``)
   * - ``ADDITIONAL_ALLOWED_ROSSUM_HOSTS``
     - No
     - Comma-separated regex for extra allowed API hosts

MCP Client Configuration
-------------------------

Claude Desktop
^^^^^^^^^^^^^^

.. code-block:: json

   {
     "mcpServers": {
       "rossum": {
         "command": "uvx",
         "args": ["rossum-mcp"],
         "env": {
           "ROSSUM_API_TOKEN": "your-api-token",
           "ROSSUM_API_BASE_URL": "https://api.elis.rossum.ai/v1",
           "ROSSUM_MCP_MODE": "read-write"
         }
       }
     }
   }

Cursor / VS Code
^^^^^^^^^^^^^^^^^

.. code-block:: json

   {
     "mcpServers": {
       "rossum": {
         "command": "uvx",
         "args": ["rossum-mcp"],
         "env": {
           "ROSSUM_API_TOKEN": "your-api-token",
           "ROSSUM_API_BASE_URL": "https://api.elis.rossum.ai/v1"
         }
       }
     }
   }

Read-Only Mode
--------------

When ``ROSSUM_MCP_MODE=read-only``, only these tools are available:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Tool
     - Purpose
   * - ``get``
     - Retrieve any entity by ID
   * - ``search``
     - Search/list entities with filters
   * - ``get_annotation_content``
     - Fetch annotation extracted content
   * - ``get_schema_tree_structure``
     - Lightweight schema tree view
   * - ``get_engine_fields``
     - Retrieve engine fields
   * - ``list_tool_categories``
     - Tool discovery
   * - ``get_mcp_mode``
     - Check current mode

All create, update, upload, and delete operations are disabled in read-only mode.

To switch modes, restart the server with a different ``ROSSUM_MCP_MODE`` value.
