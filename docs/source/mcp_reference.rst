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
  in a single MCP tool call. See ``rossum_mcp.server:226-263``

get_queue_engine
^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``get_queue_engine(queue_id: int)``

**Rossum SDK Methods:**
  Combines two SDK calls:

  1. ``SyncRossumAPIClient.retrieve_queue(queue_id)``
  2. ``SyncRossumAPIClient.retrieve_engine(engine_id)`` (if engine URL is a string)

**API Endpoints:**
  1. ``GET /v1/queues/{queue_id}``
  2. ``GET /v1/engines/{engine_id}`` (if needed)

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  This convenience method retrieves both queue and engine information. It handles
  three types of engines: dedicated, generic, and standard. If the engine is
  embedded in the queue response, it deserializes it directly without an additional
  API call. See ``rossum_mcp.server:265-337``

create_queue
^^^^^^^^^^^^

**MCP Tool:**
  ``create_queue(name: str, workspace_id: int, schema_id: int, engine_id: int | None,
  inbox_id: int | None, connector_id: int | None, locale: str, automation_enabled: bool,
  automation_level: str, training_enabled: bool)``

**Rossum SDK Method:**
  ``SyncRossumAPIClient.create_new_queue(queue_data: dict)``

**API Endpoint:**
  ``POST /v1/queues``

**Request Body:**
  JSON object with queue configuration including name, workspace URL, schema URL,
  optional engine URL, inbox URL, connector URL, locale, automation settings, and
  training settings.

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  Creates a new queue with full configuration options. Constructs URLs for workspace,
  schema, and optional resources (engine, inbox, connector) using the base URL.
  See ``rossum_mcp.server:339-442``

update_queue
^^^^^^^^^^^^

**MCP Tool:**
  ``update_queue(queue_id: int, queue_data: dict)``

**Rossum SDK Method:**
  ``SyncRossumAPIClient.internal_client.update(Resource.Queue, queue_id, queue_data)``

**API Endpoint:**
  ``PATCH /v1/queues/{queue_id}``

**Request Body:**
  Partial JSON object with only the fields to update (e.g., automation_enabled,
  automation_level, default_score_threshold).

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  Updates specific queue fields using PATCH semantics. Commonly used to configure
  automation thresholds and settings. See ``rossum_mcp.server:444-486``

update_schema
^^^^^^^^^^^^^

**MCP Tool:**
  ``update_schema(schema_id: int, schema_data: dict)``

**Rossum SDK Method:**
  ``SyncRossumAPIClient.internal_client.update(Resource.Schema, schema_id, schema_data)``

**API Endpoint:**
  ``PATCH /v1/schemas/{schema_id}``

**Request Body:**
  Partial JSON object typically containing the 'content' array with field-level
  configuration including score_threshold properties.

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  Updates schema configuration, typically used to set field-level automation
  thresholds that override the queue's default threshold. See ``rossum_mcp.server:488-526``

update_engine
^^^^^^^^^^^^^

**MCP Tool:**
  ``update_engine(engine_id: int, engine_data: dict)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.internal_client.update(Resource.Engine, engine_id, engine_data)``

**API Endpoint:**
  ``PATCH /v1/engines/{engine_id}``

**Request Body:**
  Partial JSON object with only the fields to update. Supported fields:
  - ``name`` (str): Engine name
  - ``description`` (str): Engine description
  - ``learning_enabled`` (bool): Enable/disable learning
  - ``training_queues`` (list[str]): List of queue URLs for training

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  Updates engine configuration using PATCH semantics. Commonly used to manage
  training queues and learning settings. See ``rossum_mcp.server:450-495``

**Common Use Case:**
  Update training queues to specify which queues an engine should learn from:

  .. code-block:: python

     engine_data = {
         "training_queues": [
             "https://api.elis.rossum.ai/v1/queues/12345",
             "https://api.elis.rossum.ai/v1/queues/67890"
         ]
     }
     result = await server.update_engine(engine_id=36032, engine_data=engine_data)

**Important:** When using the SDK directly with ``request_json``, always use the
``json=`` parameter, not ``data=``. The Rossum API expects JSON-encoded data
(application/json), not form-encoded data (application/x-www-form-urlencoded).

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
* ``ROSSUM_API_BASE_URL``: The Rossum API base URL (e.g., https://api.elis.rossum.ai/v1)

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
