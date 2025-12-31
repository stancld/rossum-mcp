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

list_hooks
^^^^^^^^^^

**MCP Tool:**
  ``list_hooks(queue_id: int | None, active: bool | None)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.list_hooks(**filters)``

**API Endpoint:**
  ``GET /v1/hooks``

**Query Parameters:**
  - ``queue``: Filter by queue ID
  - ``active``: Filter by active status (true/false)

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  Lists all hooks/extensions (webhooks or serverless functions) configured in
  your organization. Optionally filter by queue ID and/or active status.
  See ``rossum_mcp.server:928-970``

**Common Use Cases:**

  .. code-block:: python

     # List all hooks
     all_hooks = await server.list_hooks()

     # List hooks for a specific queue
     queue_hooks = await server.list_hooks(queue_id=12345)

     # List only active hooks
     active_hooks = await server.list_hooks(active=True)

     # List inactive hooks for a queue
     inactive_queue_hooks = await server.list_hooks(queue_id=12345, active=False)

create_hook
^^^^^^^^^^^

**MCP Tool:**
  ``create_hook(name: str, target: str, queues: list[str] | None,
  events: list[str] | None, config: dict | None, enabled: bool,
  insecure_ssl: bool, secret: str | None, response_event: dict | None)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.create_new_hook(hook_data: dict)``

**API Endpoint:**
  ``POST /v1/hooks``

**Request Body:**
  JSON object with hook configuration including name, target URL, optional
  queue URLs, event triggers, configuration, and security settings.

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  Creates a new webhook or serverless function hook. The hook will trigger on specified
  events and send requests to the target URL. See ``rossum_mcp.server:972-1046``

**Common Use Cases:**

  .. code-block:: python

     # Create a simple webhook for all queues
     basic_hook = await server.create_hook(
         name="Invoice Processing Hook",
         target="https://example.com/webhook"
     )

     # Create a hook for specific queues and events
     advanced_hook = await server.create_hook(
         name="Status Tracker",
         target="https://example.com/status",
         queues=["https://api.elis.rossum.ai/v1/queues/12345"],
         events=["annotation_status", "annotation_content"],
         config={"custom_header": "value"},
         secret="webhook_secret_123"
     )

**Parameters:**
  - ``name`` (str): Hook name for identification
  - ``target`` (str): URL endpoint where webhook requests are sent
  - ``queues`` (list[str], optional): List of queue URLs to attach the hook to.
    If not provided, hook applies to all queues
  - ``events`` (list[str], optional): List of events that trigger the hook:

    * ``annotation_status`` - Annotation status changes
    * ``annotation_content`` - Content modifications
    * ``annotation_export`` - Export operations
    * ``datapoint_value`` - Individual field value changes

  - ``config`` (dict, optional): Additional configuration (e.g., custom headers)
  - ``enabled`` (bool): Whether the hook is active (default: True)
  - ``insecure_ssl`` (bool): Skip SSL verification (default: False)
  - ``secret`` (str, optional): Secret key for securing webhook requests
  - ``response_event`` (dict, optional): Configuration for response event handling

list_rules
^^^^^^^^^^

**MCP Tool:**
  ``list_rules(schema_id: int | None, organization_id: int | None, enabled: bool | None)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.list_rules(**filters)``

**API Endpoint:**
  ``GET /v1/rules``

**Query Parameters:**
  - ``schema``: Filter by schema ID
  - ``organization``: Filter by organization ID
  - ``enabled``: Filter by enabled status (true/false)

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  Lists all business rules configured in your organization. Rules define custom business
  logic with trigger conditions (TxScript formulas) and actions. Optionally filter by
  schema ID, organization ID, and/or enabled status. See ``rossum_mcp.server:974-1030``

**Common Use Cases:**

  .. code-block:: python

     # List all rules
     all_rules = await server.list_rules()

     # List rules for a specific schema
     schema_rules = await server.list_rules(schema_id=12345)

     # List only enabled rules
     enabled_rules = await server.list_rules(enabled=True)

     # List enabled rules for a specific schema
     enabled_schema_rules = await server.list_rules(schema_id=12345, enabled=True)

update_hook
^^^^^^^^^^^

**MCP Tool:**
  ``update_hook(hook_id: int, name: str | None, queues: list[str] | None, events: list[str] | None, config: dict | None, settings: dict | None, active: bool | None)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.update_part_hook(hook_id, hook_data)``

**API Endpoint:**
  ``PATCH /v1/hooks/{hook_id}``

**Request Body:**
  Partial JSON object with only the fields to update.

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  Updates an existing hook's properties. Only provided fields are updated; others remain
  unchanged. Commonly used to modify hook name, attached queues, events, config, or active status.

list_hook_templates
^^^^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``list_hook_templates()``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.request_paginated("hook_templates")``

**API Endpoint:**
  ``GET /v1/hook_templates``

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  Lists all available hook templates from Rossum Store. Hook templates provide pre-built
  extension configurations that can be used to quickly create hooks with standard functionality.

create_hook_from_template
^^^^^^^^^^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``create_hook_from_template(name: str, hook_template_id: int, queues: list[str], events: list[str] | None, token_owner: str | None)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient._http_client.request_json("POST", "hooks/create", json=hook_data)``

**API Endpoint:**
  ``POST /v1/hooks/create``

**Request Body:**
  JSON object with hook name, template URL, queues, optional events, and optional token_owner.

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  Creates a hook from a Rossum Store template. If the template has ``use_token_owner=True``,
  a valid token_owner user URL must be provided. Organization group admin users cannot be
  used as token owners.

patch_schema
^^^^^^^^^^^^

**MCP Tool:**
  ``patch_schema(schema_id: int, operation: str, node_id: str, node_data: dict | None, parent_id: str | None, position: int | None)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.update_schema(schema_id, data)`` (with modified content)

**API Endpoint:**
  ``PATCH /v1/schemas/{schema_id}``

**Request Body:**
  JSON object with modified schema content array.

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  Patches a schema by adding, updating, or removing individual nodes without replacing the
  entire content. Operations: "add" (requires parent_id, node_data), "update" (requires node_data),
  "remove" (only node_id needed).

get_user
^^^^^^^^

**MCP Tool:**
  ``get_user(user_id: int)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.retrieve_user(user_id)``

**API Endpoint:**
  ``GET /v1/users/{user_id}``

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  Retrieves a single user by ID. Use ``list_users`` first to find users by username or email.

list_users
^^^^^^^^^^

**MCP Tool:**
  ``list_users(username: str | None, email: str | None, first_name: str | None, last_name: str | None, is_active: bool | None, is_organization_group_admin: bool | None)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.list_users(**filters)``

**API Endpoint:**
  ``GET /v1/users``

**Query Parameters:**
  - ``username``: Filter by username
  - ``email``: Filter by email
  - ``first_name``: Filter by first name
  - ``last_name``: Filter by last name
  - ``is_active``: Filter by active status

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  Lists users with optional filtering. The ``is_organization_group_admin`` filter is applied
  client-side by checking user groups against organization_group_admin role URLs.

list_user_roles
^^^^^^^^^^^^^^^

**MCP Tool:**
  ``list_user_roles()``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.list_user_roles()``

**API Endpoint:**
  ``GET /v1/groups``

**SDK Documentation:**
  https://github.com/rossumai/rossum-sdk

**Implementation:**
  Lists all user roles (groups of permissions) in the organization.

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
* ``ROSSUM_MCP_MODE``: Controls which tools are available (``read-only`` or ``read-write``, default: ``read-write``)

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
