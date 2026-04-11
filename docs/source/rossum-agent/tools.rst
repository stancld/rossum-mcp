Agent Tools
===========

Built-in tools available to the agent beyond MCP tools.

Python Execution
----------------

execute_python
^^^^^^^^^^^^^^

Run constrained Python snippets in a sandboxed environment.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``code``
     - string, required
     - Python code. Allowed imports: collections, csv, datetime, fpdf, functools, io, itertools, json, math, operator, pathlib, re, statistics, string, textwrap, time. Assign final value to ``result``.
   * - ``operation_name``
     - string, optional
     - Short label for the execution intent

Built-in helpers: ``mcp(...)``, ``api_get(...)``, ``schema_content(...)``, ``write_file(...)``, ``json``, ``copilot`` namespace.

**Example:**

.. code-block:: python

   execute_python(
       code='result = {"total": sum([1, 2, 3])}',
       operation_name="quick calculation"
   )

File Tools
----------

write_file
^^^^^^^^^^

Save content to the agent's output directory.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``filename``
     - string, required
     - File name (e.g. ``report.md``, ``data.json``)
   * - ``content``
     - string, required
     - Content to write

Working Memory
--------------

Large tool results (>30k chars) are automatically saved to workspace files under ``{output_dir}/workspace/``. The agent receives a compact summary with item count, preview, and file path -- then queries the full content on demand using ``run_jq`` or ``run_grep``.

Data Tools
----------

run_jq
^^^^^^

Run a jq expression on JSON data (string, file path, or dict/list).

.. code-block:: python

   run_jq(jq_query='.[] | select(.status == "active")', data="/tmp/annotations.json")

run_grep
^^^^^^^^

Regex search in multi-line text or a file path. Returns matching lines with line numbers (max 200 matches).

.. code-block:: python

   run_grep(pattern="amount_total", text="/tmp/schema_dump.json")

Mock PDF Generation
-------------------

generate_mock_pdf
^^^^^^^^^^^^^^^^^

Generate a mock PDF with realistic values matching schema fields for end-to-end testing.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``fields``
     - list[dict], required
     - Schema field descriptors: ``[{id, label, type, rir_field_names?, options?}]``
   * - ``document_type``
     - string, optional
     - ``invoice``, ``purchase_order``, ``receipt``, ``delivery_note``, ``credit_note``
   * - ``line_item_count``
     - int, optional
     - Number of line item rows (default: 3)
   * - ``overrides``
     - dict, optional
     - Force specific field values: ``{field_id: value}``
   * - ``line_item_overrides``
     - list[dict], optional
     - Per-row override dicts (length determines row count)
   * - ``consistent_amounts``
     - bool, optional
     - Recalculate header amounts to match line item sums (default: true)
   * - ``consistent_line_items``
     - bool, optional
     - Derive row-level amounts for consistency (default: true)
   * - ``filename``
     - string, optional
     - Output filename (auto-generated if omitted)

User Interaction
----------------

ask_user_question
^^^^^^^^^^^^^^^^^

Ask structured questions mid-execution. Supports free-text and multiple-choice.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``question``
     - string
     - The question text
   * - ``options``
     - list[dict], optional
     - Choices with ``value``, ``label``, and optional ``description``. Omit for free-text.
   * - ``multi_select``
     - bool, optional
     - Allow multiple selections (default: false)
   * - ``questions``
     - list[dict], optional
     - Array of question objects for batch questions

Knowledge Base Tools
--------------------

kb_grep
^^^^^^^

Search Knowledge Base article titles and content by keyword or regex.

.. code-block:: python

   kb_grep(pattern="document splitting")

kb_get_article
^^^^^^^^^^^^^^

Persist a KB article by slug for follow-up ``run_jq`` queries.

.. code-block:: python

   kb_get_article(slug="document-splitting-extension")

Hook Testing
------------

test_hook
^^^^^^^^^

Tests a hook via the native Rossum API endpoint. See :doc:`/rossum-mcp/tools` for full parameters.

Skills Tools
------------

load_skill
^^^^^^^^^^

Load a specialized skill. See :doc:`skills` for the full list.

.. code-block:: python

   load_skill(name="schema-patching")
