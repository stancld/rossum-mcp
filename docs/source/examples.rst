Examples
========

This section demonstrates what you can accomplish with Rossum MCP Server and AI agent toolkit.
The examples show real-world use cases from simple document processing to complex multi-queue setups.

.. note::
   The complete example prompts and results are available in the `examples/` directory
   of the repository.

Real-World Use Cases
--------------------

Example 1: Aurora Splitting & Sorting Demo
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Set up a complete document splitting and sorting pipeline with training queues, splitter engine, automated hooks, and intelligent routing:

.. code-block:: text

   1. Create three new queues in workspace `1777693` - Air Waybills, Certificates of Origin, Invoices.
   2. Set up the schema with a single enum field on each queue with a name Document type (`document_type`).
   3. Upload documents from folders air_waybill, certificate_of_origin, invoice in `examples/data/splitting_and_sorting/knowledge` to corresponding queues.
   4. Annotate all uploaded documents with a correct Document type, and confirm the annotation.
       - Beware document types are air_waybill, invoice and certificate_of_origin (lower-case, underscores).
       - IMPORTANT: After confirming all annotations, double check, that all are confirmed/exported, and fix those that are not.
   5. Create three new queues in workspace `1777693` - Air Waybills Test, Certificates of Origin Test, Invoices Test.
   6. Set up the schema with a single enum field on each queue with a name Document type (`document_type`).
   7. Create a new engine in organization `1`, with type = 'splitter'.
   8. Configure engine training queues to be - Air Waybills, Certificates of Origin, Invoices.
       - DO NOT copy knowledge.
       - Update Engine object.
   9. Create a new schema that will be the same as the schema from the queue `3885208`.
   10. Create a new queue (with splitting UI feature flag!) with the created engine and schema in the same workspace called: Inbox.
   11. Create a python function-based the **`Splitting & Sorting`** hook on the new inbox queue with this settings:
       **Functionality**: Automatically splits multi-document uploads into separate annotations and routes them to appropriate queues.
       Split documents should be routed to the following queues: Air Waybills Test, Certificates of Origin Test, Invoices Test

       **Trigger Events**:
       - annotation_content.initialize (suggests split to user)
       - annotation_content.confirm (performs actual split)
       - annotation_content.export (performs actual split)

       **How it works**: Python code

       **Settings**:
       - sorting_queues: Maps document types to target queue IDs for routing
       - max_blank_page_words: Threshold for blank page detection (pages with fewer words are considered blank)
   12. Upload 10 documents from `examples/data/splitting_and_sorting/testing` folder to inbox queues.

**What This Demonstrates:**

- **Queue Orchestration**: Creates 7 queues (3 training + 3 test + 1 inbox) with consistent schemas
- **Knowledge Warmup**: Uploads and annotates 90 training documents to teach the engine
- **Splitter Engine**: Configures an AI engine to detect document boundaries and types
- **Hook Automation**: Sets up a sophisticated webhook that automatically:

  - Splits multi-document PDFs into individual annotations
  - Removes blank pages intelligently
  - Routes split documents to correct queues by type
  - Suggests splits on initialization and executes on confirmation

- **End-to-End Testing**: Validates the entire pipeline with test documents

This example showcases the agent's ability to orchestrate complex workflows involving multiple queues, engines, schemas, automated hooks with custom logic, and intelligent document routing - all from a single conversational prompt.

Example 2: Hook Analysis & Documentation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Automatically analyze and document all hooks/extensions configured on a queue:

.. code-block:: text

   Briefly explain the functionality of every hook based on description and/or code one by one for a queue `2042843`.

   Store output in extension_explanation.md

**What This Does:**

- Lists all hooks/extensions on the specified queue
- Analyzes each hook's description and code
- Generates clear, concise explanations of functionality
- Documents trigger events and settings
- Saves comprehensive documentation to a markdown file

This example shows how the agent can analyze existing automation to help teams understand their configured workflows.

Example 3: Queue Setup with Knowledge Warmup
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Create a new queue, warm it up with training documents, and test automation performance:

.. code-block:: text

   1. Create a new queue in the same namespace as queue `3904204`
   2. Set up the same schema field as queue `3904204`
   3. Update schema so that everything with confidence > 90% will be automated
   4. Rename the queue to: MCP Air Waybills
   5. Copy the queue knowledge from `3904204`
   6. Return the queue status to check the queue status
   7. Upload all documents from `examples/data/splitting_and_sorting/knowledge/air_waybill`
      to the new queue
   8. Wait until all annotations are processed
   9. Finally, return queue URL and an automation rate (exported documents)

**Result:**

.. code-block:: json

   {
     "queue_url": "https://api.elis.rossum.ai/v1/queues/3920572",
     "queue_id": 3920572,
     "queue_name": "MCP Air Waybills",
     "total_documents": 30,
     "exported_documents": 26,
     "to_review_documents": 4,
     "automation_rate_percent": 86.7
   }

The agent automatically creates the queue, uploads documents, monitors processing, and calculates
automation performance - achieving **86.7% automation rate** from just 30 training documents.

Building Your Own Agents
-------------------------

The examples follow a common pattern for building AI agents that process Rossum data:

1. **Fetch data** using the Rossum API (``get_annotation``, ``list_annotations``, etc.)
2. **Process/aggregate** the retrieved data according to your needs
3. **Output results** in your desired format (visualizations, reports, exports, etc.)

This pattern can be adapted for many agent use cases:

* **Reporting Agents**: Generate PDF or Excel reports from annotation data
* **Analytics Agents**: Perform statistical analysis on extracted data
* **Integration Agents**: Send data to other systems (CRM, ERP, databases)
* **Validation Agents**: Build custom validation rules for annotation data
* **Monitoring Agents**: Track processing metrics and SLA compliance

Example Pattern
^^^^^^^^^^^^^^^

Here's the general structure for building an extension:

.. code-block:: python

   import json
   from rossum_api import SyncRossumAPIClient
   from rossum_api.dtos import Token

   # 1. Initialize the Rossum client (same one used by MCP server)
   client = SyncRossumAPIClient(
       base_url="https://api.elis.rossum.ai/v1",
       credentials=Token(token="your-api-token")
   )

   # 2. Fetch data using SDK methods (mirrors MCP tools)
   annotations = client.list_annotations(
       queue=12345,
       status="exported"
   )

   # 3. Process the data
   processed_data = {}
   for ann_result in annotations['results']:
       annotation = client.retrieve_annotation(
           ann_result['id'],
           sideloads=['content']
       )
       # Your processing logic here
       # processed_data[key] = value

   # 4. Output results
   # - Save to file
   # - Generate visualization
   # - Send to another system
   # - etc.

Integration with AI Agents
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Rossum Agent is built with Anthropic Claude for intelligent document processing.
The agent provides seamless access to MCP tools and can be extended with custom tools
that share the ``rossum_api`` package.

Next Steps
----------

* Review the :doc:`usage` guide to understand the core MCP tools
* Check the :doc:`api` reference for detailed SDK documentation
