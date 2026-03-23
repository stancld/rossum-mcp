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
     "name": "schema-patching"
   }

Returns skill instructions as JSON:

.. code-block:: json

   {
     "status": "success",
     "skill_name": "Schema Patching",
     "instructions": "# Schema Patching Skill\n\n**Goal**: Add, update, or remove individual schema fields..."
   }

Available Skills
^^^^^^^^^^^^^^^^

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
     - Create validation rules with TxScript trigger conditions and actions via ``create_rule``
   * - ``formula-fields``
     - Create/configure formula fields with TxScript reference, messaging functions, and common patterns
   * - ``reasoning-fields``
     - Create AI-powered reasoning fields with prompt/context configuration and instruction-writing guidance
   * - ``hooks``
     - Hook templates, token_owner, testing, debugging
   * - ``txscript``
     - TxScript language reference for formula fields, serverless functions, and rule trigger conditions
   * - ``lookup-fields``
     - Create lookup fields matching against Master Data Hub datasets
   * - ``master-data-hub``
     - Explore and query MDH datasets: list datasets, search entries, debug matching issues
   * - ``document-testing``
     - Generate mock PDFs, upload to queues, verify extraction, test hooks end-to-end
   * - ``automation-setup``
     - Analyze automation stats, run projections, configure per-field thresholds
   * - ``customer-email``
     - Draft professional customer-facing emails summarizing investigation findings, changes, or resolutions
   * - ``elasticsearch``
     - Query Elasticsearch indices for datapoint statistics and annotation analytics

Hooks Skill
""""""""""""

**Goal**: Create, configure, and test hooks — prefer Rossum Store templates over custom code.

Workflow: ``search(query={"entity": "hook_template"})`` → ``create_hook_from_template()`` or ``create_hook()`` → ``test_hook()`` → ``search(query={"entity": "hook_log", ...})``.

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

Python Execution Skill
""""""""""""""""""""""

**Goal**: Use constrained Python snippets for MCP result transformation, schema export/edit flows, and Rossum copilot helpers.

This skill is the canonical place for Python helper availability. Load it before using Python snippets for Rossum-specific work.

UI Settings Skill
"""""""""""""""""

**Goal**: Update queue UI settings (``settings.annotation_list_table.columns``) without corrupting structure.

Workflow: Fetch current settings → Modify only ``columns`` array → Patch via ``update_queue``.

Document Testing Skill
""""""""""""""""""""""

**Goal**: Test document processing end-to-end — generate a schema-aware mock PDF, upload it, verify extraction, optionally trigger hooks.

Workflow: ``get(entity="schema", entity_id=schema_id)`` → extract fields → ``generate_mock_pdf(fields=[...])`` → ``upload_document`` → poll ``search(query={"entity": "annotation", "queue_id": ..., "ordering": ["-created_at"], "first_n": 1})`` → ``get_annotation_content(annotation_id)`` → compare expected vs extracted values.

``generate_mock_pdf`` tool parameters:

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``fields``
     - ``list[dict]``
     - Schema field descriptors: ``[{id, label, type, rir_field_names?, options?}]``
   * - ``document_type``
     - ``str``
     - ``invoice``, ``purchase_order``, ``receipt``, ``delivery_note``, ``credit_note``
   * - ``line_item_count``
     - ``int``
     - Number of line item rows (default 3). Ignored when ``line_item_overrides`` is provided.
   * - ``overrides``
     - ``dict[str, str | int | float]``
     - Force specific field values: ``{field_id: value}``. Applied to header fields and as fallback for line items.
   * - ``line_item_overrides``
     - ``list[dict[str, str | int | float]]``
     - Per-row override dicts. Length determines row count. Missing fields use ``overrides`` fallback or random values.
   * - ``consistent_amounts``
     - ``bool``
     - Recalculate header amounts to match line item sums (default ``True``). Set to ``False`` for mismatch testing.
   * - ``consistent_line_items``
     - ``bool``
     - Derive unset row-level amounts so ``item_amount_total = item_quantity * item_rate`` and ``item_amount_total_base`` or ``item_total_base`` matches the total excluding tax, while preserving explicit overrides (default ``True``). Set to ``False`` for row-level mismatch testing.
   * - ``filename``
     - ``str``
     - Output filename (auto-generated if omitted)

Returns JSON:

.. code-block:: json

   {
     "status": "success",
     "file_path": "/path/to/mock.pdf",
     "expected_values": {"invoice_id": "INV-2026-00142", "date_issue": "2026-02-10"},
     "line_items": [{"item_description": "Office supplies", "item_amount_total": "150.00"}]
   }

Dynamic Tool Loading
--------------------

The agent uses dynamic tool loading to reduce initial context usage from ~8K to ~800 tokens. Instead of loading all MCP tools at startup, tools are loaded on-demand based on task requirements.

How It Works
^^^^^^^^^^^^

1. **Discovery**: The MCP server provides a ``list_tool_categories`` tool that returns all available categories with metadata
2. **Automatic Pre-loading**: On the first user message, keywords are matched against category keywords to pre-load relevant tools
3. **On-demand Loading**: The agent can explicitly load additional tools using ``load_tool``

Loading Tools
^^^^^^^^^^^^^

Use ``load_tool`` to load specific MCP tools by name:

.. code-block:: python

   # Load specific tools
   load_tool(tool_names=["get", "search"])

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


Slash Commands
--------------

Slash commands provide instant introspection into the agent's capabilities without consuming tokens or invoking the agent. Messages starting with ``/`` sent via the ``POST /api/v1/chats/{id}/messages`` endpoint are intercepted and return a direct response as an AI SDK UI Message Stream v1 stream.

Available Commands
^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Command
     - Description
   * - ``/list-commands``
     - List all available slash commands
   * - ``/list-commits``
     - List configuration commits made in the current chat (requires Redis)
   * - ``/list-skills``
     - List available agent skills with their slugs and goal descriptions
   * - ``/list-mcp-tools``
     - List MCP tools grouped by category from the cached catalog
   * - ``/list-agent-tools``
     - List built-in agent tools with descriptions

Discovery Endpoint
^^^^^^^^^^^^^^^^^^

Available commands can be fetched programmatically:

.. code-block:: bash

   GET /api/v1/commands

.. code-block:: json

   {
     "commands": [
       {"name": "/list-commands", "description": "List all available slash commands"},
       {"name": "/list-commits", "description": "List configuration commits made in this chat"},
       {"name": "/list-skills", "description": "List available agent skills"},
       {"name": "/list-mcp-tools", "description": "List MCP tools by category"},
       {"name": "/list-agent-tools", "description": "List built-in agent tools"}
     ]
   }

The TUI uses this endpoint to provide autocomplete suggestions when the user types ``/``.


Sub-Agents
----------

Sub-agents are Opus-powered components that handle complex iterative tasks requiring deep reasoning and tool use loops.

Elis API Documentation Sub-Agent
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Invoked via the ``search_elis_docs`` tool. Searches the Rossum API OpenAPI specification for endpoint details, schemas, and usage examples.

**Capabilities:**

- Queries OpenAPI spec using jq for structured lookups (``elis_openapi_jq``)
- Free-text search across spec descriptions and field names (``elis_openapi_grep``)
- Opus analyzes results and synthesizes actionable responses
- Caches OpenAPI spec locally with 24-hour TTL

**Usage:**

.. code-block:: python

   search_elis_docs(query="How do I create an annotation via API?")

Returns JSON with:

- Analysis of relevant API endpoints
- Request/response schemas
- Required fields and parameters
- Code examples where applicable

**When to use:**

- API questions: endpoints, HTTP methods, request bodies
- Schema definitions: field types, required properties, enums
- Programmatic integration: "How do I POST to /v1/queues?"

For extension setup guides and workflow tutorials, use ``search_knowledge_base`` instead.

Working Memory & File Tools
"""""""""""""""""""""""""""

Large tool results (>30k chars) are automatically saved to workspace files under ``{output_dir}/workspace/``. The agent receives a compact summary with item count, preview, and file path — then queries the full content on demand.

``write_file(filename, content)``
   Save content to the agent's output directory. Accepts string, dict, or list content.

   .. code-block:: python

      write_file(filename="report.md", content="# Analysis\n...")
      write_file(filename="data.json", content={"key": "value"})

General-Purpose Data Tools
""""""""""""""""""""""""""

Available for any JSON/text content — annotation data, logs, schema dumps, API responses. Both tools accept file paths, making them ideal for querying spilled workspace files.

``run_jq(jq_query, data)``
   Run a jq expression on a JSON string, file path, or parsed JSON (dict/list). Returns the jq output as a string (truncated at 50 000 chars).

   .. code-block:: python

      run_jq(jq_query='.[] | select(.status == "active")', data="/tmp/annotations.json")
      run_jq(jq_query='map(.id)', data='[{"id": 1}, {"id": 2}]')
      run_jq(jq_query='.[0].name', data=[{"name": "Alice"}, {"name": "Bob"}])

``run_grep(pattern, text, case_insensitive=True)``
   Regex search in multi-line text or a file path. Returns matching lines with line numbers (max 200 matches).

   .. code-block:: python

      run_grep(pattern="amount_total", text="/tmp/schema_dump.json")
      run_grep(pattern=r"error: \d+", text=log_output, case_insensitive=False)

Direct OpenAPI Search Tools
"""""""""""""""""""""""""""

The agent also exposes the underlying search tools directly for quick lookups without sub-agent overhead:

``elis_openapi_jq(jq_query)``
   Query the OpenAPI spec with jq. Returns JSON result.

   .. code-block:: python

      elis_openapi_jq(jq_query='.paths | keys | map(select(contains("queue")))')
      elis_openapi_jq(jq_query='.paths["/v1/queues/{id}"]')
      elis_openapi_jq(jq_query='.components.schemas.Queue')

``elis_openapi_grep(pattern, case_insensitive=True)``
   Free-text search across spec descriptions, summaries, operationIds, and field names. Supports regex.

   .. code-block:: python

      elis_openapi_grep(pattern="pagination")
      elis_openapi_grep(pattern="annotation_status")

Knowledge Base Search
^^^^^^^^^^^^^^^^^^^^^

Invoked via the ``search_knowledge_base`` tool. It ranks pre-scraped Knowledge Base articles locally first, then falls back to the sub-agent only when the query is ambiguous.

**Capabilities:**

- Deterministically ranks pre-scraped KB articles by slug, recovered title, and content matches
- Returns structured JSON with ranked candidates and the selected article on high-confidence lookups
- Falls back to Opus only for ambiguous queries that genuinely need multiple lookups
- Articles cached locally with 24-hour TTL from S3-hosted JSON

**Direct search tools** (available without sub-agent overhead):

``kb_grep(pattern, case_insensitive=True)``
   Regex search across article titles and content. Returns matching articles with snippets.

   .. code-block:: python

      kb_grep(pattern="document splitting")
      kb_grep(pattern="webhook|email_template")

``kb_get_article(slug)``
   Persist the full article JSON by slug and return a filesystem path for follow-up ``run_jq`` queries. Supports partial match.

   .. code-block:: python

      kb_get_article(slug="document-splitting-extension")
      kb_get_article(slug="webhook")

**Ambiguous-query fallback** (only when deterministic ranking is not decisive):

.. code-block:: python

   search_knowledge_base(
       query="document splitting extension",
       user_query="How do I configure document splitting for invoice processing?"
   )

Returns JSON with:

- Retrieval strategy (``direct_lookup`` or ``sub_agent_fallback``)
- Ranked candidate articles
- Selected article path whenever a concrete article is identified, for follow-up ``run_jq`` queries
- Token usage and tool searches when the sub-agent fallback runs

Lookup Fields Skill
^^^^^^^^^^^^^^^^^^^

Load with ``load_skill(name="lookup-fields")`` when configuring or debugging lookup fields.

Key workflow:

1. ``execute_python`` for matching config generation
2. ``execute_python`` for evaluation on real annotations — do not write to schema until this passes
3. ``patch_schema_with_subagent`` to apply it
4. ``execute_python`` for dataset inspection and refinement, then regenerate the matching config if needed

When ``execute_python`` produces bulky structured data during these flows, save it with ``write_file(...)`` instead of returning the full payload inline.

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

- **Model**: Claude Opus 4.6 via AWS Bedrock
- **Iteration limit**: 5-10 iterations depending on task complexity
- **Tool access**: MCP tools via helper functions
- **Progress reporting**: Real-time progress updates via callback system
- **Token tracking**: Input/output token usage reported per iteration

Sub-agents are designed to be autonomous—they fetch required data, iterate on solutions, and return verified results without requiring user intervention during execution.
