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
   skills_and_subagents

.. toctree::
   :maxdepth: 2
   :caption: Examples:

   examples

Welcome to Rossum MCP Server
-----------------------------

**AI-powered Rossum orchestration: Document workflows conversationally, debug pipelines automatically, and configure automation through natural language.**

A Model Context Protocol (MCP) server and AI agent toolkit for the Rossum intelligent document processing platform. Transforms complex workflow setup, debugging, and configuration into natural language conversations.

Built with Python and the official `rossum-api <https://github.com/rossumai/rossum-api>`_.

Vision & Roadmap
----------------

This project enables three progressive levels of AI-powered Rossum orchestration:

1. **📝 Workflow Documentation** *(Current Focus)* - Conversationally document Rossum setups, analyze existing workflows, and generate comprehensive configuration reports through natural language prompts
2. **🔍 Automated Debugging** *(In Progress)* - Automatically diagnose pipeline issues, identify misconfigured hooks, detect schema problems, and suggest fixes through intelligent analysis
3. **🤖 Agentic Configuration** *(Planned)* - Fully autonomous setup and optimization of Rossum workflows - from queue creation to engine training to hook deployment - guided only by high-level business requirements

Features
--------

A compact, fully-typed tool surface — Pydantic models, ``Literal`` unions, and consolidated APIs built for agents:

**Unified Read Layer**

* **get** - Get entities by ID (single or batch). Supports ``include_related`` for enriched responses (queue→schema+engine+hooks, schema→queues+rules, hook→queues+events)
* **search** - Search/list entities with typed, entity-specific filters. Supports: queue, schema, hook, engine, rule, user, workspace, email_template, organization_group, annotation, relation, document_relation, hook_log, hook_template, user_role, queue_template_name

**Delete Layer**

* **delete** - Unified delete for any supported entity by ID. Supported entities: ``queue``, ``schema``, ``hook``, ``rule``, ``workspace``, ``annotation``

**Document Processing**

* **upload_document** - Upload documents for AI extraction
* **get_annotation_content** - Fetch annotation extracted content to a local JSON file
* **start_annotation** - Start annotation for field updates
* **bulk_update_annotation_fields** - Update field values with JSON Patch
* **confirm_annotation** - Confirm and finalize annotations
* **copy_annotations** - Copy annotations to another queue

**Queue Management**

* **create_queue_from_template** - Create queues from predefined templates (EU/US/UK/CZ/CN)
* **update_queue** - Configure automation thresholds

**Schema Management**

* **patch_schema** - Add, update, or remove individual schema nodes
* **get_schema_tree_structure** - Get lightweight tree structure of schema
* **prune_schema_fields** - Remove multiple fields from schema at once

**Workspace Management**

* **create_workspace** - Create a new workspace

**User Management**

* **create_user** - Create a new user
* **update_user** - Update user properties

**Engine Management**

* **create_engine** - Create extraction or splitting engines
* **update_engine** - Configure learning and training queues
* **create_engine_field** - Define engine fields and link to schemas
* **get_engine_fields** - Retrieve engine fields for a specific engine or all fields

**Extensions (Hooks)**

* **create_hook** - Create webhooks or serverless function hooks
* **update_hook** - Update hook properties (name, queues, events, config, settings, active)
* **create_hook_from_template** - Create hooks from pre-built templates
* **test_hook** - Test a hook with sample payloads

**Rules & Actions**

* **create_rule** - Create business rules with trigger conditions and actions
* **patch_rule** - Partial update of business rules (PATCH)

**Email Templates**

* **create_email_template** - Create new email templates

**Tool Discovery**

* **list_tool_categories** - List available tool categories with descriptions and keywords
* **load_tool** - Dynamically load tools by name or category

**MCP Mode**

* **get_mcp_mode** - Get the current MCP operation mode (read-only or read-write)

**Deployment Toolkit**

The ``rossum_deploy`` package provides configuration deployment:

* Pull configurations from Rossum organizations to local files
* Diff local vs remote configurations
* Push changes back to Rossum (with dry-run support)
* Cross-organization deployment with ID mapping
* Workspace comparison for safe agent workflows

**AI Agent Toolkit**

The ``rossum_agent`` package provides additional capabilities:

* Constrained Python execution via ``execute_python`` with helper guidance loaded from skills and ``write_file(...)`` for large outputs
* Elis API OpenAPI search via jq queries and free-text grep with sub-agent analysis
* Knowledge Base search with Opus-powered sub-agent analysis
* Hook testing via native Rossum API endpoints
* Deployment tools for pull/push/diff of Rossum configurations across environments
* Multi-environment support with spawnable MCP connections
* Skills system for domain-specific workflows (deployment, TxScript, formula fields, reasoning fields)
* Mock PDF generation for end-to-end document extraction testing (``generate_mock_pdf``)
* Interactive user questions (free-text or multiple-choice) via ``ask_user_question`` tool
* Working memory with auto-spillover — large tool results (>30k chars) are saved to workspace files; agent queries them via ``run_jq`` or ``run_grep``
* File output for saving reports, documentation, and analysis results
* Integration with AI agent frameworks (Anthropic Claude via AWS Bedrock)
* REST API interface with slash commands for quick introspection (``/list-skills``, ``/list-mcp-tools``, etc.)
* See the :doc:`examples` section for complete workflows

**Deployment Tools**

The ``rossum_deploy`` package provides lightweight deployment capabilities:

* Pull/diff/push workflow for Rossum configurations
* Support for Workspace, Queue, Schema, Hook, and Inbox objects
* Conflict detection when both local and remote have changed
* Python-first API designed for agent integration
* Lightweight alternative to `deployment-manager (PRD2) <https://github.com/rossumai/deployment-manager>`_

Quick Start
-----------

**Prerequisites:** Python 3.12+, Rossum account with API credentials

.. code-block:: bash

   git clone https://github.com/stancld/rossum-agents.git
   cd rossum-mcp

   # Install both packages with all features
   uv sync --extra all --no-install-project

   # Set up environment variables
   export ROSSUM_API_TOKEN="your-api-token"
   export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
   export ROSSUM_MCP_MODE="read-write"  # Optional: "read-only" or "read-write" (default)

Run the MCP server:

.. code-block:: bash

   rossum-mcp

Run the AI agent:

.. code-block:: bash

   # CLI interface
   rossum-agent

   # Or run with Docker Compose
   docker-compose up rossum-agent

For detailed installation options, see :doc:`installation`

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
