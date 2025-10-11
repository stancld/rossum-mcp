MCP to Rossum SDK Mapping
==========================

This page documents how the MCP server tools map to the underlying Rossum SDK
endpoints and methods.

Overview
--------

The Rossum MCP Server acts as a bridge between the Model Context Protocol and the
`Rossum SDK <https://github.com/rossumai/rossum-sdk>`_. Each MCP tool corresponds
to specific Rossum SDK client methods and API endpoints.

Tool-to-SDK Mapping
--------------------

upload_document
^^^^^^^^^^^^^^^

**MCP Tool:**
  ``upload_document(file_path: str, queue_id: int)``

**Rossum SDK Method:**
  ``SyncRossumAPIClient.upload_document(queue_id, files)``

**API Endpoint:**
  ``POST /v1/queues/{queue_id}/upload``

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  The tool wraps the SDK's upload_document method in an async executor to maintain
  compatibility with MCP's async interface. See ``rossum_mcp.server:45-67``

get_annotation
^^^^^^^^^^^^^^

**MCP Tool:**
  ``get_annotation(annotation_id: int, sideloads: Sequence[str])``

**Rossum SDK Method:**
  ``SyncRossumAPIClient.retrieve_annotation(annotation_id, sideloads)``

**API Endpoint:**
  ``GET /v1/annotations/{annotation_id}``

**Query Parameters:**
  - ``sideload``: Content and related objects (e.g., ``['content']``)

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  See ``rossum_mcp.server:69-98``

list_annotations
^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``list_annotations(queue_id: int, status: str)``

**Rossum SDK Method:**
  ``SyncRossumAPIClient.list_annotations(**params)``

**API Endpoint:**
  ``GET /v1/annotations``

**Query Parameters:**
  - ``queue``: Queue ID filter
  - ``status``: Status filter (comma-separated)
  - ``page_size``: Results per page (default: 100)

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  See ``rossum_mcp.server:100-134``

get_queue
^^^^^^^^^

**MCP Tool:**
  ``get_queue(queue_id: int)``

**Rossum SDK Method:**
  ``SyncRossumAPIClient.retrieve_queue(queue_id)``

**API Endpoint:**
  ``GET /v1/queues/{queue_id}``

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  See ``rossum_mcp.server:136-156``

get_schema
^^^^^^^^^^

**MCP Tool:**
  ``get_schema(schema_id: int)``

**Rossum SDK Method:**
  ``SyncRossumAPIClient.retrieve_schema(schema_id)``

**API Endpoint:**
  ``GET /v1/schemas/{schema_id}``

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  See ``rossum_mcp.server:158-174``

get_queue_schema
^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``get_queue_schema(queue_id: int)``

**Rossum SDK Methods:**
  Combines two SDK calls:

  1. ``SyncRossumAPIClient.retrieve_queue(queue_id)``
  2. ``SyncRossumAPIClient.retrieve_schema(schema_id)``

**API Endpoints:**
  1. ``GET /v1/queues/{queue_id}``
  2. ``GET /v1/schemas/{schema_id}``

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  This is a convenience method that retrieves both queue and schema information
  in a single MCP tool call. See ``rossum_mcp.server:176-205``

Async Wrapper Pattern
----------------------

Since the Rossum SDK uses synchronous HTTP clients (``SyncRossumAPIClient``), but
MCP requires async handlers, the server uses a consistent pattern:

.. code-block:: python

   async def tool_method(self, ...):
       loop = asyncio.get_event_loop()
       with concurrent.futures.ThreadPoolExecutor() as pool:
           return await loop.run_in_executor(
               pool, self._tool_method_sync, ...
           )

This ensures the synchronous SDK calls don't block the async MCP event loop.

Rossum API Resources
---------------------

* **Rossum API Documentation**: https://elis.rossum.ai/api/docs/
* **Rossum SDK Repository**: https://github.com/rossumai/rossum-sdk
* **Rossum SDK Python Package**: Available via git installation

Authentication
--------------

The server uses token-based authentication configured via environment variables:

* ``ROSSUM_API_TOKEN``: Your Rossum API authentication token
* ``ROSSUM_API_BASE_URL``: The Rossum API base URL (e.g., https://api.elis.develop.r8.lol/v1)

The token is passed to the SDK client as:

.. code-block:: python

   from rossum_api import SyncRossumAPIClient
   from rossum_api.dtos import Token

   client = SyncRossumAPIClient(
       base_url=base_url,
       credentials=Token(token=api_token)
   )

Error Handling
--------------

All SDK exceptions are caught and returned as JSON error responses:

.. code-block:: json

   {
     "error": "Error message",
     "traceback": "Full Python traceback..."
   }

This allows MCP clients to handle errors gracefully without losing debugging context.
