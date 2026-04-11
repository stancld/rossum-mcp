Skills
======

Domain-specific instruction sets loaded on demand via ``load_skill``. Skills provide workflows, code patterns, and context for specific Rossum tasks.

Loading a Skill
---------------

.. code-block:: python

   load_skill(name="schema-patching")

Returns JSON with skill name and instructions injected into the agent's context.

Available Skills
----------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Skill
     - Purpose
   * - ``schema-patching``
     - Add, update, or remove individual schema fields
   * - ``python-execution``
     - Constrained Python snippets, schema export of bulky structured outputs
   * - ``ui-settings``
     - Update queue UI settings (annotation list columns) without corrupting structure
   * - ``rules-and-actions``
     - Create validation rules with TxScript trigger conditions and actions
   * - ``formula-fields``
     - Create/configure formula fields with TxScript reference and common patterns
   * - ``reasoning-fields``
     - Create AI-powered reasoning fields with prompt/context configuration
   * - ``hooks``
     - Hook templates, token_owner, testing, debugging
   * - ``txscript``
     - TxScript language reference for formula fields, serverless functions, and rules
   * - ``lookup-fields``
     - Create lookup fields matching against Master Data Hub datasets
   * - ``master-data-hub``
     - Explore and query MDH datasets: list datasets, search entries, debug matching
   * - ``document-testing``
     - Generate mock PDFs, upload to queues, verify extraction, test hooks end-to-end
   * - ``automation-setup``
     - Analyze automation stats, run projections, configure per-field thresholds
   * - ``customer-email``
     - Draft customer-facing emails summarizing investigation findings or changes

Skill Workflows
---------------

Hooks
^^^^^

``search(query={"entity": "hook_template"})`` -> ``create_hook_from_template()`` or ``create_hook()`` -> ``test_hook()`` -> ``search(query={"entity": "hook_log", ...})``

Schema Patching
^^^^^^^^^^^^^^^

.. code-block:: python

   patch_schema(schema_id=123, operation="add", node_id="vendor_name",
                parent_id="header_section",
                node_data={"label": "Vendor Name", "type": "string", "category": "datapoint"})

Schema Pruning
^^^^^^^^^^^^^^

.. code-block:: python

   prune_schema_fields(schema_id=12345, fields_to_keep=["invoice_number", "invoice_date", "total_amount"])

UI Settings
^^^^^^^^^^^

Fetch current settings -> Modify only ``columns`` array -> Patch via ``update_queue``.

Document Testing
^^^^^^^^^^^^^^^^

``get(entity="schema", ...)`` -> extract fields -> ``generate_mock_pdf(fields=[...])`` -> ``upload_document`` -> poll with ``search`` -> ``get_annotation_content`` -> compare expected vs extracted.

Dynamic Tool Loading
--------------------

The agent uses dynamic tool loading to reduce initial context from ~8K to ~800 tokens. Tools are loaded on-demand based on task requirements.

1. **Discovery**: ``list_tool_categories`` returns all available categories with metadata
2. **Auto-loading**: On the first user message, keywords are matched against categories
3. **On-demand**: Agent loads additional tools via ``load_tool``

.. list-table::
   :header-rows: 1
   :widths: 20 50 30

   * - Category
     - Description
     - Keywords
   * - ``annotations``
     - Document processing: upload, retrieve, update, confirm
     - annotation, document, upload, extract, confirm
   * - ``queues``
     - Queue management: create, configure, list
     - queue, inbox, connector
   * - ``schemas``
     - Schema management: define, modify field structures
     - schema, field, datapoint, section
   * - ``engines``
     - AI engine management: extraction/splitting engines
     - engine, ai, extractor, splitter, training
   * - ``hooks``
     - Extensions/webhooks: automation hooks
     - hook, extension, webhook, automation
   * - ``email_templates``
     - Email templates: automated email responses
     - email, template, notification
   * - ``rules``
     - Validation rules: schema validation
     - rule, validation, constraint
   * - ``users``
     - User management: list users and roles
     - user, role, permission, token_owner
   * - ``workspaces``
     - Workspace management: organize queues
     - workspace, organization
