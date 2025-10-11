Rossum MCP Server Documentation
=================================

.. toctree::
   :maxdepth: 2
   :caption: Getting Started:

   installation
   usage
   workflow

.. toctree::
   :maxdepth: 2
   :caption: Reference:

   api
   mcp_reference

.. toctree::
   :maxdepth: 2
   :caption: Examples:

   examples

Welcome to Rossum MCP Server
-----------------------------

A Model Context Protocol (MCP) server that provides tools for uploading documents
and retrieving annotations using the Rossum API. Built with Python and the official
`rossum-sdk <https://github.com/rossumai/rossum-sdk>`_.

Features
--------

**MCP Tools:**

* **upload_document**: Upload a document to Rossum for processing
* **get_annotation**: Retrieve annotation data for a previously uploaded document
* **list_annotations**: List all annotations for a queue with optional filtering
* **get_queue**: Retrieve queue details including schema_id
* **get_schema**: Retrieve schema details and content
* **get_queue_schema**: Retrieve complete schema for a queue in a single call

**Examples and Extensions**

The documentation includes examples demonstrating how to build downstream tools that work with Rossum data:

* Plotting tool for data visualization (bar, line, pie, scatter, heatmap charts)
* Integration patterns for AI agents (smolagents)
* Templates for building custom processing tools
* See the :doc:`examples` section for details

Quick Start
-----------

Install the package with documentation dependencies:

.. code-block:: bash

   pip install -e ".[docs]"

Run the MCP server:

.. code-block:: bash

   python -m rossum_mcp.server

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
