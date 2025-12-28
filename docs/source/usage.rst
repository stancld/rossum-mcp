Usage
=====

Running the MCP Server
-----------------------

Start the server using:

.. code-block:: bash

   python -m rossum_mcp.server

Or if installed as a package:

.. code-block:: bash

   rossum-mcp

Using with MCP Clients
----------------------

Claude Desktop Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Configure your MCP client to use this server. For example, in Claude Desktop's config:

.. code-block:: json

   {
     "mcpServers": {
       "rossum": {
         "command": "python",
         "args": ["/path/to/rossum-mcp/rossum-mcp/rossum_mcp/server.py"],
         "env": {
           "ROSSUM_API_TOKEN": "your-api-token",
           "ROSSUM_API_BASE_URL": "https://api.elis.rossum.ai/v1",
           "ROSSUM_MCP_MODE": "read-write"
         }
       }
     }
   }

For read-only access , use ``"ROSSUM_MCP_MODE": "read-only"`` to restrict access to read-only operations (GET/LIST only).

Running the AI Agent
--------------------

The ``rossum_agent`` package provides CLI and web interfaces:

.. code-block:: bash

   # CLI interface
   rossum-agent

   # Streamlit web UI
   streamlit run rossum-agent/rossum_agent/app.py

   # Or run with Docker Compose
   docker-compose up rossum-agent

The agent includes file system tools, plotting capabilities, and Rossum integration.
See the :doc:`examples` section for complete workflows.

Using Rossum Deploy
-------------------

The ``rossum_deploy`` package provides Python API and CLI for configuration deployment.

Python API
^^^^^^^^^^

.. code-block:: python

   from rossum_deploy import Workspace

   # Initialize workspace
   ws = Workspace(
       "./my-project",
       api_base="https://api.elis.rossum.ai/v1",
       token="your-token"
   )

   # Pull all objects from an organization
   result = ws.pull(org_id=123456)
   print(result.summary())

   # Show diff between local and remote
   diff = ws.diff()
   print(diff.summary())

   # Push changes (dry run first)
   result = ws.push(dry_run=True)
   print(result.summary())

   # Push for real
   result = ws.push()

CLI Commands
^^^^^^^^^^^^

Set environment variables:

.. code-block:: bash

   export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
   export ROSSUM_API_TOKEN="your-token"

Commands:

.. code-block:: bash

   # Pull from organization
   rossum-deploy pull 123456

   # Show diff
   rossum-deploy diff

   # Push (dry run)
   rossum-deploy push --dry-run

   # Push for real
   rossum-deploy push

Cross-Organization Deployment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Deploy configurations from sandbox to production:

.. code-block:: python

   from rossum_deploy import Workspace

   ws = Workspace("./my-project", api_base="...", token="...")

   # Copy production config to sandbox (one-time setup)
   result = ws.copy_org(
       source_org_id=123456,  # Production
       target_org_id=789012,  # Sandbox
   )

   # After agent modifies sandbox, deploy back to production
   result = ws.deploy(target_org_id=123456, dry_run=True)
   print(result.summary())

Using with AI Agents
--------------------

The Rossum Agent is built with Anthropic Claude for intelligent document processing.
The agent includes file system tools, plotting capabilities, and seamless Rossum integration.

Available Tools
---------------

upload_document
^^^^^^^^^^^^^^^

Uploads a document to Rossum for processing. Returns a task ID. Use ``list_annotations``
to get the annotation ID.

**Parameters:**

- ``file_path`` (string, required): Absolute path to the document file
- ``queue_id`` (integer, required): Rossum queue ID where the document should be uploaded

**Returns:**

.. code-block:: json

   {
     "task_id": "12345",
     "task_status": "created",
     "queue_id": 12345,
     "message": "Document upload initiated. Use `list_annotations` to find the annotation ID for this queue."
   }

get_annotation
^^^^^^^^^^^^^^

Retrieves annotation data for a previously uploaded document. Use this to check the
status of a document.

**Parameters:**

- ``annotation_id`` (integer, required): The annotation ID obtained from list_annotations
- ``sideloads`` (array, optional): List of sideloads to include. Use ``['content']`` to
  fetch annotation content with datapoints

**Returns:**

.. code-block:: json

   {
     "id": "12345",
     "status": "to_review",
     "url": "https://elis.rossum.ai/api/v1/annotations/12345",
     "schema": "67890",
     "modifier": "11111",
     "document": "22222",
     "content": [...],
     "created_at": "2024-01-01T00:00:00Z",
     "modified_at": "2024-01-01T00:00:00Z"
   }

list_annotations
^^^^^^^^^^^^^^^^

Lists all annotations for a queue with optional filtering. Useful for checking the
status of multiple uploaded documents.

**Parameters:**

- ``queue_id`` (integer, required): Rossum queue ID to list annotations from
- ``status`` (string, optional): Filter by annotation status
  (default: 'importing,to_review,confirmed,exported')

**Returns:**

.. code-block:: json

   {
     "count": 42,
     "results": [
       {
         "id": "12345",
         "status": "to_review",
         "url": "https://elis.rossum.ai/api/v1/annotations/12345",
         "document": "67890",
         "created_at": "2024-01-01T00:00:00Z",
         "modified_at": "2024-01-01T00:00:00Z"
       }
     ]
   }

get_queue
^^^^^^^^^

Retrieves queue details including the schema_id. Use this to get the schema_id for
use with get_schema.

**Parameters:**

- ``queue_id`` (integer, required): Rossum queue ID to retrieve

**Returns:**

.. code-block:: json

   {
     "id": "12345",
     "name": "Invoices",
     "url": "https://elis.rossum.ai/api/v1/queues/12345",
     "schema_id": "67890",
     "workspace": "11111",
     "inbox": "22222",
     "created_at": "2024-01-01T00:00:00Z",
     "modified_at": "2024-01-01T00:00:00Z"
   }

get_schema
^^^^^^^^^^

Retrieves schema details including the schema content/structure. Use get_queue first
to obtain the schema_id.

**Parameters:**

- ``schema_id`` (integer, required): Rossum schema ID to retrieve

**Returns:**

.. code-block:: json

   {
     "id": "67890",
     "name": "Invoice Schema",
     "url": "https://elis.rossum.ai/api/v1/schemas/67890",
     "content": [...]
   }

get_queue_schema
^^^^^^^^^^^^^^^^

Retrieves the complete schema for a queue in a single call. This is the recommended
way to get a queue's schema.

**Parameters:**

- ``queue_id`` (integer, required): Rossum queue ID

**Returns:**

.. code-block:: json

   {
     "queue_id": "12345",
     "queue_name": "Invoices",
     "schema_id": "67890",
     "schema_name": "Invoice Schema",
     "schema_url": "https://elis.rossum.ai/api/v1/schemas/67890",
     "schema_content": [...]
   }

get_queue_engine
^^^^^^^^^^^^^^^^

Retrieves the complete engine information for a given queue in a single call. Returns
engine type (dedicated, generic, or standard) and details.

**Parameters:**

- ``queue_id`` (integer, required): Rossum queue ID

**Returns:**

.. code-block:: json

   {
     "queue_id": "12345",
     "queue_name": "Invoices",
     "engine_id": 67890,
     "engine_name": "My Engine",
     "engine_url": "https://elis.rossum.ai/api/v1/engines/67890",
     "engine_type": "dedicated"
   }

create_queue
^^^^^^^^^^^^

Creates a new queue with schema and optional engine assignment. Allows full configuration
of queue settings including automation and training.

**Parameters:**

- ``name`` (string, required): Name of the queue to create
- ``workspace_id`` (integer, required): Workspace ID where the queue should be created
- ``schema_id`` (integer, required): Schema ID to assign to the queue
- ``engine_id`` (integer, optional): Optional engine ID to assign for document processing
- ``inbox_id`` (integer, optional): Optional inbox ID to assign
- ``connector_id`` (integer, optional): Optional connector ID to assign
- ``locale`` (string, optional): Queue locale (default: "en_GB")
- ``automation_enabled`` (boolean, optional): Enable automation (default: false)
- ``automation_level`` (string, optional): Automation level - "never", "always", etc. (default: "never")
- ``training_enabled`` (boolean, optional): Enable training (default: true)

**Returns:**

.. code-block:: json

   {
     "id": "12345",
     "name": "My New Queue",
     "url": "https://elis.rossum.ai/api/v1/queues/12345",
     "workspace": "https://elis.rossum.ai/api/v1/workspaces/11111",
     "schema": "https://elis.rossum.ai/api/v1/schemas/67890",
     "engine": "https://elis.rossum.ai/api/v1/engines/54321",
     "inbox": null,
     "connector": null,
     "locale": "en_GB",
     "automation_enabled": false,
     "automation_level": "never",
     "training_enabled": true,
     "message": "Queue 'My New Queue' created successfully with ID 12345"
   }

update_queue
^^^^^^^^^^^^

Updates an existing queue's settings including automation thresholds. Use this to
configure automation settings like enabling automation, setting automation level,
and defining the default confidence score threshold.

**Parameters:**

- ``queue_id`` (integer, required): Queue ID to update
- ``queue_data`` (object, required): Dictionary containing queue fields to update. Common fields:

  - ``name`` (string): Queue name
  - ``automation_enabled`` (boolean): Enable/disable automation
  - ``automation_level`` (string): "never", "always", "confident", etc.
  - ``default_score_threshold`` (float): Default confidence threshold 0.0-1.0 (e.g., 0.90 for 90%)
  - ``locale`` (string): Queue locale
  - ``training_enabled`` (boolean): Enable/disable training

**Returns:**

.. code-block:: json

   {
     "id": "12345",
     "name": "Updated Queue",
     "url": "https://elis.rossum.ai/api/v1/queues/12345",
     "automation_enabled": true,
     "automation_level": "confident",
     "default_score_threshold": 0.90,
     "locale": "en_GB",
     "training_enabled": true,
     "message": "Queue 'Updated Queue' (ID 12345) updated successfully"
   }

update_schema
^^^^^^^^^^^^^

Updates an existing schema, typically used to set field-level automation thresholds.
Field-level thresholds override the queue's default_score_threshold.

**Workflow:**

1. First get the schema using ``get_queue_schema``
2. Modify the ``content`` array by adding/updating ``score_threshold`` properties on specific fields
3. Call this tool with the modified content

**Parameters:**

- ``schema_id`` (integer, required): Schema ID to update
- ``schema_data`` (object, required): Dictionary containing schema fields to update. Typically contains:

  - ``content`` (array): Full schema content array where each field can have a ``score_threshold`` property (float 0.0-1.0)

**Best Practices:**

- Use higher thresholds (0.95-0.98) for critical fields like amounts and IDs
- Use lower thresholds (0.80-0.90) for less critical fields

**Returns:**

.. code-block:: json

   {
     "id": "67890",
     "name": "Invoice Schema",
     "url": "https://elis.rossum.ai/api/v1/schemas/67890",
     "content": [...],
     "message": "Schema 'Invoice Schema' (ID 67890) updated successfully"
   }

patch_schema
^^^^^^^^^^^^

Patch a schema by adding, updating, or removing individual nodes without replacing the entire content.
This is particularly useful for making incremental changes to schemas.

**Parameters:**

- ``schema_id`` (integer, required): Schema ID to patch
- ``operation`` (string, required): One of "add", "update", or "remove"
- ``node_id`` (string, required): ID of the node to operate on
- ``node_data`` (object, optional): Data for add/update operations. Required for "add" and "update"
- ``parent_id`` (string, optional): Parent node ID for add operation. Required for "add"
- ``position`` (integer, optional): Position for add operation (appends if not specified)

**Operations:**

- **add**: Add a new datapoint/multivalue to a parent (section or tuple). Requires ``parent_id`` and ``node_data``.
- **update**: Update properties of an existing node. Requires ``node_data`` with fields to update.
- **remove**: Remove a node from the schema. Only ``node_id`` is required.

**Returns:**

.. code-block:: json

   {
     "id": 123,
     "name": "Invoice Schema",
     "content": [
       {
         "id": "header_section",
         "label": "Header",
         "category": "section",
         "children": [
           {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint"},
           {"id": "vendor_name", "label": "Vendor Name", "category": "datapoint"}
         ]
       }
     ]
   }

**Example usage:**

.. code-block:: python

   # Add a new datapoint to a section
   patch_schema(
       schema_id=123,
       operation="add",
       node_id="vendor_name",
       parent_id="header_section",
       node_data={"label": "Vendor Name", "type": "string", "category": "datapoint"}
   )

   # Update a field's label and threshold
   patch_schema(
       schema_id=123,
       operation="update",
       node_id="invoice_number",
       node_data={"label": "Invoice #", "score_threshold": 0.9}
   )

   # Remove a field
   patch_schema(
       schema_id=123,
       operation="remove",
       node_id="old_field"
   )

update_engine
^^^^^^^^^^^^^

Updates an existing engine's settings including learning and training queues.

**Parameters:**

- ``engine_id`` (integer, required): Engine ID to update
- ``engine_data`` (object, required): Dictionary containing engine fields to update:

  - ``name`` (string): Engine name
  - ``description`` (string): Engine description
  - ``learning_enabled`` (boolean): Enable/disable learning
  - ``training_queues`` (array): List of queue URLs for training

**Example:**

.. code-block:: json

   {
     "learning_enabled": true,
     "training_queues": [
       "https://elis.rossum.ai/api/v1/queues/12345",
       "https://elis.rossum.ai/api/v1/queues/67890"
     ]
   }

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "My Engine",
     "url": "https://elis.rossum.ai/api/v1/engines/12345",
     "type": "extractor",
     "learning_enabled": true,
     "training_queues": [...],
     "description": "Engine description",
     "message": "Engine 'My Engine' (ID 12345) updated successfully"
   }

create_schema
^^^^^^^^^^^^^

Creates a new schema with sections and datapoints.

**Parameters:**

- ``name`` (string, required): Schema name
- ``content`` (array, required): Schema content array containing sections with datapoints.
  Must follow Rossum schema structure with sections containing children.

**Example content structure:**

.. code-block:: json

   [
     {
       "category": "section",
       "id": "document_info",
       "label": "Document Information",
       "children": [
         {
           "category": "datapoint",
           "id": "document_type",
           "label": "Document Type",
           "type": "enum",
           "rir_field_names": [],
           "constraints": {"required": false},
           "options": [
             {"value": "invoice", "label": "Invoice"},
             {"value": "receipt", "label": "Receipt"}
           ]
         }
       ]
     }
   ]

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "My Schema",
     "url": "https://elis.rossum.ai/api/v1/schemas/12345",
     "content": [...],
     "message": "Schema 'My Schema' created successfully with ID 12345"
   }

get_engine
^^^^^^^^^^

Retrieves a single engine by ID.

**Parameters:**

- ``engine_id`` (integer, required): The engine ID to retrieve

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "My Engine",
     "url": "https://elis.rossum.ai/api/v1/engines/12345",
     "type": "extractor",
     "learning_enabled": true,
     "training_queues": ["https://elis.rossum.ai/api/v1/queues/100"],
     "description": "Engine description",
     "agenda_id": "abc123",
     "organization": "https://elis.rossum.ai/api/v1/organizations/123"
   }

list_engines
^^^^^^^^^^^^

Lists all engines with optional filtering.

**Parameters:**

- ``id`` (integer, optional): Filter by engine ID
- ``engine_type`` (string, optional): Filter by engine type ('extractor' or 'splitter')
- ``agenda_id`` (string, optional): Filter by agenda ID

**Returns:**

.. code-block:: json

   {
     "count": 2,
     "results": [
       {
         "id": 12345,
         "name": "My Engine",
         "url": "https://elis.rossum.ai/api/v1/engines/12345",
         "type": "extractor",
         "learning_enabled": true,
         "training_queues": ["https://elis.rossum.ai/api/v1/queues/100"],
         "description": "Engine description",
         "agenda_id": "abc123",
         "organization": "https://elis.rossum.ai/api/v1/organizations/123"
       }
     ],
     "message": "Retrieved 2 engine(s)"
   }

**Example:**

.. code-block:: python

   # List all engines
   all_engines = list_engines()

   # List specific engine by ID
   engine = list_engines(id=12345)

   # List extractors only
   extractors = list_engines(engine_type="extractor")

   # List engines by agenda
   agenda_engines = list_engines(agenda_id="abc123")

create_engine
^^^^^^^^^^^^^

Creates a new engine for document processing.

**Parameters:**

- ``name`` (string, required): Engine name
- ``organization_id`` (integer, required): Organization ID where the engine should be created
- ``engine_type`` (string, required): Engine type - either 'extractor' or 'splitter'

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "My Engine",
     "url": "https://elis.rossum.ai/api/v1/engines/12345",
     "type": "extractor",
     "organization": "https://elis.rossum.ai/api/v1/organizations/123",
     "message": "Engine 'My Engine' created successfully with ID 12345"
   }

create_engine_field
^^^^^^^^^^^^^^^^^^^

Creates a new engine field and links it to schemas. Engine fields define what data the
engine extracts and must be created for each field in the schema when setting up an engine.

**Parameters:**

- ``engine_id`` (integer, required): Engine ID to which this field belongs
- ``name`` (string, required): Field name (slug format, max 50 chars)
- ``label`` (string, required): Human-readable label (max 100 chars)
- ``field_type`` (string, required): Field type - 'string', 'number', 'date', or 'enum'
- ``schema_ids`` (array, required): List of schema IDs to link this engine field to (at least one required)
- ``tabular`` (boolean, optional): Whether this field is in a table (default: false)
- ``multiline`` (string, optional): Multiline setting - 'true', 'false', or '' (default: 'false')
- ``subtype`` (string, optional): Optional field subtype (max 50 chars)
- ``pre_trained_field_id`` (string, optional): Optional pre-trained field ID (max 50 chars)

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "invoice_number",
     "label": "Invoice Number",
     "url": "https://elis.rossum.ai/api/v1/engine_fields/12345",
     "type": "string",
     "engine": "https://elis.rossum.ai/api/v1/engines/123",
     "tabular": false,
     "multiline": "false",
     "schema_ids": [456, 789],
     "message": "Engine field 'Invoice Number' created successfully with ID 12345 and linked to 2 schema(s)"
   }

get_engine_fields
^^^^^^^^^^^^^^^^^

Retrieves engine fields for a specific engine or all engine fields.

**Parameters:**

- ``engine_id`` (integer, optional): Engine ID to filter fields by. If not provided, retrieves all engine fields.

**Returns:**

.. code-block:: json

   {
     "count": 2,
     "results": [
       {
         "id": 12345,
         "url": "https://elis.rossum.ai/api/v1/engine_fields/12345",
         "engine": "https://elis.rossum.ai/api/v1/engines/123",
         "name": "invoice_number",
         "label": "Invoice Number",
         "type": "string",
         "subtype": null,
         "tabular": false,
         "multiline": "false",
         "pre_trained_field_id": null,
         "schemas": ["https://elis.rossum.ai/api/v1/schemas/456"]
       },
       {
         "id": 12346,
         "url": "https://elis.rossum.ai/api/v1/engine_fields/12346",
         "engine": "https://elis.rossum.ai/api/v1/engines/123",
         "name": "invoice_date",
         "label": "Invoice Date",
         "type": "date",
         "subtype": null,
         "tabular": false,
         "multiline": "false",
         "pre_trained_field_id": null,
         "schemas": ["https://elis.rossum.ai/api/v1/schemas/456"]
       }
     ]
   }

**Example usage:**

.. code-block:: python

   # Get all engine fields for a specific engine
   engine_fields = get_engine_fields(engine_id=123)

   # Get all engine fields
   all_fields = get_engine_fields()

start_annotation
^^^^^^^^^^^^^^^^

Starts an annotation to move it from 'importing' to 'reviewing' status. This is required
before you can update annotation fields.

**Parameters:**

- ``annotation_id`` (integer, required): Rossum annotation ID to start

**Returns:**

.. code-block:: json

   {
     "annotation_id": 12345,
     "message": "Annotation 12345 started successfully. Status changed to 'reviewing'."
   }

bulk_update_annotation_fields
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Bulk update annotation field values using JSON Patch operations. This is the correct way
to update annotation field values. Must be called after ``start_annotation``.

**Parameters:**

- ``annotation_id`` (integer, required): Rossum annotation ID to update
- ``operations`` (array, required): List of JSON Patch operations with format:

  .. code-block:: json

     [
       {
         "op": "replace",
         "id": 1234,
         "value": {
           "content": {
             "value": "new_value",
             "page": 1,
             "position": [x, y, w, h]
           }
         }
       }
     ]

**Important:** Use the numeric datapoint ``id`` from ``annotation.content``, NOT the ``schema_id``.

**Returns:**

.. code-block:: json

   {
     "annotation_id": 12345,
     "operations_count": 1,
     "message": "Annotation 12345 updated with 1 operations successfully."
   }

confirm_annotation
^^^^^^^^^^^^^^^^^^

Confirms an annotation to move it to 'confirmed' status. Can be called after
``bulk_update_annotation_fields``.

**Parameters:**

- ``annotation_id`` (integer, required): Rossum annotation ID to confirm

**Returns:**

.. code-block:: json

   {
     "annotation_id": 12345,
     "message": "Annotation 12345 confirmed successfully. Status changed to 'confirmed'."
   }

get_hook
^^^^^^^^

Retrieves details of a specific hook/extension by its ID.

**Parameters:**

- ``hook_id`` (integer, required): Hook ID

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "Validation Hook",
     "url": "https://elis.rossum.ai/api/v1/hooks/12345",
     "type": "webhook",
     "active": true,
     "queues": ["https://elis.rossum.ai/api/v1/queues/100"],
     "events": ["annotation_status", "annotation_content"],
     "config": {
       "url": "https://example.com/webhook",
       "secret": "***"
     },
     "settings": {},
     "extension_source": "rossum_store"
   }

**Example usage:**

.. code-block:: python

   # Get hook details
   hook = get_hook(hook_id=12345)

list_hooks
^^^^^^^^^^

Lists all hooks/extensions configured in your organization. Hooks (also called extensions)
are webhooks or serverless functions that respond to Rossum events.

**Parameters:**

- ``queue_id`` (integer, optional): Filter hooks by queue ID
- ``active`` (boolean, optional): Filter by active status (true for active hooks, false for inactive)

**Returns:**

.. code-block:: json

   {
     "count": 2,
     "results": [
       {
         "id": 12345,
         "name": "Validation Hook",
         "url": "https://elis.rossum.ai/api/v1/hooks/12345",
         "type": "webhook",
         "active": true,
         "queues": ["https://elis.rossum.ai/api/v1/queues/100"],
         "events": ["annotation_status", "annotation_content"],
         "config": {
           "url": "https://example.com/webhook",
           "secret": "***"
         },
         "extension_source": "rossum_store"
       }
     ]
   }

**Example usage:**

.. code-block:: python

   # List all hooks
   all_hooks = list_hooks()

   # List hooks for a specific queue
   queue_hooks = list_hooks(queue_id=12345)

   # List only active hooks
   active_hooks = list_hooks(active=True)

create_hook
^^^^^^^^^^^

Creates a new hook (webhook or serverless function). Hooks respond to Rossum events and
can be used for custom validation, data enrichment, or integration with external systems.

**Parameters:**

- ``name`` (string, required): Hook name
- ``type`` (string, required): Hook type - either 'webhook' or 'function'
- ``queues`` (array, optional): List of queue URLs to attach the hook to. If not provided,
  hook applies to all queues. Format: ``["https://api.elis.rossum.ai/v1/queues/12345"]``
- ``events`` (array, optional): List of events that trigger the hook. Common events:

  - ``annotation_content.initialize`` - When annotation is first created
  - ``annotation_content.confirm`` - When annotation is confirmed
  - ``annotation_content.export`` - When annotation is exported
  - ``annotation_status`` - When annotation status changes
  - ``annotation_content`` - When annotation content changes
  - ``datapoint_value`` - When individual field value changes

- ``config`` (object, optional): Hook configuration

  - For webhook: ``{"url": "https://example.com/webhook"}``
  - For function: ``{"runtime": "python3.12", "function": "import json\ndef rossum_hook_request_handler(payload):\n    return {}"}``

- ``settings`` (object, optional): Specific settings included in the payload when executing the hook
- ``secret`` (string, optional): Secret key for securing webhook requests

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "My Hook",
     "url": "https://elis.rossum.ai/api/v1/hooks/12345",
     "enabled": true,
     "queues": ["https://elis.rossum.ai/api/v1/queues/100"],
     "events": ["annotation_content.initialize"],
     "config": {"runtime": "python3.12", "function": "..."},
     "settings": {"custom_key": "custom_value"},
     "message": "Hook 'My Hook' created successfully with ID 12345"
   }

update_hook
^^^^^^^^^^^

Updates an existing hook. Use this to modify hook properties like name, queues, events, config,
settings, or active status. Only provide the fields you want to change - other fields will remain unchanged.

**Parameters:**

- ``hook_id`` (integer, required): ID of the hook to update
- ``name`` (string, optional): New name for the hook
- ``queues`` (array, optional): List of queue URLs to attach the hook to
- ``events`` (array, optional): List of events that trigger the hook
- ``config`` (object, optional): Hook configuration
- ``settings`` (object, optional): Hook settings
- ``active`` (boolean, optional): Whether the hook is active

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "Updated Hook Name",
     "url": "https://elis.rossum.ai/api/v1/hooks/12345",
     "active": true,
     "queues": ["https://elis.rossum.ai/api/v1/queues/100"],
     "events": ["annotation_content.initialize"],
     "config": {"runtime": "python3.12", "function": "..."},
     "settings": {}
   }

**Example usage:**

.. code-block:: python

   # Rename a hook
   update_hook(hook_id=12345, name="New Hook Name")

   # Deactivate a hook
   update_hook(hook_id=12345, active=False)

   # Change hook events
   update_hook(hook_id=12345, events=["annotation_content.confirm"])

list_hook_templates
^^^^^^^^^^^^^^^^^^^

Lists available hook templates from Rossum Store. Hook templates provide pre-built extension
configurations (e.g., data validation, field mapping, notifications) that can be used to
quickly create hooks instead of writing code from scratch.

**Parameters:**

None

**Returns:**

.. code-block:: json

   [
     {
       "id": 5,
       "url": "https://elis.rossum.ai/api/v1/hook_templates/5",
       "name": "Document Splitting",
       "description": "Automatically split multi-page documents into separate annotations",
       "type": "function",
       "events": ["annotation_content.initialize"],
       "config": {"runtime": "python3.12", "function": "..."},
       "settings_schema": {"type": "object", "properties": {}},
       "guide": "https://knowledge-base.rossum.ai/docs/..."
     }
   ]

**Example usage:**

.. code-block:: python

   # List all available hook templates
   templates = list_hook_templates()

   # Find a template by name
   for template in templates:
       if "splitting" in template.name.lower():
           print(f"Found: {template.name} (ID: {template.id})")

create_hook_from_template
^^^^^^^^^^^^^^^^^^^^^^^^^

Creates a hook from a Rossum Store template. Use ``list_hook_templates`` first to find
available templates and their IDs. This is the recommended way to create hooks as it
uses battle-tested configurations from the Rossum Store.

**Parameters:**

- ``name`` (string, required): Name for the new hook
- ``hook_template_id`` (integer, required): ID of the hook template to use (from ``list_hook_templates``)
- ``queues`` (array, required): List of queue URLs to attach the hook to
- ``events`` (array, optional): List of events to trigger the hook (overrides template defaults if provided)
- ``token_owner`` (string, optional but required for some templates): User URL to use as token owner when the template has ``use_token_owner=True``. Obtain this via ``list_users``.

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "My Document Splitting Hook",
     "url": "https://elis.rossum.ai/api/v1/hooks/12345",
     "hook_template": "https://elis.rossum.ai/api/v1/hook_templates/5",
     "type": "function",
     "queues": ["https://elis.rossum.ai/api/v1/queues/100"],
     "events": ["annotation_content.initialize"],
     "config": {},
     "settings": {}
   }

**Example usage:**

.. code-block:: python

   # Create a hook from template
   create_hook_from_template(
       name="Invoice Splitting",
       hook_template_id=5,
       queues=["https://api.elis.rossum.ai/v1/queues/12345"],
       token_owner="https://api.elis.rossum.ai/v1/users/12345"
   )

list_hook_logs
^^^^^^^^^^^^^^

Lists hook execution logs for debugging, monitoring performance, and troubleshooting errors.
Logs are retained for 7 days and at most 100 logs are returned per call.

**Parameters:**

- ``hook_id`` (integer, optional): Filter by hook ID
- ``queue_id`` (integer, optional): Filter by queue ID
- ``annotation_id`` (integer, optional): Filter by annotation ID
- ``email_id`` (integer, optional): Filter by email ID
- ``log_level`` (string, optional): Filter by log level - 'INFO', 'ERROR', or 'WARNING'
- ``status`` (string, optional): Filter by execution status
- ``status_code`` (integer, optional): Filter by HTTP status code
- ``request_id`` (string, optional): Filter by request ID
- ``timestamp_before`` (string, optional): ISO 8601 timestamp, filter logs triggered before this time
- ``timestamp_after`` (string, optional): ISO 8601 timestamp, filter logs triggered after this time
- ``start_before`` (string, optional): ISO 8601 timestamp, filter logs started before this time
- ``start_after`` (string, optional): ISO 8601 timestamp, filter logs started after this time
- ``end_before`` (string, optional): ISO 8601 timestamp, filter logs ended before this time
- ``end_after`` (string, optional): ISO 8601 timestamp, filter logs ended after this time
- ``search`` (string, optional): Full-text search across log messages
- ``page_size`` (integer, optional): Number of results per page (default 100, max 100)

**Returns:**

.. code-block:: json

   {
     "count": 2,
     "results": [
       {
         "log_level": "INFO",
         "action": "initialize",
         "event": "annotation_content",
         "request_id": "abc123",
         "organization_id": 100,
         "hook_id": 12345,
         "hook_type": "function",
         "queue_id": 200,
         "annotation_id": 300,
         "message": "Hook executed successfully",
         "start": "2024-01-01T00:00:00Z",
         "end": "2024-01-01T00:00:01Z",
         "status": "success",
         "status_code": 200,
         "timestamp": "2024-01-01T00:00:00Z",
         "uuid": "uuid-here"
       }
     ]
   }

**Example usage:**

.. code-block:: python

   # List all logs for a specific hook
   logs = list_hook_logs(hook_id=12345)

   # List error logs only
   error_logs = list_hook_logs(log_level="ERROR")

   # List logs for a specific annotation
   annotation_logs = list_hook_logs(annotation_id=300)

   # Search logs by message content
   search_logs = list_hook_logs(search="validation failed")

get_rule
^^^^^^^^

Retrieves details of a specific business rule by its ID.

**Parameters:**

- ``rule_id`` (integer, required): Rule ID

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "Auto-calculate Total",
     "url": "https://elis.rossum.ai/api/v1/rules/12345",
     "enabled": true,
     "organization": "https://elis.rossum.ai/api/v1/organizations/100",
     "schema": "https://elis.rossum.ai/api/v1/schemas/200",
     "trigger_condition": "field.amount_total.changed",
     "created_by": "https://elis.rossum.ai/api/v1/users/300",
     "created_at": "2024-01-01T00:00:00Z",
     "modified_by": "https://elis.rossum.ai/api/v1/users/300",
     "modified_at": "2024-01-01T00:00:00Z",
     "rule_template": null,
     "synchronized_from_template": false,
     "actions": [
       {
         "id": 54321,
         "type": "set_datapoint_value",
         "payload": {
           "datapoint_id": "tax_amount",
           "value": "field.amount_total.value * 0.2"
         },
         "event": "trigger",
         "enabled": true
       }
     ]
   }

**Example usage:**

.. code-block:: python

   # Get rule details
   rule = get_rule(rule_id=12345)

list_rules
^^^^^^^^^^

Lists all business rules configured in your organization. Rules define custom business
logic with trigger conditions (TxScript formulas) and actions that execute when conditions are met.

**Parameters:**

- ``schema_id`` (integer, optional): Filter rules by schema ID
- ``organization_id`` (integer, optional): Filter rules by organization ID
- ``enabled`` (boolean, optional): Filter by enabled status (true for enabled rules, false for disabled)

**Returns:**

.. code-block:: json

   {
     "count": 2,
     "results": [
       {
         "id": 12345,
         "name": "Auto-calculate Total",
         "url": "https://elis.rossum.ai/api/v1/rules/12345",
         "enabled": true,
         "organization": "https://elis.rossum.ai/api/v1/organizations/100",
         "schema": "https://elis.rossum.ai/api/v1/schemas/200",
         "trigger_condition": "field.amount_total.changed",
         "created_by": "https://elis.rossum.ai/api/v1/users/300",
         "created_at": "2024-01-01T00:00:00Z",
         "modified_by": "https://elis.rossum.ai/api/v1/users/300",
         "modified_at": "2024-01-01T00:00:00Z",
         "rule_template": null,
         "synchronized_from_template": false,
         "actions": [
           {
             "id": 54321,
             "type": "set_datapoint_value",
             "payload": {
               "datapoint_id": "tax_amount",
               "value": "field.amount_total.value * 0.2"
             },
             "event": "trigger",
             "enabled": true
           }
         ]
       }
     ]
   }

**Example usage:**

.. code-block:: python

   # List all rules
   all_rules = list_rules()

   # List rules for a specific schema
   schema_rules = list_rules(schema_id=12345)

   # List only enabled rules
   enabled_rules = list_rules(enabled=True)

User Management
---------------

get_user
^^^^^^^^

Retrieves a single user by ID. Use ``list_users`` first to find users by username or email.

**Parameters:**

- ``user_id`` (integer, required): The user ID to retrieve

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "url": "https://elis.rossum.ai/api/v1/users/12345",
     "username": "john.doe@example.com",
     "first_name": "John",
     "last_name": "Doe",
     "email": "john.doe@example.com",
     "organization": "https://elis.rossum.ai/api/v1/organizations/100",
     "is_active": true,
     "date_joined": "2024-01-01T00:00:00Z",
     "last_login": "2024-01-15T10:30:00Z"
   }

list_users
^^^^^^^^^^

Lists users in the organization. Use this to find a user's URL when you need it for
``token_owner`` in ``create_hook_from_template``.

**Parameters:**

- ``username`` (string, optional): Filter by exact username
- ``email`` (string, optional): Filter by email address
- ``first_name`` (string, optional): Filter by first name
- ``last_name`` (string, optional): Filter by last name
- ``is_active`` (boolean, optional): Filter by active status

**Returns:**

.. code-block:: json

   [
     {
       "id": 12345,
       "url": "https://elis.rossum.ai/api/v1/users/12345",
       "username": "john.doe@example.com",
       "first_name": "John",
       "last_name": "Doe",
       "email": "john.doe@example.com",
       "organization": "https://elis.rossum.ai/api/v1/organizations/100",
       "is_active": true
     }
   ]

**Example usage:**

.. code-block:: python

   # Find user by username to get their URL for token_owner
   users = list_users(username="john.doe@example.com")
   if users:
       user_url = users[0].url
       # Use user_url in create_hook_from_template

list_user_roles
^^^^^^^^^^^^^^^

Lists all user roles (groups of permissions) in the organization.

**Parameters:**

None

**Returns:**

.. code-block:: json

   [
     {
       "id": 12345,
       "name": "Organization group admin",
       "url": "https://elis.rossum.ai/api/v1/groups/12345"
     },
     {
       "id": 12346,
       "name": "Admin",
       "url": "https://elis.rossum.ai/api/v1/groups/12346"
     }
   ]

**Example usage:**

.. code-block:: python

   # List all available roles
   roles = list_user_roles()
   for role in roles:
       print(f"{role.name} (ID: {role.id})")

Relations Management
--------------------

get_relation
^^^^^^^^^^^^

Retrieves details of a specific relation by its ID. Relations introduce common relations between annotations.

**Parameters:**

- ``relation_id`` (integer, required): Relation ID

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "type": "duplicate",
     "key": "abc123def456",
     "parent": "https://elis.rossum.ai/api/v1/annotations/100",
     "annotations": [
       "https://elis.rossum.ai/api/v1/annotations/100",
       "https://elis.rossum.ai/api/v1/annotations/101"
     ],
     "url": "https://elis.rossum.ai/api/v1/relations/12345"
   }

**Example usage:**

.. code-block:: python

   # Get relation details
   relation = get_relation(relation_id=12345)

list_relations
^^^^^^^^^^^^^^

Lists all relations between annotations with optional filters. Relations introduce common relations between annotations:

- **edit**: Created after editing annotation in user interface (rotation or split of the document)
- **attachment**: One or more documents are attachments to another document
- **duplicate**: Created after importing the same document that already exists in Rossum

**Parameters:**

- ``id`` (integer, optional): Filter by relation ID
- ``type`` (string, optional): Filter by relation type ('edit', 'attachment', 'duplicate')
- ``parent`` (integer, optional): Filter by parent annotation ID
- ``key`` (string, optional): Filter by relation key
- ``annotation`` (integer, optional): Filter by annotation ID

**Returns:**

.. code-block:: json

   {
     "count": 2,
     "results": [
       {
         "id": 12345,
         "type": "duplicate",
         "key": "abc123def456",
         "parent": "https://elis.rossum.ai/api/v1/annotations/100",
         "annotations": [
           "https://elis.rossum.ai/api/v1/annotations/100",
           "https://elis.rossum.ai/api/v1/annotations/101"
         ],
         "url": "https://elis.rossum.ai/api/v1/relations/12345"
       },
       {
         "id": 12346,
         "type": "edit",
         "key": null,
         "parent": "https://elis.rossum.ai/api/v1/annotations/200",
         "annotations": [
           "https://elis.rossum.ai/api/v1/annotations/201",
           "https://elis.rossum.ai/api/v1/annotations/202"
         ],
         "url": "https://elis.rossum.ai/api/v1/relations/12346"
       }
     ]
   }

**Example usage:**

.. code-block:: python

   # List all relations
   all_relations = list_relations()

   # List duplicate relations
   duplicate_relations = list_relations(type="duplicate")

   # List relations for a specific parent annotation
   parent_relations = list_relations(parent=12345)

   # List relations containing a specific annotation
   annotation_relations = list_relations(annotation=12345)

get_document_relation
^^^^^^^^^^^^^^^^^^^^^

Retrieves details of a specific document relation by its ID. Document relations introduce additional relations between annotations and documents.

**Parameters:**

- ``document_relation_id`` (integer, required): Document relation ID

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "type": "export",
     "annotation": "https://elis.rossum.ai/api/v1/annotations/100",
     "key": "exported_file_key",
     "documents": [
       "https://elis.rossum.ai/api/v1/documents/200",
       "https://elis.rossum.ai/api/v1/documents/201"
     ],
     "url": "https://elis.rossum.ai/api/v1/document_relations/12345"
   }

**Example usage:**

.. code-block:: python

   # Get document relation details
   doc_relation = get_document_relation(document_relation_id=12345)

list_document_relations
^^^^^^^^^^^^^^^^^^^^^^^

Lists all document relations with optional filters. Document relations introduce additional relations between annotations and documents:

- **export**: Documents generated from exporting an annotation
- **einvoice**: Electronic invoice documents associated with an annotation

**Parameters:**

- ``id`` (integer, optional): Filter by document relation ID
- ``type`` (string, optional): Filter by relation type ('export', 'einvoice')
- ``annotation`` (integer, optional): Filter by annotation ID
- ``key`` (string, optional): Filter by relation key
- ``documents`` (integer, optional): Filter by document ID

**Returns:**

.. code-block:: json

   {
     "count": 2,
     "results": [
       {
         "id": 12345,
         "type": "export",
         "annotation": "https://elis.rossum.ai/api/v1/annotations/100",
         "key": "exported_file_key",
         "documents": [
           "https://elis.rossum.ai/api/v1/documents/200",
           "https://elis.rossum.ai/api/v1/documents/201"
         ],
         "url": "https://elis.rossum.ai/api/v1/document_relations/12345"
       },
       {
         "id": 12346,
         "type": "einvoice",
         "annotation": "https://elis.rossum.ai/api/v1/annotations/102",
         "key": null,
         "documents": [
           "https://elis.rossum.ai/api/v1/documents/300"
         ],
         "url": "https://elis.rossum.ai/api/v1/document_relations/12346"
       }
     ]
   }

**Example usage:**

.. code-block:: python

   # List all document relations
   all_doc_relations = list_document_relations()

   # List export-type document relations
   export_relations = list_document_relations(type="export")

   # List document relations for a specific annotation
   annotation_doc_relations = list_document_relations(annotation=100)

   # List document relations containing a specific document
   document_relations = list_document_relations(documents=200)

   Agent Tools
   -----------

   The ``rossum_agent`` package provides additional tools beyond the MCP server.

   Knowledge Base Tools
   ^^^^^^^^^^^^^^^^^^^^

   search_knowledge_base
   """"""""""""""""""""""

   Search the Rossum Knowledge Base for documentation about extensions, hooks, and configurations.

   Use this tool to find information about Rossum features, troubleshoot errors,
   and understand extension configurations. The search is performed against
   https://knowledge-base.rossum.ai/docs.

   **Parameters:**

   - ``query`` (string, required): Search query. Be specific - include extension names, error messages,
     or feature names. Examples: 'document splitting extension', 'duplicate handling configuration',
     'webhook timeout error'.
   - ``user_query`` (string, optional): The original user question for context. Pass the user's full
     question here so Opus can tailor the analysis to address their specific needs.

   **Returns:**

   JSON string with structure:

   .. code-block:: json

      {
        "status": "success",
        "query": "document splitting",
        "analysis": "## Document Splitting Extension\n\nThe document splitting extension...",
        "source_urls": ["https://knowledge-base.rossum.ai/docs/..."]
      }

   **Use cases:**

   - Finding documentation about Rossum extensions
   - Troubleshooting error messages
   - Understanding hook configurations and behaviors

   **Example usage:**

   .. code-block:: python

      # Search for document splitting documentation
      result = search_knowledge_base(
          query="document splitting extension",
          user_query="How do I configure document splitting for my queue?"
      )
      print(result)

   Hook Analysis Tools
   ^^^^^^^^^^^^^^^^^^^

   analyze_hook_dependencies
   """"""""""""""""""""""""""

   Analyze hook dependencies from a list of hooks and generate a dependency tree.

   This tool helps understand the workflow and execution order of hooks in a Rossum queue
   by analyzing their trigger events, types, and relationships.

   **Parameters:**

   - ``hooks_json`` (string, required): JSON string containing hooks data from ``list_hooks`` MCP tool.
   Expected format: ``{"count": N, "results": [{"id": ..., "name": ..., "events": [...], ...}]}``

   **Returns:**

   JSON string containing dependency analysis with:

   - ``execution_phases``: Hooks grouped by trigger event
   - ``dependency_tree``: Visual tree representation
   - ``hook_details``: Detailed information about each hook
   - ``workflow_summary``: Overall workflow description

   .. code-block:: json

   {
    "total_hooks": 5,
    "active_hooks": 4,
    "execution_phases": [
      {
        "event": "annotation_content.initialize",
        "description": "Initial setup when annotation is first created",
        "hooks": [
          {
            "id": 12345,
            "name": "Data Enrichment",
            "type": "function",
            "queues": [...],
            "config": {...}
          }
        ]
      }
    ],
    "dependency_tree": "...",
    "workflow_summary": "...",
    "hook_details": [...]
   }

   **Example usage:**

   .. code-block:: python

   # First get hooks from MCP server
   hooks_data = mcp.list_hooks(queue_id=12345)

   # Analyze dependencies
   analysis = analyze_hook_dependencies(hooks_data)
   print(analysis)

   visualize_hook_tree
   """""""""""""""""""

   Generate a visual tree diagram of hook execution flow.

   Creates an easy-to-read tree visualization showing how hooks are triggered
   throughout the document lifecycle in a Rossum queue.

   **Parameters:**

   - ``hooks_json`` (string, required): JSON string containing hooks data from ``list_hooks`` MCP tool
   - ``output_format`` (string, optional): Format for the tree visualization. Options:

   - ``"ascii"``: Simple ASCII art tree (default)
   - ``"markdown"``: Markdown-formatted tree with indentation
   - ``"mermaid"``: Mermaid diagram syntax for rendering

   **Returns:**

   String containing the tree visualization in the requested format.

   **Example ASCII output:**

   .. code-block:: text

   Document Lifecycle Flow:

   ├── [annotation_content.initialize] Initial setup when annotation is first created
   │   ├── [function] Data Enrichment (ID: 12345)
   │   └── [webhook] External Validation (ID: 12346)
   └── [annotation_content.confirm] User confirms the annotation
      └── [function] Final Check (ID: 12347)

   **Example usage:**

   .. code-block:: python

   hooks_data = mcp.list_hooks(queue_id=12345)

   # ASCII tree
   tree = visualize_hook_tree(hooks_data, output_format="ascii")
   print(tree)

   # Markdown tree
   md_tree = visualize_hook_tree(hooks_data, output_format="markdown")

   # Mermaid diagram
   mermaid = visualize_hook_tree(hooks_data, output_format="mermaid")

   explain_hook_execution_order
   """""""""""""""""""""""""""""

   Explain the execution order and timing of hooks in plain language.

   Provides a narrative explanation of when and why each hook executes,
   helping users understand the automation workflow.

   **Parameters:**

   - ``hooks_json`` (string, required): JSON string containing hooks data from ``list_hooks`` MCP tool

   **Returns:**

   Plain text explanation of hook execution flow and dependencies.

   **Example output:**

   .. code-block:: text

   HOOK EXECUTION FLOW EXPLANATION
   ==================================================

   This queue has 4 active hooks configured across 3 different trigger events.

   Here's how the hooks execute throughout the document lifecycle:

   1. ANNOTATION_CONTENT.INITIALIZE
     When: Initial setup when annotation is first created
     Hooks triggered (2):
     - Data Enrichment (Python function)
     - External Validation (Webhook call)

   2. ANNOTATION_CONTENT.CONFIRM
     When: User confirms the annotation
     Hooks triggered (1):
     - Final Check (Python function)

   WORKFLOW INSIGHTS
   --------------------------------------------------

   • Initial automation: 2 hook(s) run when documents first arrive to set up data
   • Pre-export processing: 1 hook(s) run final checks before export

   **Example usage:**

   .. code-block:: python

   hooks_data = mcp.list_hooks(queue_id=12345)
   explanation = explain_hook_execution_order(hooks_data)
   print(explanation)

   evaluate_python_hook
   """"""""""""""""""""

   Execute Rossum function hook Python code against test annotation/schema data for debugging.

   This tool runs the provided code in a restricted sandbox, looks for a function named
   ``rossum_hook_request_handler``, and calls it with a payload containing the annotation
   and optional schema data. Use this to verify hook logic without making actual API calls.

   **IMPORTANT**: This is for debugging only. No imports or external I/O are allowed.

   **Parameters:**

   - ``code`` (string, required): Full Python source containing a function:
     ``def rossum_hook_request_handler(payload): ...``
     The function receives a dict with 'annotation' and optionally 'schema' keys.
   - ``annotation_json`` (string, required): JSON string of the annotation object as seen in hook payload["annotation"].
     Get this from the ``get_annotation`` MCP tool.
   - ``schema_json`` (string, optional): JSON string of the schema object as seen in payload["schema"].
     Get this from the ``get_schema`` MCP tool.

   **Returns:**

   JSON string with structure:

   .. code-block:: json

      {
        "status": "success",
        "result": {"status": "ok", "document_id": 12345},
        "stdout": "Debug: Processing annotation\nDocument ID: 12345\n",
        "stderr": "",
        "exception": null,
        "elapsed_ms": 5.123
      }

   For errors:

   .. code-block:: json

      {
        "status": "error",
        "result": null,
        "stdout": "",
        "stderr": "",
        "exception": {
          "type": "KeyError",
          "message": "'missing_field'",
          "traceback": "Traceback (most recent call last):..."
        },
        "elapsed_ms": 2.5
      }

   **Limitations:**

   - No imports allowed (sandboxed environment)
   - No file I/O (``open()`` is blocked)
   - Limited builtins (safe subset for data manipulation)

   **Example usage:**

   .. code-block:: python

      # Get annotation data from MCP
      annotation = mcp.get_annotation(annotation_id=12345, sideloads=["content"])

      # Hook code to test
      hook_code = '''
      def rossum_hook_request_handler(payload):
          annotation = payload["annotation"]
          content = annotation.get("content", [])
          total = 0
          for field in content:
              if field.get("schema_id") == "amount_total":
                  total = float(field.get("value", 0))
          return {"total_amount": total}
      '''

      # Test the hook
      result = evaluate_python_hook(
          code=hook_code,
          annotation_json=json.dumps(annotation)
      )
      print(result)

   debug_hook
   """"""""""

   Debug a Rossum hook using an Opus sub-agent for expert analysis.

   This tool combines code execution with deep reasoning from Claude Opus 4 to:
   1. Execute the hook code against test data (using ``evaluate_python_hook``)
   2. Analyze the code and execution results with Opus
   3. Provide detailed debugging insights and fix suggestions

   Use this for complex hook debugging where you need expert-level analysis.

   **Parameters:**

   - ``code`` (string, required): Full Python source containing a ``rossum_hook_request_handler(payload)`` function.
   - ``annotation_json`` (string, required): JSON string of the annotation object from ``get_annotation`` MCP tool.
   - ``schema_json`` (string, optional): JSON string of the schema from ``get_schema`` MCP tool.

   **Returns:**

   JSON string with structure:

   .. code-block:: json

      {
        "execution": {
          "status": "success",
          "result": {"status": "ok"},
          "stdout": "",
          "stderr": "",
          "exception": null,
          "elapsed_ms": 5.0
        },
        "analysis": "## What the hook does\n\nThis hook validates...\n\n## Issues Found\n\n1. KeyError...",
        "elapsed_ms": 2500.0
      }

   **Features:**

   - **Opus-powered analysis**: Uses Claude Opus 4 for deep reasoning about hook behavior
   - **Root cause analysis**: Explains why errors occur, not just what the error is
   - **Fix suggestions**: Provides corrected code snippets you can use directly
   - **Best practices**: Recommends improvements to hook structure and patterns

   **Example usage:**

   .. code-block:: python

      # Get annotation and hook code
      annotation = mcp.get_annotation(annotation_id=12345, sideloads=["content"])
      hook = mcp.get_hook(hook_id=67890)

      # Debug the hook with Opus analysis
      result = debug_hook(
          code=hook["config"]["code"],
          annotation_json=json.dumps(annotation)
      )

      # The result contains both execution details and expert analysis
      print(result["analysis"])

Deployment Tools
----------------

The ``rossum_deploy`` package provides lightweight configuration deployment capabilities.
This is a minimalistic alternative to `deployment-manager (PRD2) <https://github.com/rossumai/deployment-manager>`_.

Workspace
^^^^^^^^^

The ``Workspace`` class is the main entry point for deployment operations.

.. code-block:: python

   from rossum_deploy import Workspace

   # Initialize workspace
   ws = Workspace(
       "./my-project",
       api_base="https://api.elis.rossum.ai/v1",
       token="your-token"
   )

   # Pull all objects from an organization
   result = ws.pull(org_id=123456)
   print(result.summary())

   # Show diff between local and remote
   diff = ws.diff()
   print(diff.summary())

   # Push changes (dry run first)
   result = ws.push(dry_run=True)
   print(result.summary())

   # Push for real
   result = ws.push(confirm=True)
   print(result.summary())

pull
^^^^

Pull objects from Rossum to local workspace.

**Parameters:**

- ``org_id`` (integer, optional): Organization ID to pull from
- ``types`` (list, optional): Object types to pull (default: all)

**Returns:**

``PullResult`` with summary of pulled objects.

.. code-block:: python

   # Pull all objects
   result = ws.pull(org_id=123456)

   # Pull specific types only
   from rossum_deploy import ObjectType
   result = ws.pull(org_id=123456, types=[ObjectType.QUEUE, ObjectType.HOOK])

diff
^^^^

Compare local workspace with remote Rossum.

**Returns:**

``DiffResult`` with status of each object (unchanged, local_modified, remote_modified, conflict).

.. code-block:: python

   diff = ws.diff()
   print(diff.summary())
   # Output:
   # # Diff Summary
   # - Unchanged: 10
   # - Local modified: 2
   # - Remote modified: 0
   # - Conflicts: 0

push
^^^^

Push local changes to Rossum.

**Parameters:**

- ``dry_run`` (boolean): If True, only show what would be pushed
- ``confirm`` (boolean): Must be True to actually push (safety mechanism)
- ``force`` (boolean): If True, push even if there are conflicts

**Returns:**

``PushResult`` with summary of pushed objects.

.. code-block:: python

   # Dry run first
   result = ws.push(dry_run=True)
   print(result.summary())

   # Push for real
   result = ws.push(confirm=True)

   # Force push (override conflicts)
   result = ws.push(confirm=True, force=True)

CLI Usage
^^^^^^^^^

Set environment variables:

.. code-block:: bash

   export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
   export ROSSUM_API_TOKEN="your-token"

Commands:

.. code-block:: bash

   # Pull from organization
   rossum-deploy pull 123456

   # Show diff
   rossum-deploy diff

   # Push (dry run)
   rossum-deploy push --dry-run

   # Push for real
   rossum-deploy push

Comparison with deployment-manager
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For complex deployments across multiple organizations, attribute overrides, and GIT-based
workflow tracking, use `deployment-manager (PRD2) <https://github.com/rossumai/deployment-manager>`_.

``rossum_deploy`` is designed for:

- Simple pull/push workflows within an AI agent
- Minimal dependency footprint
- Programmatic Python-first access
