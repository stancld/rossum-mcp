Rossum Agent
=============

AI agent for Rossum document processing. Debug hooks, deploy configs, automate workflows -- all through natural language.

Built on Claude (via AWS Bedrock) with skills, sub-agents, working memory, and seamless MCP integration.

Quick Start
-----------

.. code-block:: bash

   pip install rossum-agent[api]

   export ROSSUM_API_TOKEN="your-token"
   export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
   export AWS_PROFILE="default"

   rossum-agent-api

Verify:

.. code-block:: bash

   curl http://localhost:8000/api/v1/health

Or run with Docker Compose:

.. code-block:: bash

   docker-compose up rossum-agent
