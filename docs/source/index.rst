Rossum Agents
=============

AI-powered tools for Rossum document processing.

.. grid:: 2
   :gutter: 3

   .. grid-item-card:: Rossum MCP Server
      :link: rossum-mcp/index
      :link-type: doc

      MCP server exposing 30+ typed tools for document processing,
      queue management, schema editing, and hook automation.

      **Language:** Python |  **Install:** ``uvx rossum-mcp``

   .. grid-item-card:: Rossum Agent
      :link: rossum-agent/index
      :link-type: doc

      AI agent with skills, sub-agents, deployment tools,
      and working memory. Built on Claude + AWS Bedrock.

      **Language:** Python |  **Install:** ``pip install rossum-agent``


.. toctree::
   :hidden:
   :caption: MCP Server

   rossum-mcp/index
   rossum-mcp/configuration
   rossum-mcp/tools

.. toctree::
   :hidden:
   :caption: AI Agent

   rossum-agent/index
   rossum-agent/configuration
   rossum-agent/skills
   rossum-agent/tools
   rossum-agent/subagents

.. toctree::
   :hidden:
   :caption: Examples

   examples/index
