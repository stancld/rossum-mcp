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
         "args": ["/path/to/rossum-mcp/server.py"],
         "env": {
           "ROSSUM_API_TOKEN": "your-api-token",
           "ROSSUM_API_BASE_URL": "https://api.elis.develop.r8.lol/v1"
         }
       }
     }
   }

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
