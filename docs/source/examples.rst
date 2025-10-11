Examples
========

This section demonstrates how to build additional tools and integrations that work alongside
the Rossum MCP Server. These examples show patterns for extending MCP functionality and
building downstream processors for data retrieved via MCP tools.

.. note::
   The examples in this section are not part of the core Rossum MCP Server. They demonstrate
   how to build applications and tools that consume data from the MCP server.

Available Examples
------------------

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
