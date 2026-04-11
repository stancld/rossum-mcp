Sub-Agents
==========

Opus-powered components that handle complex iterative tasks requiring deep reasoning and tool use loops.

Elis API Documentation
----------------------

Invoked via ``search_elis_docs``. Searches the Rossum API OpenAPI specification for endpoint details, schemas, and usage examples.

- Queries OpenAPI spec using jq (``elis_openapi_jq``)
- Free-text search across descriptions and field names (``elis_openapi_grep``)
- Opus analyzes results and synthesizes actionable responses
- Caches OpenAPI spec locally with 24-hour TTL

**Usage:**

.. code-block:: python

   search_elis_docs(query="How do I create an annotation via API?")

**Direct search tools** (without sub-agent overhead):

.. code-block:: python

   elis_openapi_jq(jq_query='.paths | keys | map(select(contains("queue")))')
   elis_openapi_grep(pattern="pagination")

Knowledge Base Search
---------------------

Invoked via ``search_knowledge_base``. Ranks pre-scraped KB articles locally first, falls back to Opus sub-agent only for ambiguous queries.

- Deterministically ranks articles by slug, title, and content matches
- Returns structured JSON with ranked candidates on high-confidence lookups
- Falls back to Opus only for genuinely ambiguous queries
- Articles cached locally with 24-hour TTL from S3-hosted JSON

**Usage:**

.. code-block:: python

   search_knowledge_base(
       query="document splitting extension",
       user_query="How do I configure document splitting for invoice processing?"
   )

**Direct search tools:**

.. code-block:: python

   kb_grep(pattern="document splitting")
   kb_get_article(slug="document-splitting-extension")

Schema Patching Sub-Agent
-------------------------

Handles complex multi-step schema modifications using ``patch_schema`` in a tool use loop. Invoked internally when schema changes require iterative reasoning.
