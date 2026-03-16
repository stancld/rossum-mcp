MCP to Rossum SDK Mapping
==========================

This page documents how the MCP server tools map to the underlying Rossum SDK
endpoints and methods.

Overview
--------

The Rossum MCP Server acts as a bridge between the Model Context Protocol and the
`Rossum API <https://github.com/rossumai/rossum-api>`_. Each MCP tool corresponds
to specific Rossum SDK client methods and API endpoints.

Tool-to-SDK Mapping
--------------------

upload_document
^^^^^^^^^^^^^^^

**MCP Tool:**
  ``upload_document(file_path: str, queue_id: int)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.upload_document(queue_id, files)``

**API Endpoint:**
  ``POST /v1/queues/{queue_id}/upload``

**SDK Documentation:**
  https://github.com/rossumai/rossum-api

**Implementation:**
  The tool wraps the SDK's upload_document method in an async executor to maintain
  compatibility with MCP's async interface. See ``rossum_mcp.tools.create.annotations``

get_annotation_content
^^^^^^^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``get_annotation_content(annotation_id: int)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.retrieve_annotation(annotation_id, sideloads=("content",))``

**API Endpoint:**
  ``GET /v1/annotations/{annotation_id}?sideload=content``

**Returns:**
  Path to a local JSON file at ``/tmp/rossum_annotation_{id}_content.json``

**SDK Documentation:**
  https://github.com/rossumai/rossum-api

**Implementation:**
  See ``rossum_mcp.tools.annotations``

get
^^^

**MCP Tool:**
  ``get(entity: EntityType, entity_id: int, include_related: bool = False)``

**Supported entities:**
  ``queue``, ``schema``, ``hook``, ``engine``, ``rule``, ``user``, ``workspace``,
  ``email_template``, ``organization_group``, ``organization_limit``, ``annotation``,
  ``relation``, ``document_relation``, ``hook_secrets_keys``

**Returns:**
  ``{"entity": "<type>", "id": <id>, "data": {...}}``

**include_related enrichment:**
  - ``queue`` → adds ``schema_tree``, ``engine``, ``hooks``, ``hooks_count``
  - ``schema`` → adds ``queues``, ``rules``
  - ``hook`` → adds ``queues``, ``events``

**API Endpoints:**
  Varies by entity — ``GET /v1/{entity_plural}/{id}``

**Implementation:**
  See ``rossum_mcp.tools.get`` and ``rossum_mcp.tools.search``

search
^^^^^^

**MCP Tool:**
  ``search(query: SearchQuery)``

**Query object:** discriminated union on ``entity`` field — each entity type exposes only its valid filter params.

**Supported entities and their filters:**

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Entity
     - Available filters
   * - ``queue``
     - ``id``, ``workspace_id``, ``name``, ``use_regex``
   * - ``schema``
     - ``name``, ``queue_id``, ``use_regex``
   * - ``hook``
     - ``queue_id``, ``active``, ``first_n``
   * - ``engine``
     - ``id``, ``engine_type``, ``agenda_id``
   * - ``rule``
     - ``schema_id``, ``organization_id``, ``enabled``
   * - ``user``
     - ``username``, ``email``, ``first_name``, ``last_name``, ``is_active``, ``is_organization_group_admin``
   * - ``workspace``
     - ``organization_id``, ``name``, ``use_regex``
   * - ``email_template``
     - ``queue_id``, ``type``, ``name``, ``first_n``, ``use_regex``
   * - ``organization_group``
     - ``name``, ``use_regex``
   * - ``annotation``
     - ``queue_id`` (required), ``status``, ``ordering``, ``first_n``
   * - ``relation``
     - ``id``, ``type``, ``parent``, ``key``, ``annotation``
   * - ``document_relation``
     - ``id``, ``type``, ``annotation``, ``key``, ``documents``
   * - ``hook_log``
     - ``hook_id``, ``queue_id``, ``annotation_id``, ``email_id``, ``log_level``, ``status``, ``status_code``, ``request_id``, ``timestamp_before/after``, ``start/end_before/after``, ``search``, ``page_size``
   * - ``hook_template``
     - *(no filters)*
   * - ``user_role``
     - *(no filters)*
   * - ``queue_template_name``
     - *(no filters)*

**Returns:**
  ``list`` of entity objects

**API Endpoints:**
  Varies by entity — ``GET /v1/{entity_plural}``

**Implementation:**
  See ``rossum_mcp.tools.get`` and ``rossum_mcp.tools.search``

create_queue_from_template
^^^^^^^^^^^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``create_queue_from_template(name: str, template_name: str, workspace_id: int,
  include_documents: bool, engine_id: int | None)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient._http_client.request_json("POST", "queues/from_template", ...)``

**API Endpoint:**
  ``POST /v1/queues/from_template``

**Request Body:**
  JSON object with queue name, template_name, workspace URL, include_documents flag,
  and optional engine URL.

**SDK Documentation:**
  https://rossum.app/api/docs/#tag/Queue/operation/queues_from_template

**Implementation:**
  Creates a queue from predefined templates. Preferred method for new customer setup.
  Templates include pre-configured schema and AI engine for specific document types
  (EU/US/UK/CZ/CN invoices, purchase orders, credit notes, etc.).

update_queue
^^^^^^^^^^^^

**MCP Tool:**
  ``update_queue(queue_id: int, queue_data: dict)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.internal_client.update(Resource.Queue, queue_id, queue_data)``

**API Endpoint:**
  ``PATCH /v1/queues/{queue_id}``

**Request Body:**
  Partial JSON object with only the fields to update (e.g., automation_enabled,
  automation_level, default_score_threshold).

**SDK Documentation:**
  https://github.com/rossumai/rossum-api

**Implementation:**
  Updates specific queue fields using PATCH semantics. Commonly used to configure
  automation thresholds and settings. See ``rossum_mcp.tools.update.queues``

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
  https://github.com/rossumai/rossum-api

**Implementation:**
  Updates engine configuration using PATCH semantics. Commonly used to manage
  training queues and learning settings. See ``rossum_mcp.tools.update.engines``

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

create_hook
^^^^^^^^^^^

**MCP Tool:**
  ``create_hook(name: str, type: HookType, queues: list[str] | None,
  events: list[HookEventAndAction] | None, config: dict | None, settings: dict | None,
  secrets: dict[str, str] | None, token_owner: str | None,
  run_after: list[str] | None, sideload: list[HookSideload] | None)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.create_new_hook(hook_data: dict)``

**API Endpoint:**
  ``POST /v1/hooks``

**Request Body:**
  JSON object with hook configuration including name, type, optional
  queue URLs, event triggers, configuration, and settings.

**Implementation:**
  Creates a new webhook or serverless function hook. For function hooks,
  ``config.source`` is auto-renamed to ``config.code``, default runtime is
  ``python3.12``, and ``timeout_s`` is capped at 60.
  See ``rossum_mcp.tools.create.hooks``

**Parameters:**
  - ``name`` (str): Hook name
  - ``type`` (HookType): ``webhook`` or ``function``
  - ``queues`` (list[str], optional): List of queue URLs to attach the hook to
  - ``events`` (list[HookEventAndAction], optional): List of trigger events in ``event.action`` format
  - ``config`` (dict, optional): Hook configuration
  - ``settings`` (dict, optional): Hook settings
  - ``secrets`` (dict[str, str], optional): Secret key-value pairs for the hook
  - ``token_owner`` (str, optional): User URL for token ownership; cannot be an ``organization_group_admin`` user
  - ``run_after`` (list[str], optional): List of hook URLs that must run before this hook
  - ``sideload`` (list[HookSideload], optional): Sideload configuration for the hook

create_rule
^^^^^^^^^^^

**MCP Tool:**
  ``create_rule(name: str, trigger_condition: str, actions: list[dict], enabled: bool = True, schema_id: int | None = None, queue_ids: list[int] | None = None)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.create_new_rule(rule_data)``

**API Endpoint:**
  ``POST /v1/rules``

**Request Body:**
  - ``name``: Rule name
  - ``trigger_condition``: TxScript formula string (e.g., ``"field.amount > 10000"``)
  - ``actions``: List of actions with required fields: ``id``, ``type``, ``event``, ``payload``
  - ``enabled``: Whether the rule is active (default: True)
  - ``schema``: Schema URL (optional, at least one of ``schema_id`` or ``queue_ids`` required)
  - ``queues``: List of queue URLs to limit rule to specific queues (optional)

**Action types:** ``show_message``, ``add_automation_blocker``, ``add_validation_source``, ``change_queue``, ``send_email``, ``hide_field``, ``show_field``, ``show_hide_field``, ``change_status``, ``add_label``, ``remove_label``, ``custom``

**Event:** ``validation``

**Implementation:**
  Creates a new business rule. Rules automate field operations based on trigger conditions.
  Actions define what happens when conditions are met (e.g., set field value, show message).
  At least one of ``schema_id`` or ``queue_ids`` must be provided to scope the rule.

**Common Use Cases:**

  .. code-block:: python

     # Create a validation rule
     rule = await server.create_rule(
         name="High Value Alert",
         trigger_condition="field.amount > 10000",
         actions=[{"id": "alert1", "type": "show_message", "event": "validation", "payload": {"type": "error", "content": "High value invoice", "schema_id": "amount"}}],
         schema_id=12345
     )

patch_rule
^^^^^^^^^^

**MCP Tool:**
  ``patch_rule(rule_id: int, name: str | None, trigger_condition: str | None, actions: list[dict] | None, enabled: bool | None, queue_ids: list[int] | None = None)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.update_part_rule(rule_id, rule_data)``

**API Endpoint:**
  ``PATCH /v1/rules/{id}``

**Request Body:**
  - ``name``: Rule name (optional)
  - ``trigger_condition``: TxScript formula string (optional)
  - ``actions``: List of actions (optional)
  - ``enabled``: Whether the rule is active (optional)
  - ``queues``: List of queue URLs (optional, empty list removes all queue associations)

**Implementation:**
  Partial update (PATCH) of a business rule. Only provided fields are updated.

**Common Use Cases:**

  .. code-block:: python

     # Disable a rule
     rule = await server.patch_rule(rule_id=67890, enabled=False)

     # Update only the trigger condition
     rule = await server.patch_rule(
         rule_id=67890,
         trigger_condition="field.amount > 20000"
     )

update_hook
^^^^^^^^^^^

**MCP Tool:**
  ``update_hook(hook_id: int, name: str | None, queues: list[str] | None,
  events: list[HookEventAndAction] | None, config: dict | None, settings: dict | None,
  active: bool | None, secrets: dict[str, str] | None, token_owner: str | None,
  run_after: list[str] | None, sideload: list[HookSideload] | None)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.update_part_hook(hook_id, hook_data)``

**API Endpoint:**
  ``PATCH /v1/hooks/{hook_id}``

**Request Body:**
  Partial JSON object with only the fields to update.

**Implementation:**
  Updates an existing hook's properties. Only provided fields are updated; others remain
  unchanged. See ``rossum_mcp.tools.update.hooks``

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
  https://github.com/rossumai/rossum-api

**Implementation:**
  Creates a hook from a Rossum Store template. If the template has ``use_token_owner=True``,
  a valid token_owner user URL must be provided. Organization group admin users cannot be
  used as token owners.

test_hook
^^^^^^^^^

**MCP Tool:**
  ``test_hook(hook_id: int, event: HookEvent, action: HookAction, annotation: str | None, status: str | None, previous_status: str | None, config: dict | None)``

**API Endpoint:**
  ``POST /v1/hooks/{hook_id}/test``

**Request Body:**
  JSON object with ``event``, ``action``, optional ``annotation`` URL, optional ``status``/``previous_status``,
  and optional ``config`` override.

**Implementation:**
  Tests a hook by generating a payload from the given event/action parameters and sending it directly.
  Returns hook response and logs.

patch_schema
^^^^^^^^^^^^

**MCP Tool:**
  ``patch_schema(schema_id: int, operation: str, node_id: str, node_data: dict | None, parent_id: str | None, position: int | None)``

**API Endpoint:**
  ``PATCH /v1/schemas/{schema_id}``

**Request Body:**
  JSON object with modified schema content array.

**SDK Documentation:**
  https://github.com/rossumai/rossum-api

**Implementation:**
  Patches a schema by adding, updating, or removing individual nodes without replacing the
  entire content. Operations: "add" (requires parent_id, node_data), "update" (requires node_data),
  "remove" (only node_id needed).

get_schema_tree_structure
^^^^^^^^^^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``get_schema_tree_structure(schema_id: int | None, queue_id: int | None)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.retrieve_schema(schema_id)``

**API Endpoint:**
  ``GET /v1/schemas/{schema_id}``

**SDK Documentation:**
  https://github.com/rossumai/rossum-api

**Implementation:**
  Returns a lightweight tree structure of the schema with only ids, labels, categories, and types.
  Accepts either ``schema_id`` or ``queue_id`` (resolves to schema automatically). Exactly one
  parameter must be provided.

prune_schema_fields
^^^^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``prune_schema_fields(schema_id: int, fields_to_keep: list[str])``

**API Endpoint:**
  ``PUT /v1/schemas/{schema_id}``

**SDK Documentation:**
  https://github.com/rossumai/rossum-api

**Implementation:**
  Removes multiple fields from a schema at once, keeping only specified fields and their
  ancestor sections/multivalues. Efficient for pruning unwanted fields during setup.

list_tool_categories
^^^^^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``list_tool_categories()``

**API Endpoint:**
  N/A (returns data from local catalog)

**Implementation:**
  Returns all available tool categories with their metadata. The catalog is defined
  in ``rossum_mcp.tools.catalog`` and includes category names, descriptions, tool
  lists, and keywords for automatic pre-loading based on user request text.
  See ``rossum_mcp.tools.discovery:18-36``

**Returns:**
  List of category objects with structure:

  - ``name``: Category identifier (e.g., "queues", "schemas")
  - ``description``: Human-readable category description
  - ``tool_count``: Number of tools in the category
  - ``tools``: List of tool metadata (name, description)
  - ``keywords``: Keywords for automatic category matching

**Available Categories:**

.. list-table::
   :header-rows: 1
   :widths: 20 50 30

   * - Category
     - Description
     - Keywords
   * - ``read``
     - Unified read layer: get one entity by ID or search/list with typed filters
     - get, search, list, read, retrieve, find, lookup
   * - ``annotations``
     - Document processing: upload, retrieve, update, confirm
     - annotation, document, upload, extract, confirm, review
   * - ``queues``
     - Queue management: create, configure, list
     - queue, inbox, connector
   * - ``schemas``
     - Schema management: define, modify field structures
     - schema, field, datapoint, section, multivalue, tuple
   * - ``engines``
     - AI engine management: extraction/splitting engines
     - engine, ai, extractor, splitter, training
   * - ``hooks``
     - Extensions/webhooks: automation hooks
     - hook, extension, webhook, automation, function, serverless
   * - ``email_templates``
     - Email templates: automated email responses
     - email, notification, rejection
   * - ``rules``
     - Validation rules: schema validation
     - rule, validation, constraint
   * - ``users``
     - User management: create and update users
     - user, role, permission, token_owner
   * - ``workspaces``
     - Workspace management: organize queues
     - workspace, organization
**Example:**

.. code-block:: python

   # Get all available categories
   categories = await server.list_tool_categories()

   # Find categories matching a keyword
   for cat in categories:
       if "schema" in cat["keywords"]:
           print(f"{cat['name']}: {cat['tool_count']} tools")

copy_annotations
^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``copy_annotations(annotation_ids: Sequence[int], target_queue_id: int, target_status: str | None = None, reimport: bool = False)``

**API Endpoint:**
  ``POST /v1/annotations/{annotation_id}/copy`` (called per annotation)

**Implementation:**
  Iterates over ``annotation_ids``, calling the copy endpoint for each. Collects
  results and errors separately for graceful partial failure handling. Uses
  ``_http_client.request_json`` directly since the SDK has no copy method.

start_annotation
^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``start_annotation(annotation_id: int)``

**Description:**
  Set annotation status to 'reviewing' (from 'to_review').

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.start_annotation(annotation_id)``

**API Endpoint:**
  ``POST /v1/annotations/{annotation_id}/start``

**Returns:**

.. code-block:: json

   {"annotation_id": 12345, "message": "Annotation 12345 started successfully. Status changed to 'reviewing'."}

**Implementation:**
  See ``rossum_mcp.tools.update.annotations``

bulk_update_annotation_fields
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``bulk_update_annotation_fields(annotation_id: int, operations: list[dict])``

**Description:**
  Bulk update extracted fields. Requires annotation in 'reviewing' status.
  Use datapoint IDs from content, not schema_id.

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.bulk_update_annotation_data(annotation_id, operations)``

**API Endpoint:**
  ``POST /v1/annotations/{annotation_id}/content/operations``

**Parameters:**

- ``annotation_id`` (int): Annotation to update
- ``operations`` (list[dict]): List of update operations, each containing datapoint ID and new value

**Returns:**

.. code-block:: json

   {"annotation_id": 12345, "operations_count": 3, "message": "Annotation 12345 updated with 3 operations successfully."}

**Implementation:**
  See ``rossum_mcp.tools.update.annotations``

confirm_annotation
^^^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``confirm_annotation(annotation_id: int)``

**Description:**
  Set annotation status to 'confirmed' (typically after field updates).

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.confirm_annotation(annotation_id)``

**API Endpoint:**
  ``POST /v1/annotations/{annotation_id}/confirm``

**Returns:**

.. code-block:: json

   {"annotation_id": 12345, "message": "Annotation 12345 confirmed successfully. Status changed to 'confirmed'."}

**Implementation:**
  See ``rossum_mcp.tools.update.annotations``

create_engine
^^^^^^^^^^^^^

**MCP Tool:**
  ``create_engine(name: str, organization_id: int, engine_type: EngineType)``

**Description:**
  Create an engine; create matching engine fields for the target schema immediately after.

**Rossum SDK Method:**
  ``AsyncRossumAPIClient._http_client.create(Resource.Engine, engine_data)``

**API Endpoint:**
  ``POST /v1/engines``

**Parameters:**

- ``name`` (str): Engine name
- ``organization_id`` (int): Organization to create the engine in
- ``engine_type`` (Literal["extractor", "splitter"]): Type of engine

**Returns:**
  ``Engine`` object

**Implementation:**
  See ``rossum_mcp.tools.create.engines``

create_engine_field
^^^^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``create_engine_field(engine_id: int, name: str, label: str, field_type: EngineFieldType, schema_ids: list[int], tabular: bool = False, multiline: bool = False, subtype: str | None = None, pre_trained_field_id: str | None = None)``

**Description:**
  Create an engine field corresponding to a schema field (used during engine+schema setup).

**Rossum SDK Method:**
  ``AsyncRossumAPIClient._http_client.create(Resource.EngineField, engine_field_data)``

**API Endpoint:**
  ``POST /v1/engine_fields``

**Parameters:**

- ``engine_id`` (int): Engine to add the field to
- ``name`` (str): Field name (should match schema field id)
- ``label`` (str): Human-readable label
- ``field_type`` (Literal["string", "number", "date", "enum"]): Data type
- ``schema_ids`` (list[int]): Schemas this field is linked to (at least one required)
- ``tabular`` (bool): Whether the field is inside a table (default: False)
- ``multiline`` (bool): Whether the field spans multiple lines (default: False)
- ``subtype`` (str, optional): Field subtype
- ``pre_trained_field_id`` (str, optional): Pre-trained field identifier for transfer learning

**Returns:**
  ``EngineField`` object

**Implementation:**
  See ``rossum_mcp.tools.create.engines``

get_engine_fields
^^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``get_engine_fields(engine_id: int | None = None)``

**Description:**
  Retrieve engine fields for a specific engine or all engine fields.

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.retrieve_engine_fields(engine_id=engine_id)``

**API Endpoint:**
  ``GET /v1/engine_fields?engine={engine_id}``

**Parameters:**

- ``engine_id`` (int, optional): Filter by engine ID. If not provided, returns all engine fields.

**Returns:**
  ``list[EngineField]``

**Implementation:**
  See ``rossum_mcp.tools.get.engines``

create_user
^^^^^^^^^^^

**MCP Tool:**
  ``create_user(username: str, email: str, queues: list[str] | None = None, groups: list[str] | None = None, first_name: str | None = None, last_name: str | None = None, is_active: bool = True, metadata: dict | None = None, oidc_id: str | None = None, auth_type: str = "password")``

**Description:**
  Create a user (requires username + email). Use list_user_roles for role/group URLs;
  queue/group fields take full API URLs.

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.create_new_user(user_data)``

**API Endpoint:**
  ``POST /v1/users``

**Parameters:**

- ``username`` (str): Username (typically email)
- ``email`` (str): User email
- ``queues`` (list[str], optional): Queue URLs to grant access to
- ``groups`` (list[str], optional): Role/group URLs (use ``search(entity='user_role')`` to find)
- ``first_name`` (str, optional): First name
- ``last_name`` (str, optional): Last name
- ``is_active`` (bool): Whether user is active (default: True)
- ``metadata`` (dict, optional): Custom metadata
- ``oidc_id`` (str, optional): OIDC identifier for SSO
- ``auth_type`` (str): Authentication type (default: "password")

**Returns:**
  ``User`` object

**Implementation:**
  See ``rossum_mcp.tools.create.users``

update_user
^^^^^^^^^^^

**MCP Tool:**
  ``update_user(user_id: int, username: str | None = None, email: str | None = None, first_name: str | None = None, last_name: str | None = None, queues: list[str] | None = None, groups: list[str] | None = None, is_active: bool | None = None, metadata: dict | None = None, oidc_id: str | None = None, auth_type: str | None = None, ui_settings: dict | None = None)``

**Description:**
  Patch a user; only provided fields change. Use list_user_roles for role/group URLs.

**Rossum SDK Method:**
  ``AsyncRossumAPIClient._http_client.update(Resource.User, user_id, patch_data)``

**API Endpoint:**
  ``PATCH /v1/users/{user_id}``

**Parameters:**

- ``user_id`` (int): User to update
- ``username`` (str, optional): New username
- ``email`` (str, optional): New email
- ``first_name`` (str, optional): First name
- ``last_name`` (str, optional): Last name
- ``queues`` (list[str], optional): Queue URLs
- ``groups`` (list[str], optional): Role/group URLs
- ``is_active`` (bool, optional): Active status
- ``metadata`` (dict, optional): Custom metadata
- ``oidc_id`` (str, optional): OIDC identifier
- ``auth_type`` (str, optional): Authentication type
- ``ui_settings`` (dict, optional): UI preferences

**Returns:**
  ``User`` object

**Implementation:**
  See ``rossum_mcp.tools.update.users``

create_workspace
^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``create_workspace(name: str, organization_id: int, metadata: dict | None = None)``

**Description:**
  Create a new workspace.

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.create_new_workspace(workspace_data)``

**API Endpoint:**
  ``POST /v1/workspaces``

**Parameters:**

- ``name`` (str): Workspace name
- ``organization_id`` (int): Organization to create workspace in
- ``metadata`` (dict, optional): Custom metadata

**Returns:**
  ``Workspace`` object

**Implementation:**
  See ``rossum_mcp.tools.create.workspaces``

create_email_template
^^^^^^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``create_email_template(name: str, queue: int, subject: str, message: str, type: EmailTemplateType = "custom", automate: bool = False, to: list[EmailRecipient] | None = None, cc: list[EmailRecipient] | None = None, bcc: list[EmailRecipient] | None = None, triggers: list[str] | None = None)``

**Description:**
  Create an email template; set automate=true for automatic sending.
  to/cc/bcc are recipient objects ``{type: annotator|constant|datapoint, value: ...}``.

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.create_new_email_template(template_data)``

**API Endpoint:**
  ``POST /v1/email_templates``

**Parameters:**

- ``name`` (str): Template name
- ``queue`` (int): Queue ID to attach the template to
- ``subject`` (str): Email subject line
- ``message`` (str): Email body (supports HTML)
- ``type`` (Literal["rejection", "rejection_default", "email_with_no_processable_attachments", "custom"]): Template type (default: "custom")
- ``automate`` (bool): Send automatically when triggered (default: False)
- ``to`` (list[EmailRecipient], optional): To recipients
- ``cc`` (list[EmailRecipient], optional): CC recipients
- ``bcc`` (list[EmailRecipient], optional): BCC recipients
- ``triggers`` (list[str], optional): Events that trigger the email

**Returns:**
  ``EmailTemplate`` object

**Implementation:**
  See ``rossum_mcp.tools.create.email_templates``

Delete Layer
------------

The unified ``delete`` tool replaces all individual ``delete_X`` tools. It routes
to the appropriate SDK method based on the ``entity`` parameter, using the
``delete_resource`` helper from ``rossum_mcp.tools.base`` for consistent
read-only mode checks and response formatting.

delete
^^^^^^

**MCP Tool:**
  ``delete(entity: str, entity_id: int)``

**Supported entities and SDK methods:**

.. list-table::
   :header-rows: 1

   * - Entity
     - SDK Method
     - API Endpoint
     - Notes
   * - ``queue``
     - ``AsyncRossumAPIClient.delete_queue(id)``
     - ``DELETE /v1/queues/{id}``
     - Schedules deletion after 24h; cascades to annotations/documents
   * - ``schema``
     - ``AsyncRossumAPIClient.delete_schema(id)``
     - ``DELETE /v1/schemas/{id}``
     - Fails with 409 if linked to any queue/annotation
   * - ``hook``
     - ``AsyncRossumAPIClient.delete_hook(id)``
     - ``DELETE /v1/hooks/{id}``
     -
   * - ``rule``
     - ``AsyncRossumAPIClient.delete_rule(id)``
     - ``DELETE /v1/rules/{id}``
     -
   * - ``workspace``
     - ``AsyncRossumAPIClient.delete_workspace(id)``
     - ``DELETE /v1/workspaces/{id}``
     - Fails if workspace contains queues
   * - ``annotation``
     - ``AsyncRossumAPIClient.delete_annotation(id)``
     - ``DELETE /v1/annotations/{id}``
     - Soft delete — moves to 'deleted' status

**Implementation:**
  Defined in ``rossum_mcp/tools/delete/handler.py``. A registry maps entity
  names to SDK delete methods.

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

   from rossum_api import AsyncRossumAPIClient
   from rossum_api.dtos import Token

   client = AsyncRossumAPIClient(
       base_url=base_url,
       credentials=Token(token=api_token)
   )

Mode Control Tools
^^^^^^^^^^^^^^^^^^

get_mcp_mode
""""""""""""

Returns the current MCP operation mode.

**Parameters:** None

**Returns:**

.. code-block:: json

   {"mode": "read-only"}

Error Handling
--------------

All SDK exceptions are caught and returned as JSON error responses:

.. code-block:: json

   {
     "error": "Error message",
     "traceback": "Full Python traceback..."
   }

This allows MCP clients to handle errors gracefully without losing debugging context.
