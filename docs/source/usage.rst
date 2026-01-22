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

The ``rossum_agent`` package provides Streamlit web UI and REST API interfaces:

.. code-block:: bash

   # Streamlit web UI
   rossum-agent
   # or directly:
   streamlit run rossum-agent/rossum_agent/streamlit_app/app.py

   # REST API
   rossum-agent-api

   # Or run with Docker Compose
   docker-compose up rossum-agent

The agent includes file output, knowledge base search, hook debugging, deployment tools,
and multi-environment MCP connections. See the :doc:`examples` section for complete workflows.

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

get_queue_template_names
^^^^^^^^^^^^^^^^^^^^^^^^

Returns a list of available template names for use with ``create_queue_from_template``.

**Parameters:** None

**Returns:**

.. code-block:: json

   [
     "EU Demo Template",
     "AP&R EU Demo Template",
     "Tax Invoice EU Demo Template",
     "US Demo Template",
     "AP&R US Demo Template",
     "Tax Invoice US Demo Template",
     "UK Demo Template",
     "AP&R UK Demo Template",
     "Tax Invoice UK Demo Template",
     "CZ Demo Template",
     "Empty Organization Template",
     "Delivery Notes Demo Template",
     "Delivery Note Demo Template",
     "Chinese Invoices (Fapiao) Demo Template",
     "Tax Invoice CN Demo Template",
     "Certificates of Analysis Demo Template",
     "Purchase Order Demo Template",
     "Credit Note Demo Template",
     "Debit Note Demo Template",
     "Proforma Invoice Demo Template"
   ]

create_queue_from_template
^^^^^^^^^^^^^^^^^^^^^^^^^^

Creates a new queue from a predefined template. **Preferred method for new customer setup.**
Templates include pre-configured schema and AI engine optimized for specific document types.

**Parameters:**

- ``name`` (string, required): Name of the queue to create
- ``template_name`` (string, required): Template name (use ``get_queue_template_names`` to list)
- ``workspace_id`` (integer, required): Workspace ID where the queue should be created
- ``include_documents`` (boolean, optional): Copy documents from template queue (default: false)
- ``engine_id`` (integer, optional): Override engine assignment

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "ACME Corp - Invoices",
     "url": "https://elis.rossum.ai/api/v1/queues/12345",
     "workspace": "https://elis.rossum.ai/api/v1/workspaces/11111",
     "schema": "https://elis.rossum.ai/api/v1/schemas/67890"
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

delete_queue
^^^^^^^^^^^^

Schedules a queue for deletion. The queue will be deleted after a 24-hour delay,
allowing time to recover if needed.

**Parameters:**

- ``queue_id`` (integer, required): Queue ID to delete

**Returns:**

.. code-block:: json

   {
     "message": "Queue 12345 scheduled for deletion (starts after 24 hours)"
   }

**Note:** This operation is only available in read-write mode.

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

delete_schema
^^^^^^^^^^^^^

Deletes a schema. Schemas can only be deleted if they are not currently assigned to any queue.

**Parameters:**

- ``schema_id`` (integer, required): Schema ID to delete

**Returns:**

.. code-block:: json

   {
     "message": "Schema 12345 deleted successfully"
   }

**Note:** This operation is only available in read-write mode.

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

delete_annotation
^^^^^^^^^^^^^^^^^

Deletes an annotation by moving it to 'deleted' status. The annotation is not
permanently removed but marked as deleted.

**Parameters:**

- ``annotation_id`` (integer, required): Rossum annotation ID to delete

**Returns:**

.. code-block:: json

   {
     "message": "Annotation 12345 deleted successfully"
   }

**Note:** This operation is only available in read-write mode.

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

delete_hook
^^^^^^^^^^^

Deletes a hook/extension.

**Parameters:**

- ``hook_id`` (integer, required): Hook ID to delete

**Returns:**

.. code-block:: json

   {
     "message": "Hook 12345 deleted successfully"
   }

**Note:** This operation is only available in read-write mode.

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

delete_rule
^^^^^^^^^^^

Deletes a business rule.

**Parameters:**

- ``rule_id`` (integer, required): Rule ID to delete

**Returns:**

.. code-block:: json

   {
     "message": "Rule 12345 deleted successfully"
   }

**Note:** This operation is only available in read-write mode.

Workspace Management
--------------------

get_workspace
^^^^^^^^^^^^^

Retrieves details of a specific workspace by its ID.

**Parameters:**

- ``workspace_id`` (integer, required): Workspace ID to retrieve

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "My Workspace",
     "url": "https://elis.rossum.ai/api/v1/workspaces/12345",
     "organization": "https://elis.rossum.ai/api/v1/organizations/100",
     "queues": ["https://elis.rossum.ai/api/v1/queues/200"]
   }

list_workspaces
^^^^^^^^^^^^^^^

Lists all workspaces with optional filtering.

**Parameters:**

- ``organization_id`` (integer, optional): Filter by organization ID
- ``name`` (string, optional): Filter by workspace name

**Returns:**

.. code-block:: json

   {
     "count": 2,
     "results": [
       {
         "id": 12345,
         "name": "Production Workspace",
         "url": "https://elis.rossum.ai/api/v1/workspaces/12345",
         "organization": "https://elis.rossum.ai/api/v1/organizations/100",
         "queues": ["https://elis.rossum.ai/api/v1/queues/200"]
       }
     ]
   }

create_workspace
^^^^^^^^^^^^^^^^

Creates a new workspace in an organization.

**Parameters:**

- ``name`` (string, required): Workspace name
- ``organization_id`` (integer, required): Organization ID where the workspace should be created

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "My New Workspace",
     "url": "https://elis.rossum.ai/api/v1/workspaces/12345",
     "organization": "https://elis.rossum.ai/api/v1/organizations/100",
     "message": "Workspace 'My New Workspace' created successfully with ID 12345"
   }

delete_workspace
^^^^^^^^^^^^^^^^

Deletes a workspace. The workspace must be empty (no queues) before deletion.

**Parameters:**

- ``workspace_id`` (integer, required): Workspace ID to delete

**Returns:**

.. code-block:: json

   {
     "message": "Workspace 12345 deleted successfully"
   }

**Note:** This operation is only available in read-write mode.

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

Email Template Tools
^^^^^^^^^^^^^^^^^^^^

get_email_template
""""""""""""""""""

Retrieves details of a specific email template by its ID.

**Parameters:**

- ``email_template_id`` (integer, required): Email template ID

**Returns:**

.. code-block:: json

   {
     "id": 1500,
     "name": "Rejection Email",
     "url": "https://elis.rossum.ai/api/v1/email_templates/1500",
     "queue": "https://elis.rossum.ai/api/v1/queues/8199",
     "organization": "https://elis.rossum.ai/api/v1/organizations/1",
     "subject": "Document Rejected",
     "message": "<p>Your document has been rejected.</p>",
     "type": "rejection",
     "enabled": true,
     "automate": false,
     "triggers": [],
     "to": [{"type": "annotator", "value": ""}],
     "cc": [],
     "bcc": []
   }

**Example usage:**

.. code-block:: python

   # Get email template details
   template = get_email_template(email_template_id=1500)

list_email_templates
""""""""""""""""""""

Lists all email templates with optional filters. Email templates define automated or
manual email responses sent from Rossum queues.

**Parameters:**

- ``queue_id`` (integer, optional): Filter by queue ID
- ``type`` (string, optional): Filter by template type ('rejection', 'rejection_default',
  'email_with_no_processable_attachments', 'custom')
- ``name`` (string, optional): Filter by template name
- ``first_n`` (integer, optional): Limit results to first N templates

**Returns:**

.. code-block:: json

   {
     "count": 2,
     "results": [
       {
         "id": 1500,
         "name": "Rejection Email",
         "type": "rejection",
         "queue": "https://elis.rossum.ai/api/v1/queues/8199",
         "automate": false
       },
       {
         "id": 1501,
         "name": "No Attachments Notification",
         "type": "email_with_no_processable_attachments",
         "queue": "https://elis.rossum.ai/api/v1/queues/8199",
         "automate": true
       }
     ]
   }

**Example usage:**

.. code-block:: python

   # List all email templates
   all_templates = list_email_templates()

   # List email templates for a specific queue
   queue_templates = list_email_templates(queue_id=8199)

   # List rejection templates
   rejection_templates = list_email_templates(type="rejection")

   # List first 5 templates
   first_templates = list_email_templates(first_n=5)

create_email_template
"""""""""""""""""""""

Creates a new email template. Templates can be automated to send emails automatically
on specific triggers, or manual for user-initiated sending.

**Parameters:**

- ``name`` (string, required): Name of the email template
- ``queue`` (string, required): URL of the queue to associate with
- ``subject`` (string, required): Email subject line
- ``message`` (string, required): Email body (HTML supported)
- ``type`` (string, optional): Template type - 'rejection', 'rejection_default',
  'email_with_no_processable_attachments', 'custom' (default: 'custom')
- ``automate`` (boolean, optional): If true, email is sent automatically on trigger (default: false)
- ``to`` (array, optional): List of recipient objects with 'type' and 'value' keys
- ``cc`` (array, optional): List of CC recipient objects
- ``bcc`` (array, optional): List of BCC recipient objects
- ``triggers`` (array, optional): List of trigger URLs

**Recipient object types:**

- ``{"type": "annotator", "value": ""}`` - Send to the document annotator
- ``{"type": "constant", "value": "email@example.com"}`` - Send to a fixed email address
- ``{"type": "datapoint", "value": "email_field_id"}`` - Send to email from a datapoint field

**Returns:**

.. code-block:: json

   {
     "id": 1502,
     "name": "Custom Notification",
     "url": "https://elis.rossum.ai/api/v1/email_templates/1502",
     "queue": "https://elis.rossum.ai/api/v1/queues/8199",
     "subject": "Document Processed",
     "message": "<p>Your document has been processed.</p>",
     "type": "custom",
     "automate": true,
     "to": [{"type": "constant", "value": "notifications@example.com"}]
   }

**Example usage:**

.. code-block:: python

   # Create a simple custom email template
   template = create_email_template(
       name="Processing Complete",
       queue="https://elis.rossum.ai/api/v1/queues/8199",
       subject="Document Processing Complete",
       message="<p>Your document has been successfully processed.</p>"
   )

   # Create an automated rejection template
   template = create_email_template(
       name="Auto Rejection",
       queue="https://elis.rossum.ai/api/v1/queues/8199",
       subject="Document Rejected",
       message="<p>Your document could not be processed.</p>",
       type="rejection",
       automate=True,
       to=[{"type": "annotator", "value": ""}]
   )

   # Create template with multiple recipients
   template = create_email_template(
       name="Team Notification",
       queue="https://elis.rossum.ai/api/v1/queues/8199",
       subject="New Document",
       message="<p>A new document has arrived.</p>",
       to=[{"type": "constant", "value": "team@example.com"}],
       cc=[{"type": "datapoint", "value": "sender_email"}]
   )

Agent Tools
-----------

The ``rossum_agent`` package provides additional tools beyond the MCP server.

File System Tools
^^^^^^^^^^^^^^^^^

write_file
""""""""""

Write content to a file in the agent's output directory.

Use this tool to save analysis results, export data, or create reports.
Files are saved to a session-specific directory that can be shared with the user.

**Parameters:**

- ``filename`` (string, required): The name of the file to write (e.g., 'report.md', 'analysis.json')
- ``content`` (string, required): The content to write to the file

**Returns:**

.. code-block:: json

   {
     "status": "success",
     "message": "Successfully wrote 1234 characters to report.md",
     "path": "/path/to/outputs/report.md"
   }

Knowledge Base Tools
^^^^^^^^^^^^^^^^^^^^

search_knowledge_base
"""""""""""""""""""""

Search the Rossum Knowledge Base for documentation about extensions, hooks, and configurations.

Use this tool to find information about Rossum features, troubleshoot errors,
and understand extension configurations. The search is performed against
https://knowledge-base.rossum.ai/docs and results are analyzed by Claude Opus.

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

Hook Debugging Tools
^^^^^^^^^^^^^^^^^^^^

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

.. code-block:: json

   {
     "status": "success",
     "result": {"status": "ok", "document_id": 12345},
     "stdout": "Debug: Processing annotation\nDocument ID: 12345\n",
     "stderr": "",
     "exception": null,
     "elapsed_ms": 5.123
   }

**Sandbox Environment:**

- Available modules: ``collections``, ``datetime``, ``decimal``, ``functools``, ``itertools``, ``json``, ``math``, ``re``, ``string``
- No imports or external I/O allowed
- Limited builtins (safe subset for data manipulation)

debug_hook
""""""""""

Debug a Rossum hook using an Opus sub-agent for expert analysis. This is the PRIMARY tool
for debugging Python function hooks.

Simply pass the hook ID and annotation ID, and the Opus sub-agent will:

1. Fetch hook code and annotation data via MCP tools
2. Execute and analyze errors with Claude Opus for deep reasoning
3. Iteratively fix and verify the code works
4. Return detailed analysis with working code

**Parameters:**

- ``hook_id`` (string, required): The hook ID (from get_hook or hook URL). The sub-agent will fetch the code.
- ``annotation_id`` (string, required): The annotation ID to use for testing. The sub-agent will fetch the data.
- ``schema_id`` (string, optional): Optional schema ID if schema context is needed.

**Returns:**

.. code-block:: json

   {
     "hook_id": "12345",
     "annotation_id": "67890",
     "analysis": "## What the hook does\n\nThis hook validates...\n\n## Issues Found\n\n1. KeyError...\n\n## Fixed Code\n\n```python\n...\n```",
     "elapsed_ms": 2500.0
   }

**Features:**

- **Opus-powered analysis**: Uses Claude Opus 4 for deep reasoning about hook behavior
- **Automatic data fetching**: Fetches hook code and annotation data automatically
- **Iterative debugging**: Continues fixing until the code works
- **Fix suggestions**: Provides corrected code snippets you can use directly

**Example usage:**

.. code-block:: python

   # Simply pass the IDs - the sub-agent fetches everything
   result = debug_hook(hook_id="12345", annotation_id="67890")
   print(result["analysis"])

Multi-Environment Tools
^^^^^^^^^^^^^^^^^^^^^^^

spawn_mcp_connection
""""""""""""""""""""

Spawn a new MCP connection to a different Rossum environment.

Use this when you need to make changes to a different Rossum environment than the one
the agent was initialized with. For example, when deploying changes from source to target.

**Parameters:**

- ``connection_id`` (string, required): A unique identifier for this connection (e.g., 'target', 'sandbox')
- ``api_token`` (string, required): API token for the target environment
- ``api_base_url`` (string, required): API base URL for the target environment
- ``mcp_mode`` (string, optional): "read-only" or "read-write" (default: "read-write")

**Returns:**

Success message with list of available tools on the spawned connection.

call_on_connection
""""""""""""""""""

Call a tool on a spawned MCP connection.

Use this to execute MCP tools on a connection that was previously spawned with ``spawn_mcp_connection``.

**Parameters:**

- ``connection_id`` (string, required): The identifier of the spawned connection
- ``tool_name`` (string, required): The name of the MCP tool to call
- ``arguments`` (string, required): JSON string of arguments to pass to the tool

**Returns:**

The result of the tool call as a JSON string.

close_connection
""""""""""""""""

Close a spawned MCP connection.

**Parameters:**

- ``connection_id`` (string, required): The connection to close

**Returns:**

Success or error message.

Skills Tools
^^^^^^^^^^^^

load_skill
""""""""""

Load a specialized skill that provides domain-specific instructions and workflows.

Use this tool when you recognize that a task matches one of the available skills.
The skill will provide detailed instructions, workflows, and context for the task.

**Parameters:**

- ``name`` (string, required): The name of the skill to load (e.g., "rossum-deployment", "hook-debugging")

**Returns:**

.. code-block:: json

   {
     "status": "success",
     "skill_name": "rossum-deployment",
     "instructions": "## Rossum Deployment Workflow\n\n..."
   }

Agent Deployment Tools
^^^^^^^^^^^^^^^^^^^^^^

The agent includes deployment tools that wrap the ``rossum_deploy`` package for use within agent conversations.

deploy_pull
"""""""""""

Pull Rossum configuration objects from an organization to local files.

**Parameters:**

- ``org_id`` (int, required): Organization ID to pull from
- ``workspace_path`` (string, optional): Path to workspace directory
- ``api_base_url`` (string, optional): API base URL for target environment
- ``token`` (string, optional): API token for target environment

deploy_diff
"""""""""""

Compare local workspace files with remote Rossum configuration.

**Parameters:**

- ``workspace_path`` (string, optional): Path to workspace directory

deploy_push
"""""""""""

Push local changes to Rossum.

**Parameters:**

- ``dry_run`` (bool, optional): Only show what would be pushed
- ``force`` (bool, optional): Push even if there are conflicts
- ``workspace_path`` (string, optional): Path to workspace directory

deploy_copy_org
"""""""""""""""

Copy all objects from source organization to target organization.

**Parameters:**

- ``source_org_id`` (int, required): Source organization ID
- ``target_org_id`` (int, required): Target organization ID
- ``target_api_base`` (string, optional): Target API base URL
- ``target_token`` (string, optional): Target API token
- ``workspace_path`` (string, optional): Path to workspace directory

deploy_copy_workspace
"""""""""""""""""""""

Copy a single workspace and all its objects to target organization.

**Parameters:**

- ``source_workspace_id`` (int, required): Source workspace ID
- ``target_org_id`` (int, required): Target organization ID
- ``target_api_base`` (string, optional): Target API base URL
- ``target_token`` (string, optional): Target API token
- ``workspace_path`` (string, optional): Path to workspace directory

deploy_compare_workspaces
"""""""""""""""""""""""""

Compare two local workspaces to see differences between source and target.

**Parameters:**

- ``source_workspace_path`` (string, required): Path to source workspace
- ``target_workspace_path`` (string, required): Path to target workspace
- ``id_mapping_path`` (string, optional): Path to ID mapping JSON from copy operations

deploy_to_org
"""""""""""""

Deploy local configuration changes to a target organization.

**Parameters:**

- ``target_org_id`` (int, required): Target organization ID
- ``target_api_base`` (string, optional): Target API base URL
- ``target_token`` (string, optional): Target API token
- ``dry_run`` (bool, optional): Only show what would be deployed
- ``workspace_path`` (string, optional): Path to workspace directory

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
