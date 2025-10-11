Plotting Tool
=============

The ``plot_tools`` module demonstrates how to build downstream processing tools that visualize
data extracted from Rossum annotations. This example shows a complete implementation that can
serve as a template for building your own custom tools.

Overview
--------

This example demonstrates:

* Processing data retrieved via the Rossum API
* Aggregating annotation data for visualization
* Creating interactive and static charts
* Building a reusable tool for the smolagents framework

The plotting tool acts as a downstream processor that takes aggregated data and creates
visualizations. It can be used alongside the MCP server or independently with the Rossum SDK.

Quick Example
-------------

The plotting tool works as a downstream processor for data retrieved via the Rossum API:

.. code-block:: python

   import json
   from rossum_api import SyncRossumAPIClient
   from rossum_api.dtos import Token
   from plot_tools import plot_data

   # 1. Initialize Rossum client (same one used by MCP server)
   client = SyncRossumAPIClient(
       base_url="https://api.elis.rossum.ai/v1",
       credentials=Token(token="your-api-token")
   )

   # 2. Fetch annotations using SDK methods
   annotations = client.list_annotations(
       queue=12345,
       status='exported'
   )

   # 3. Aggregate data from annotations
   service_revenue = {}
   for ann_result in annotations['results']:
       annotation = client.retrieve_annotation(
           ann_result['id'],
           sideloads=['content']
       )
       # Process annotation content...
       for datapoint in annotation['content']:
           if datapoint['schema_id'] == 'service_category':
               category = datapoint['value']
               service_revenue[category] = service_revenue.get(category, 0)
           if datapoint['schema_id'] == 'total_amount':
               service_revenue[category] += float(datapoint['value'])

   # 4. Visualize the aggregated data
   result = plot_data(
       data_json=json.dumps(service_revenue),
       chart_type='bar',
       title='Revenue by Service Category',
       output_path='revenue.html'
   )

   print(f"Chart saved: {json.loads(result)['output_path']}")

Chart Types
-----------

The tool supports 6 chart types:

* ``bar`` - Vertical bar charts
* ``horizontal_bar`` - Horizontal bar charts (better for long labels)
* ``line`` - Line charts (time series, trends)
* ``pie`` - Pie charts (proportions)
* ``scatter`` - Scatter plots (correlations)
* ``heatmap`` - Heatmaps (2D matrix data)

Integration Pattern
-------------------

This example demonstrates a common pattern for building tools that process Rossum data:

.. code-block:: python

   import json
   from rossum_api import SyncRossumAPIClient
   from rossum_api.dtos import Token
   from plot_tools import plot_data

   # Step 1: Initialize client
   client = SyncRossumAPIClient(
       base_url="https://api.elis.rossum.ai/v1",
       credentials=Token(token="your-api-token")
   )

   # Step 2: Fetch data using SDK methods
   annotations = client.list_annotations(queue=12345, status='exported')

   # Step 3: Process/aggregate the retrieved data
   category_totals = {}
   for ann_result in annotations['results']:
       annotation = client.retrieve_annotation(
           ann_result['id'],
           sideloads=['content']
       )
       # Extract line items from annotation content
       for datapoint in annotation['content']:
           if datapoint['schema_id'] == 'line_items':
               for item in datapoint['children']:
                   category = item.get('item_category', 'Unknown')
                   amount = float(item.get('item_amount', 0))
                   category_totals[category] = category_totals.get(category, 0) + amount

   # Step 4: Visualize with the plotting tool
   result = plot_data(
       data_json=json.dumps(category_totals),
       chart_type='bar',
       title='Invoice Analysis',
       output_path='invoice_analysis.html'
   )

This pattern can be adapted for other downstream processing:

* Generating PDF reports
* Exporting to Excel/CSV
* Sending data to other systems (CRM, ERP, etc.)
* Running statistical analysis
* Building custom validation rules

Implementation Details
----------------------

The plotting tool is implemented as a smolagents-compatible tool (``@tool`` decorator),
making it easy to integrate with AI agents that use the Rossum MCP Server.

**File:** ``examples/python/plot_tools.py``

**Key features:**

* Returns JSON-formatted results for easy parsing
* Validates input data and provides clear error messages
* Supports both interactive (Plotly) and static (Matplotlib) output
* Smart defaults minimize required configuration

Running the Example
-------------------

To try the plotting example:

.. code-block:: bash

   cd examples/python
   pip install -r requirements.txt
   python quick_demo.py

This will generate sample charts demonstrating the various chart types and options.

API Reference
-------------

For detailed API documentation of the ``plot_data`` function, see:

.. autofunction:: examples.python.plot_tools.plot_data

For more information on the supported parameters, see ``examples/python/README_PLOTTING.md``.

See Also
--------

* :doc:`usage` - Using the core MCP tools
* :doc:`workflow` - MCP workflow patterns
* :doc:`api` - Complete MCP server API reference
