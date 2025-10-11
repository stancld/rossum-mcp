API Reference
=============

This page provides detailed API documentation for the Rossum MCP Server.

RossumMCPServer
---------------

.. automodule:: rossum_mcp.server
   :members:
   :undoc-members:
   :show-inheritance:

Main Server Class
^^^^^^^^^^^^^^^^^

.. autoclass:: rossum_mcp.server.RossumMCPServer
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Methods
^^^^^^^

Document Upload
"""""""""""""""

.. automethod:: rossum_mcp.server.RossumMCPServer.upload_document
.. automethod:: rossum_mcp.server.RossumMCPServer._upload_document_sync

Annotation Retrieval
""""""""""""""""""""

.. automethod:: rossum_mcp.server.RossumMCPServer.get_annotation
.. automethod:: rossum_mcp.server.RossumMCPServer._get_annotation_sync
.. automethod:: rossum_mcp.server.RossumMCPServer.list_annotations
.. automethod:: rossum_mcp.server.RossumMCPServer._list_annotations_sync

Queue and Schema
""""""""""""""""

.. automethod:: rossum_mcp.server.RossumMCPServer.get_queue
.. automethod:: rossum_mcp.server.RossumMCPServer._get_queue_sync
.. automethod:: rossum_mcp.server.RossumMCPServer.get_schema
.. automethod:: rossum_mcp.server.RossumMCPServer._get_schema_sync
.. automethod:: rossum_mcp.server.RossumMCPServer.get_queue_schema
.. automethod:: rossum_mcp.server.RossumMCPServer._get_queue_schema_sync

Server Management
"""""""""""""""""

.. automethod:: rossum_mcp.server.RossumMCPServer.setup_handlers

The ``setup_handlers`` method registers two critical MCP protocol handlers:

1. **list_tools()** - Returns the list of available MCP tools:

   - ``upload_document`` - Upload documents to Rossum queues
   - ``get_annotation`` - Retrieve annotation data by ID
   - ``list_annotations`` - List annotations for a queue with filtering
   - ``get_queue`` - Get queue details including schema_id
   - ``get_schema`` - Get schema details and content
   - ``get_queue_schema`` - Get complete queue schema in one call

2. **call_tool()** - Executes the requested tool with provided arguments

Each tool definition includes:

- Tool name and description
- Input schema (JSON Schema format)
- Required and optional parameters
- Parameter types and descriptions

.. automethod:: rossum_mcp.server.RossumMCPServer.run

Functions
^^^^^^^^^

.. autofunction:: rossum_mcp.server.async_main
.. autofunction:: rossum_mcp.server.main
