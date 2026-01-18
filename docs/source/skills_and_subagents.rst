Skills & Sub-Agents
===================

The Rossum Agent includes a skills system and Opus-powered sub-agents for domain-specific workflows and complex iterative tasks.

Skills
------

Skills are markdown files that provide domain-specific instructions and workflows to the agent. They are loaded on-demand via the ``load_skill`` tool and injected into the agent's context.

Loading Skills
^^^^^^^^^^^^^^

Use the ``load_skill`` tool when a task matches one of the available skills:

.. code-block:: json

   {
     "name": "rossum-deployment"
   }

Returns skill instructions as JSON:

.. code-block:: json

   {
     "status": "success",
     "skill_name": "Rossum Deployment",
     "instructions": "# Rossum Deployment Skill\n\n**Goal**: Deploy configuration changes safely..."
   }

Available Skills
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Skill
     - Purpose
   * - ``rossum-deployment``
     - Deploy configuration changes safely via sandbox with before/after diff
   * - ``hook-debugging``
     - Identify and fix hook issues using knowledge base and Opus sub-agent
   * - ``schema-patching``
     - Add, update, or remove individual schema fields
   * - ``schema-pruning``
     - Remove unwanted fields from schema in one call
   * - ``organization-setup``
     - Set up Rossum for new customers with correct document types and regional configurations
   * - ``ui-settings``
     - Update queue UI settings (annotation list columns) without corrupting structure

Rossum Deployment Skill
"""""""""""""""""""""""

**Goal**: Deploy configuration changes safely via sandbox with before/after diff.

Key workflow:

1. Copy workspace to sandbox (``deploy_copy_workspace``)
2. Pull BEFORE state (``deploy_pull``)
3. Modify sandbox via spawned connection (``call_on_connection``)
4. Pull AFTER state (``deploy_pull``)
5. Compare and show diff (``deploy_compare_workspaces``) - **wait for user approval**
6. Deploy to production (``deploy_to_org``)

**Critical rule**: Direct MCP calls modify production. Use ``call_on_connection("sandbox", ...)`` for sandbox modifications.

Hook Debugging Skill
""""""""""""""""""""

**Goal**: Identify and fix hook issues.

Tools:

- ``search_knowledge_base`` - **Use first** to find Rossum docs, extension configs, known issues
- ``debug_hook(hook_id, annotation_id)`` - Spawns Opus sub-agent for code analysis, returns verified fix

Schema Patching Skill
"""""""""""""""""""""

**Goal**: Add, update, or remove individual schema fields.

.. code-block:: python

   patch_schema_with_subagent(
       schema_id="12345",
       changes='[{"action": "add", "id": "invoice_number", "parent_section": "header_section", "type": "string", "label": "Invoice Number"}]'
   )

Schema Pruning Skill
""""""""""""""""""""

**Goal**: Remove unwanted fields from schema in one call.

.. code-block:: python

   prune_schema_fields(
       schema_id=12345,
       fields_to_keep=["invoice_number", "invoice_date", "total_amount"]
   )

Organization Setup Skill
""""""""""""""""""""""""

**Goal**: Set up Rossum for new customers with correct document types and regional configurations.

Use ``create_queue_from_template`` for new customer onboarding with regional templates (EU/US/UK/CZ/CN).

UI Settings Skill
"""""""""""""""""

**Goal**: Update queue UI settings (``settings.annotation_list_table.columns``) without corrupting structure.

Workflow: Fetch current settings → Modify only ``columns`` array → Patch via ``update_queue``.


Dynamic Tool Loading
--------------------

The agent uses dynamic tool loading to reduce initial context usage from ~8K to ~800 tokens. Instead of loading all MCP tools at startup, tools are loaded on-demand based on task requirements.

How It Works
^^^^^^^^^^^^

1. **Discovery**: The MCP server provides a ``list_tool_categories`` tool that returns all available categories with metadata
2. **Automatic Pre-loading**: On the first user message, keywords are matched against category keywords to pre-load relevant tools
3. **On-demand Loading**: The agent can explicitly load additional categories using ``load_tool_category``

Loading Tools
^^^^^^^^^^^^^

Use ``load_tool_category`` to load MCP tools from specific categories:

.. code-block:: python

   # Load single category
   load_tool_category(categories=["schemas"])

   # Load multiple categories
   load_tool_category(categories=["queues", "schemas", "engines"])

Available Categories
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 50 30

   * - Category
     - Description
     - Keywords (for auto-loading)
   * - ``annotations``
     - Document processing: upload, retrieve, update, confirm
     - annotation, document, upload, extract, confirm, review
   * - ``queues``
     - Queue management: create, configure, list
     - queue, inbox, connector
   * - ``schemas``
     - Schema management: define, modify field structures
     - schema, field, datapoint, section, multivalue, tuple
   * - ``engines``
     - AI engine management: extraction/splitting engines
     - engine, ai, extractor, splitter, training
   * - ``hooks``
     - Extensions/webhooks: automation hooks
     - hook, extension, webhook, automation, function, serverless
   * - ``email_templates``
     - Email templates: automated email responses
     - email, template, notification, rejection
   * - ``document_relations``
     - Document relations: export/einvoice links
     - document relation, export, einvoice
   * - ``relations``
     - Annotation relations: edit/attachment/duplicate links
     - relation, duplicate, attachment, edit
   * - ``rules``
     - Validation rules: schema validation
     - rule, validation, constraint
   * - ``users``
     - User management: list users and roles
     - user, role, permission, token_owner
   * - ``workspaces``
     - Workspace management: organize queues
     - workspace, organization

Automatic Pre-loading
^^^^^^^^^^^^^^^^^^^^^

When the user sends their first message, the agent scans for keywords and automatically loads matching categories. For example:

- User says "update the schema" → ``schemas`` category is pre-loaded
- User says "create a new hook" → ``hooks`` category is pre-loaded
- User says "list all queues" → ``queues`` category is pre-loaded

This ensures relevant tools are available without requiring explicit loading while keeping context usage minimal.


Sub-Agents
----------

Sub-agents are Opus-powered components that handle complex iterative tasks requiring deep reasoning and tool use loops.

Hook Debug Sub-Agent
^^^^^^^^^^^^^^^^^^^^

Invoked via the ``debug_hook`` tool. Provides iterative hook debugging with sandboxed code execution.

**Capabilities:**

- Fetches hook code and annotation data via MCP tools
- Executes code in sandboxed environment with restricted builtins
- Iteratively analyzes errors and fixes issues
- Searches Rossum Knowledge Base for documentation
- Returns verified, working code

**Available in sandbox:**

- Modules: ``collections``, ``datetime``, ``decimal``, ``functools``, ``itertools``, ``json``, ``math``, ``re``, ``string``
- Safe builtins: ``abs``, ``all``, ``any``, ``bool``, ``dict``, ``enumerate``, ``filter``, ``float``, ``int``, ``len``, ``list``, ``map``, ``max``, ``min``, ``range``, ``set``, ``sorted``, ``str``, ``sum``, ``tuple``, ``zip``, and common exceptions

**Usage:**

.. code-block:: python

   debug_hook(hook_id="12345", annotation_id="67890")

Returns JSON with:

- Hook ID and annotation ID
- Detailed analysis including:
  - What the hook does
  - All issues found
  - Root causes
  - Fixed, verified code
  - Successful execution result

Knowledge Base Sub-Agent
^^^^^^^^^^^^^^^^^^^^^^^^

Invoked via the ``search_knowledge_base`` tool. Searches Rossum documentation and analyzes results with Opus.

**Capabilities:**

- Searches ``knowledge-base.rossum.ai`` for documentation
- Fetches full page content via Jina Reader
- Analyzes results with Opus to extract relevant information
- Provides synthesized, actionable responses

**Usage:**

.. code-block:: python

   search_knowledge_base(
       query="document splitting extension",
       user_query="How do I configure document splitting for invoice processing?"
   )

Returns JSON with:

- Search status
- Query used
- Analyzed results from Opus
- Source URLs

Schema Patching Sub-Agent
^^^^^^^^^^^^^^^^^^^^^^^^^

Invoked via the ``patch_schema_with_subagent`` tool. Handles bulk schema modifications programmatically.

**Workflow:**

1. Fetches schema tree structure (lightweight view)
2. Fetches full schema content
3. Opus analyzes current vs requested fields
4. Programmatically filters to keep required fields and adds new ones
5. Single PUT to update schema

**Usage:**

.. code-block:: python

   patch_schema_with_subagent(
       schema_id="12345",
       changes='[{"action": "add", "id": "po_number", "parent_section": "basic_info_section", "type": "string", "label": "PO Number"}]'
   )

**Field specification:**

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Property
     - Required
     - Notes
   * - ``id``
     - Yes
     - Unique field identifier
   * - ``label``
     - Yes
     - Display name
   * - ``parent_section``
     - Yes
     - Section ID to add field to
   * - ``type``
     - Yes
     - ``string``, ``number``, ``date``, ``enum``
   * - ``table_id``
     - If table
     - Multivalue ID for table columns
   * - ``multiline``
     - No
     - ``true`` for multiline string fields
   * - ``options``
     - For enum
     - Array of enum options

Sub-Agent Architecture
^^^^^^^^^^^^^^^^^^^^^^

All sub-agents share common patterns:

- **Model**: Claude Opus 4.5 via AWS Bedrock
- **Iteration limit**: 5-10 iterations depending on task complexity
- **Tool access**: MCP tools via helper functions
- **Progress reporting**: Real-time progress updates via callback system
- **Token tracking**: Input/output token usage reported per iteration

Sub-agents are designed to be autonomous—they fetch required data, iterate on solutions, and return verified results without requiring user intervention during execution.
