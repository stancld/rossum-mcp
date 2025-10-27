Examples
========

This section demonstrates what you can accomplish with Rossum MCP Server and AI agent toolkit.
The examples show real-world use cases from simple document processing to complex multi-queue setups.

.. note::
   The complete example prompts and results are available in the `examples/` directory
   of the repository.

Real-World Use Cases
--------------------

Example 1: Bulk Processing & Visualization
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Process multiple invoices and generate revenue analysis charts through a single conversational prompt:

.. code-block:: text

   1. Upload all invoices from `/path/to/examples/data` folder to Rossum queue 3901094
      - Do not include documents from `knowledge` folder
   2. Once you send all annotations, wait for a few seconds
   3. Then, start checking annotation status. Once all are imported, return a list of all annotations_urls
   4. Fetch the schema for the target queue
   5. Identify the schema field IDs for:
      - Line item description field
      - Line item total amount field
   6. Retrieve all annotations in 'to_review' state from queue 3901094
   7. For each document:
      - Extract all line items
      - Create a dictionary mapping {item_description: item_amount_total}
      - If multiple line items share the same description, sum their amounts
      - Print result for each document
   8. Aggregate across all documents: sum amounts for each unique description
   9. Return the final dictionary: {description: total_amount_across_all_docs}
   10. Using the retrieved data, generate bar plot displaying revenue by services.
       Sort it in descending order. Store it interactive `revenue.html`.

**Result:** Automatically processes 30 invoices and generates an interactive visualization showing
revenue breakdown by service category.

See the `complete example <https://github.com/stancld/rossum-mcp/blob/master/examples/PROMPT.md>`_
for the full prompt and results.

Example 2: Queue Setup with Knowledge Warmup
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

Example 3: Multi-Queue Setup with Sorting Engine
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Set up multiple queues with training data, create a sorting engine, and test classification performance:

.. code-block:: text

   1. Create three new queues in workspace `1777693` - Air Waybills, Certificates of Origin, Invoices
   2. Set up the schema with a single enum field on each queue with a name Document type (`document_type`)
   3. Upload documents from folders air_waybill, certificate_of_origin, invoice in
      `examples/data/splitting_and_sorting/knowledge` to corresponding queues
   4. Annotate all uploaded documents with a correct Document type, and confirm the annotation
      - Beware document types are air_waybill, invoice and certificate_of_origin (lower-case, underscores)
   5. Create a new engine in organization `1`, with type = 'extractor'
   6. Configure engine training queues to be - Air Waybills, Certificates of Origin, Invoices
      - DO NOT copy knowledge
      - Update Engine object
   7. Create a new schema with a single enum field `Document type`
   8. Create a new queue with the created engine and schema in the same workspace called: Inbox
   9. Upload documents from folders air_waybill, certificate_of_origin, invoice in
      `examples/data/splitting_and_sorting/knowledge` to inbox queues
   10. Based on the file names and predicted values, generate a pie plot with correct/wrong
       for each document type

**Result:**

.. code-block:: text

   ✅ Step 10: Generated accuracy reports
     • Overall Accuracy: 100.0% (90/90)

     Accuracy by document type:
       • air_waybill: 100.0% (30/30)
       • certificate_of_origin: 100.0% (30/30)
       • invoice: 100.0% (30/30)

   📊 Generated Charts:
     • output/air_waybill_accuracy.html
     • output/certificate_of_origin_accuracy.html
     • output/invoice_accuracy.html
     • output/overall_accuracy_by_type.html

   ================================================================================
   🎉 ALL TASKS COMPLETED SUCCESSFULLY!
   ================================================================================

   📝 Key Findings:
     • The engine achieved 100% accuracy on all document types
     • All 90 test documents were correctly classified
     • The training data (88 confirmed annotations) was sufficient
     • No misclassifications occurred

The agent achieved **100% classification accuracy** across all document types.

Building Custom Tools
----------------------

.. toctree::
   :maxdepth: 1

   plotting

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

The Python implementation makes it easy to integrate with AI agent frameworks like
`smolagents <https://huggingface.co/docs/smolagents>`_. Both the MCP server and your
custom tools can share the ``rossum_api`` package:

.. code-block:: python

   from smolagents import ToolCallingAgent, ManagedAgent, tool

   # Define your custom tool
   @tool
   def my_custom_tool(annotation_id: int) -> str:
       """Process annotation data in a custom way."""
       # Use rossum_api client to fetch data
       # Process it
       # Return results
       return json.dumps({"status": "processed"})

   # Create agent with both MCP and custom tools
   agent = ToolCallingAgent(
       tools=[my_custom_tool],
       # MCP tools are available through managed agent
   )

Next Steps
----------

* Explore the :doc:`plotting` example to see a complete implementation
* Review the :doc:`usage` guide to understand the core MCP tools
* Check the :doc:`api` reference for detailed SDK documentation
