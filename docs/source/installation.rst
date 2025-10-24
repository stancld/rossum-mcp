Installation
============

Prerequisites
-------------

* Python 3.10 or higher
* Rossum account with API credentials
* A Rossum queue ID

The repository contains two separate packages:

* **rossum-mcp**: MCP server for Rossum SDK interactions
* **rossum-agent**: AI agent with tools for data manipulation and visualization

Installation Methods
--------------------

Installing MCP Server Only
^^^^^^^^^^^^^^^^^^^^^^^^^^^

To install only the MCP server:

.. code-block:: bash

   git clone https://github.com/stancld/rossum-mcp.git
   cd rossum-mcp/rossum_mcp
   pip install -e .

With extras:

.. code-block:: bash

   pip install -e ".[all]"  # Install all extras (docs, tests)
   pip install -e ".[docs]"  # Install documentation dependencies
   pip install -e ".[tests]"  # Install testing dependencies

Installing Agent Only
^^^^^^^^^^^^^^^^^^^^^

To install only the agent package:

.. code-block:: bash

   git clone https://github.com/stancld/rossum-mcp.git
   cd rossum-mcp/rossum_agent
   pip install -e .

With extras:

.. code-block:: bash

   pip install -e ".[all]"  # Install all extras (streamlit, docs, tests)
   pip install -e ".[streamlit]"  # Install Streamlit UI
   pip install -e ".[tests]"  # Install testing dependencies

Installing Both Packages (Workspace)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For development work with both packages:

.. code-block:: bash

   git clone https://github.com/stancld/rossum-mcp.git
   cd rossum-mcp
   pip install -e ".[all]"

This installs both packages together with all dependencies.

From GitHub (Direct)
^^^^^^^^^^^^^^^^^^^^

Install directly from GitHub:

.. code-block:: bash

   # MCP server only
   pip install "git+https://github.com/stancld/rossum-mcp.git#subdirectory=rossum_mcp"

   # Agent only
   pip install "git+https://github.com/stancld/rossum-mcp.git#subdirectory=rossum_agent"

   # Both packages (workspace)
   pip install "git+https://github.com/stancld/rossum-mcp.git"

Environment Variables
---------------------

Set up the required environment variables:

.. code-block:: bash

   export ROSSUM_API_TOKEN="your-api-token"
   export ROSSUM_API_BASE_URL="https://api.elis.develop.r8.lol/v1"

Replace the base URL with your organization's base URL if different.
