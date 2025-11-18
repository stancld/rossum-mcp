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
         "args": ["/path/to/rossum-mcp/rossum_mcp/server.py"],
         "env": {
           "ROSSUM_API_TOKEN": "your-api-token",
           "ROSSUM_API_BASE_URL": "https://api.elis.rossum.ai/v1",
           "ROSSUM_MCP_MODE": "read-write"
         }
       }
     }
   }

For read-only access (recommended for untrusted environments), use ``"ROSSUM_MCP_MODE": "read-only"``
to restrict access to read-only operations (GET/LIST only).

Running the AI Agent
--------------------

The ``rossum_agent`` package provides CLI and web interfaces:

.. code-block:: bash

   # CLI interface
   rossum-agent

   # Streamlit web UI
   streamlit run rossum_agent/app.py

   # Or run with Docker Compose
   docker-compose up rossum-agent

The agent includes file system tools, plotting capabilities, and Rossum integration.
See the :doc:`examples` section for complete workflows.

Using with Smolagents
---------------------

The Python implementation makes it easy to use with smolagents, as both use Python
and can share the ``rossum_api`` package:

.. code-block:: python

   from smolagents import ToolCallingAgent, ManagedAgent

   # Create a Rossum MCP agent
   rossum_agent = ManagedAgent(
       agent=ToolCallingAgent(tools=[]),
       name="rossum",
       description="Upload and process documents using Rossum API"
   )

   # Use the agent
   result = rossum_agent.run(
       "Upload the invoice.pdf to queue 12345 and wait for it to be processed"
   )

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
