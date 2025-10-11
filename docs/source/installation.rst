Installation
============

Prerequisites
-------------

* Python 3.10 or higher
* Rossum account with API credentials
* A Rossum queue ID

Installation Methods
--------------------

From GitHub
^^^^^^^^^^^

Install directly from GitHub:

.. code-block:: bash

   pip install git+https://github.com/stancld/rossum-mcp.git

With Documentation Support
^^^^^^^^^^^^^^^^^^^^^^^^^^^

To build and view the documentation, install with the ``docs`` extra:

.. code-block:: bash

   pip install "git+https://github.com/stancld/rossum-mcp.git#egg=rossum-mcp[docs]"

From Source (Development)
^^^^^^^^^^^^^^^^^^^^^^^^^^

For development work:

.. code-block:: bash

   git clone https://github.com/stancld/rossum-mcp.git
   cd rossum-mcp
   pip install -e ".[docs]"

Environment Variables
---------------------

Set up the required environment variables:

.. code-block:: bash

   export ROSSUM_API_TOKEN="your-api-token"
   export ROSSUM_API_BASE_URL="https://api.elis.develop.r8.lol/v1"

Replace the base URL with your organization's base URL if different.
