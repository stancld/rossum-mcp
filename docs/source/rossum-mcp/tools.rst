Tool Reference
==============

30+ tools organized by domain. All tools use Pydantic models and ``StrEnum`` parameters.

Unified Read Layer
------------------

get
^^^

Retrieves one or more entities by ID.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``entity``
     - string, required
     - One of: ``queue``, ``schema``, ``hook``, ``engine``, ``rule``, ``user``, ``workspace``, ``email_template``, ``organization_group``, ``annotation``, ``relation``, ``document_relation``, ``organization_limit``, ``hook_secrets_keys``
   * - ``entity_id``
     - int or list[int], required
     - Single ID or list of IDs for batch retrieval
   * - ``include_related``
     - bool, optional
     - Enrich with related data. ``queue`` adds schema_tree/engine/hooks; ``schema`` adds queues/rules; ``hook`` adds queues/events

**Returns:**

.. code-block:: json

   {"entity": "queue", "id": 12345, "data": {"id": 12345, "name": "Invoices"}}

Batch retrieval returns an array. Failed items are silently skipped.

**Example:**

.. code-block:: python

   get(entity="queue", entity_id=12345, include_related=True)
   get(entity="schema", entity_id=[100, 200, 300])

search
^^^^^^

Lists/searches entities with typed, entity-specific filters.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``query``
     - object, required
     - Discriminated query object with ``entity`` as discriminator. Each entity type exposes only its valid filter fields.
   * - ``first_n``
     - int, optional
     - Limit results across any entity type

**Supported entities and filters:**

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Entity
     - Filters
   * - ``queue``
     - ``workspace_id``, ``name``, ``use_regex``
   * - ``schema``
     - ``name``, ``queue_id``, ``workspace_id``, ``use_regex``
   * - ``hook``
     - ``queue_id``, ``active``, ``workspace_id``
   * - ``engine``
     - ``engine_type`` (``extractor`` | ``splitter``), ``agenda_id``
   * - ``rule``
     - ``queue_id``, ``workspace_id``, ``organization_id``, ``enabled``
   * - ``user``
     - ``username``, ``email``, ``first_name``, ``last_name``, ``is_active``, ``is_organization_group_admin``
   * - ``workspace``
     - ``organization_id``, ``name``, ``use_regex``
   * - ``email_template``
     - ``queue_id``, ``workspace_id``, ``type``, ``name``, ``use_regex``
   * - ``organization_group``
     - ``name``, ``use_regex``
   * - ``annotation``
     - ``queue_id`` (required), ``workspace_id``, ``status``, ``ordering``
   * - ``relation``
     - ``type``, ``parent``, ``key``, ``annotation``
   * - ``document_relation``
     - ``type``, ``annotation``, ``key``, ``documents``
   * - ``hook_log``
     - ``hook_id``, ``queue_id``, ``annotation_id``, ``email_id``, ``log_level``, ``status``, ``status_code``, ``request_id``, ``timestamp_before/after``, ``start_before/after``, ``end_before/after``, ``search``, ``page_size``
   * - ``hook_template``
     - *(no filters)*
   * - ``user_role``
     - *(no filters)*
   * - ``queue_template_name``
     - *(no filters)*

**Example:**

.. code-block:: python

   search(query={"entity": "annotation", "queue_id": 12345, "status": "to_review"}, first_n=10)
   search(query={"entity": "hook", "queue_id": 12345, "active": True})
   search(query={"entity": "hook_template"})

Delete Layer
------------

delete
^^^^^^

Deletes any supported entity by ID.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``entity``
     - string, required
     - One of: ``queue``, ``schema``, ``hook``, ``rule``, ``workspace``, ``annotation``
   * - ``entity_id``
     - int, required
     - ID of the entity to delete

**Entity-specific behavior:**

- **queue** -- Deletion begins after ~24h; cascades to annotations/documents
- **schema** -- Fails with ``409 Conflict`` if linked to any queue/annotation
- **workspace** -- Fails if workspace still contains queues
- **annotation** -- Soft delete (moves to ``deleted`` status)

.. note:: Only available in read-write mode.

Document Processing
-------------------

upload_document
^^^^^^^^^^^^^^^

Uploads a document for AI extraction.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``file_path``
     - string, required
     - Absolute path to the document file
   * - ``queue_id``
     - int, required
     - Queue ID for processing

**Returns:** Task ID and status. Use ``search(query={"entity": "annotation", "queue_id": ...})`` to find the created annotation.

get_annotation_content
^^^^^^^^^^^^^^^^^^^^^^

Fetches annotation extracted content and saves to a local JSON file.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``annotation_id``
     - int, required
     - The annotation ID

**Returns:** ``{"path": "/tmp/rossum_annotation_12345_content.json"}``

start_annotation
^^^^^^^^^^^^^^^^

Sets annotation status to ``reviewing`` (from ``to_review``). Required before updating fields.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``annotation_id``
     - int, required
     - Annotation ID to start

bulk_update_annotation_fields
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Updates field values using JSON Patch operations. Requires annotation in ``reviewing`` status.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``annotation_id``
     - int, required
     - Annotation ID to update
   * - ``operations``
     - list[dict], required
     - JSON Patch operations: ``[{"op": "replace", "id": <datapoint_id>, "value": {"content": {"value": "..."}}}]``

.. important:: Use the numeric datapoint ``id`` from ``annotation.content``, NOT the ``schema_id``.

confirm_annotation
^^^^^^^^^^^^^^^^^^

Confirms an annotation (moves to ``confirmed`` status). Call after field updates.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``annotation_id``
     - int, required
     - Annotation ID to confirm

copy_annotations
^^^^^^^^^^^^^^^^

Copies annotations to another queue. Use ``reimport=True`` to re-extract data in the target queue.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``annotation_ids``
     - list[int], required
     - Annotation IDs to copy
   * - ``target_queue_id``
     - int, required
     - Target queue ID
   * - ``target_status``
     - string, optional
     - Status of copied annotations
   * - ``reimport``
     - bool, optional
     - Re-extract data in target queue (default: false)

Queue Management
----------------

create_queue_from_template
^^^^^^^^^^^^^^^^^^^^^^^^^^

Creates a queue from a predefined regional template. Automatically creates a matching schema and optionally assigns an engine.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``name``
     - string, required
     - Queue name
   * - ``template_name``
     - string, required
     - Template name (use ``search`` with ``entity="queue_template_name"`` to list)
   * - ``workspace_id``
     - int, required
     - Workspace ID
   * - ``include_documents``
     - bool, optional
     - Copy documents from template (default: false)
   * - ``engine_id``
     - int, optional
     - Override engine assignment

**Returns:** Queue object with ``_tracked_resources`` listing created schema and engine.

update_queue
^^^^^^^^^^^^

Updates queue settings including automation thresholds.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``queue_id``
     - int, required
     - Queue ID to update
   * - ``queue_data``
     - dict, required
     - Fields to update: ``name``, ``automation_enabled``, ``automation_level``, ``locale``, ``metadata``, ``settings``, ``engine``, ``dedicated_engine``, ``training_enabled``, ``webhooks``, ``hooks``, ``default_score_threshold``, ``session_timeout``, ``document_lifetime``, ``delete_after``, ``schema``, ``workspace``, ``connector``, ``inbox``

Schema Management
-----------------

patch_schema
^^^^^^^^^^^^

Adds, updates, or removes individual schema nodes without replacing the entire content.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``schema_id``
     - int, required
     - Schema ID to patch
   * - ``operation``
     - string, required
     - ``add``, ``update``, or ``remove``
   * - ``node_id``
     - string, required
     - ID of the node to operate on
   * - ``node_data``
     - dict, optional
     - Data for add/update operations
   * - ``parent_id``
     - string, optional
     - Parent node ID (required for ``add``)
   * - ``position``
     - int, optional
     - Position for ``add`` (appends if omitted)
   * - ``after_field``
     - string, optional
     - Insert after this field ID
   * - ``before_field``
     - string, optional
     - Insert before this field ID

**Example:**

.. code-block:: python

   # Add a field
   patch_schema(schema_id=123, operation="add", node_id="vendor_name",
                parent_id="header_section",
                node_data={"label": "Vendor Name", "type": "string", "category": "datapoint"})

   # Update a field
   patch_schema(schema_id=123, operation="update", node_id="invoice_number",
                node_data={"label": "Invoice #", "score_threshold": 0.9})

   # Remove a field
   patch_schema(schema_id=123, operation="remove", node_id="old_field")

get_schema_tree_structure
^^^^^^^^^^^^^^^^^^^^^^^^^

Gets a lightweight tree view with only IDs, labels, categories, and types.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``schema_id``
     - int, optional
     - Schema ID
   * - ``queue_id``
     - int, optional
     - Queue ID (resolves the queue's schema)

Provide one of ``schema_id`` or ``queue_id``.

prune_schema_fields
^^^^^^^^^^^^^^^^^^^

Removes multiple fields from a schema at once.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``schema_id``
     - int, required
     - Schema ID to prune
   * - ``fields_to_keep``
     - list[str], optional
     - Keep only these leaf field IDs; parent containers preserved automatically
   * - ``fields_to_remove``
     - list[str], optional
     - Remove these leaf field IDs

Provide exactly one of ``fields_to_keep`` or ``fields_to_remove``.

Engine Management
-----------------

create_engine
^^^^^^^^^^^^^

Creates a new extraction or splitting engine.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``name``
     - string, required
     - Engine name
   * - ``organization_id``
     - int, required
     - Organization ID
   * - ``engine_type``
     - string, required
     - ``extractor`` or ``splitter``

update_engine
^^^^^^^^^^^^^

Updates engine settings.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``engine_id``
     - int, required
     - Engine ID
   * - ``engine_data``
     - dict, required
     - Fields to update: ``name``, ``description``, ``learning_enabled``, ``training_queues``

create_engine_field
^^^^^^^^^^^^^^^^^^^

Creates a new engine field and links it to schemas.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``engine_id``
     - int, required
     - Engine ID
   * - ``name``
     - string, required
     - Field name (slug format, max 50 chars)
   * - ``label``
     - string, required
     - Human-readable label (max 100 chars)
   * - ``field_type``
     - string, required
     - ``string``, ``number``, ``date``, or ``enum``
   * - ``schema_ids``
     - list[int], required
     - Schema IDs to link (at least one)
   * - ``tabular``
     - bool, optional
     - Tabular/line item field (default: false)
   * - ``multiline``
     - bool, optional
     - Multiline field (default: false)
   * - ``subtype``
     - string, optional
     - Field subtype
   * - ``pre_trained_field_id``
     - string, optional
     - Pre-trained field ID to link

get_engine_fields
^^^^^^^^^^^^^^^^^

Retrieves engine fields for a specific engine or all fields.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``engine_id``
     - int, optional
     - Engine ID to filter by; omit to retrieve all engine fields

Extensions -- Hooks
-------------------

create_hook
^^^^^^^^^^^

Creates a new webhook or serverless function hook.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``name``
     - string, required
     - Hook name
   * - ``type``
     - string, required
     - ``webhook`` or ``function``
   * - ``queues``
     - list[str], optional
     - Queue URLs to attach to
   * - ``events``
     - list[str], optional
     - Trigger events in ``event.action`` format
   * - ``config``
     - dict, optional
     - Hook configuration. For functions: ``config.source`` auto-renamed to ``config.code``
   * - ``settings``
     - dict, optional
     - Hook settings included in payload
   * - ``secrets``
     - dict[str, str], optional
     - Secret key-value pairs
   * - ``token_owner``
     - string, optional
     - User URL for token ownership
   * - ``run_after``
     - list[str], optional
     - Hook URLs that must run before this hook
   * - ``sideload``
     - list, optional
     - Sideload configuration

**Common events:** ``annotation_content.initialize``, ``annotation_content.confirm``, ``annotation_content.export``, ``annotation_status.changed``

update_hook
^^^^^^^^^^^

Patches an existing hook; only provided fields change.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``hook_id``
     - int, required
     - Hook ID
   * - ``name``
     - string, optional
     - New name
   * - ``queues``
     - list[str], optional
     - New queue URLs
   * - ``events``
     - list[str], optional
     - New trigger events
   * - ``config``
     - dict, optional
     - New configuration
   * - ``settings``
     - dict, optional
     - New settings
   * - ``active``
     - bool, optional
     - Enable/disable
   * - ``secrets``
     - dict[str, str], optional
     - Secret key-value pairs
   * - ``token_owner``
     - string, optional
     - User URL for token ownership

create_hook_from_template
^^^^^^^^^^^^^^^^^^^^^^^^^

Creates a hook from a Rossum Store template. Use ``search(query={"entity": "hook_template"})`` to browse templates.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``name``
     - string, required
     - Hook name
   * - ``hook_template_id``
     - int, required
     - Template ID from ``search``
   * - ``queues``
     - list[str], required
     - Queue URLs to attach to
   * - ``events``
     - list[str], optional
     - Override template default events
   * - ``token_owner``
     - string, optional
     - User URL (required if template has ``use_token_owner``)

test_hook
^^^^^^^^^

Tests a hook by auto-generating a realistic payload and executing it.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``hook_id``
     - int, required
     - Hook ID
   * - ``event``
     - HookEvent, required
     - e.g. ``annotation_content``, ``annotation_status``
   * - ``action``
     - HookAction, required
     - e.g. ``initialize``, ``confirm``, ``export``
   * - ``annotation``
     - string, optional
     - Annotation URL for real data
   * - ``status``
     - string, optional
     - Annotation status
   * - ``previous_status``
     - string, optional
     - Previous annotation status
   * - ``config``
     - dict, optional
     - Config override for test run

**Returns:** Hook response and execution logs.

Rules & Actions
---------------

create_rule
^^^^^^^^^^^

Creates a new business rule with trigger conditions and actions.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``name``
     - string, required
     - Rule name
   * - ``trigger_condition``
     - string, required
     - TxScript formula (e.g. ``"field.amount > 10000"``)
   * - ``actions``
     - list[dict], required
     - Actions with ``id``, ``type``, ``event``, ``payload``
   * - ``enabled``
     - bool, optional
     - Default: true
   * - ``schema_id``
     - int, optional
     - Schema ID (at least one of ``schema_id`` or ``queue_ids`` required)
   * - ``queue_ids``
     - list[int], optional
     - Queue IDs to scope the rule

**Action types:** ``show_message``, ``add_automation_blocker``, ``add_validation_source``, ``change_queue``, ``send_email``, ``hide_field``, ``show_field``, ``show_hide_field``, ``change_status``, ``add_label``, ``remove_label``, ``custom``

patch_rule
^^^^^^^^^^

Partial update of a business rule. Only provided fields are updated.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``rule_id``
     - int, required
     - Rule ID
   * - ``name``
     - string, optional
     - Rule name
   * - ``trigger_condition``
     - string, optional
     - TxScript formula
   * - ``actions``
     - list[dict], optional
     - Updated actions
   * - ``enabled``
     - bool, optional
     - Enable/disable
   * - ``queue_ids``
     - list[int], optional
     - Queue IDs (``[]`` removes all queue associations)

Workspace Management
--------------------

create_workspace
^^^^^^^^^^^^^^^^

Creates a new workspace.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``name``
     - string, required
     - Workspace name
   * - ``organization_id``
     - int, required
     - Organization ID
   * - ``metadata``
     - dict, optional
     - Custom metadata

User Management
---------------

create_user
^^^^^^^^^^^

Creates a new user. Use ``search(query={"entity": "user_role"})`` to get role/group URLs.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``username``
     - string, required
     - Username
   * - ``email``
     - string, required
     - Email address
   * - ``queues``
     - list[str], optional
     - Queue URLs to assign
   * - ``groups``
     - list[str], optional
     - Group/role URLs to assign
   * - ``first_name``
     - string, optional
     - First name
   * - ``last_name``
     - string, optional
     - Last name
   * - ``is_active``
     - bool, optional
     - Default: true
   * - ``metadata``
     - dict, optional
     - Custom metadata
   * - ``oidc_id``
     - string, optional
     - OIDC identity for SSO
   * - ``auth_type``
     - string, optional
     - Authentication type (default: ``password``)

update_user
^^^^^^^^^^^

Patches a user; only provided fields change.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``user_id``
     - int, required
     - User ID
   * - ``username``
     - string, optional
     - Updated username
   * - ``email``
     - string, optional
     - Updated email
   * - ``first_name``
     - string, optional
     - Updated first name
   * - ``last_name``
     - string, optional
     - Updated last name
   * - ``queues``
     - list[str], optional
     - New queue URLs
   * - ``groups``
     - list[str], optional
     - New group/role URLs
   * - ``is_active``
     - bool, optional
     - Active status
   * - ``metadata``
     - dict, optional
     - Updated metadata
   * - ``oidc_id``
     - string, optional
     - Updated OIDC identity
   * - ``auth_type``
     - string, optional
     - Updated auth type
   * - ``ui_settings``
     - dict, optional
     - Updated UI settings

Email Templates
---------------

create_email_template
^^^^^^^^^^^^^^^^^^^^^

Creates a new email template.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``name``
     - string, required
     - Template name
   * - ``queue``
     - int, required
     - Queue ID
   * - ``subject``
     - string, required
     - Email subject
   * - ``message``
     - string, required
     - Email body (HTML supported)
   * - ``type``
     - string, optional
     - ``rejection``, ``rejection_default``, ``email_with_no_processable_attachments``, or ``custom`` (default)
   * - ``automate``
     - bool, optional
     - Auto-send on trigger (default: false)
   * - ``to``
     - list[dict], optional
     - Recipients
   * - ``cc``
     - list[dict], optional
     - CC recipients
   * - ``bcc``
     - list[dict], optional
     - BCC recipients
   * - ``triggers``
     - list[str], optional
     - Trigger event names

**Recipient types:** ``{"type": "annotator", "value": ""}``, ``{"type": "constant", "value": "email@example.com"}``, ``{"type": "datapoint", "value": "email_field_id"}``

Discovery
---------

list_tool_categories
^^^^^^^^^^^^^^^^^^^^

Lists all available tool categories with descriptions, tool names, read/write status, and keywords for dynamic tool loading.

**Available categories:** ``read``, ``annotations``, ``queues``, ``schemas``, ``engines``, ``hooks``, ``email_templates``, ``rules``, ``users``, ``workspaces``

MCP Mode
--------

get_mcp_mode
^^^^^^^^^^^^^

Returns the current MCP operation mode.

**Returns:** ``{"mode": "read-only"}`` or ``{"mode": "read-write"}``
