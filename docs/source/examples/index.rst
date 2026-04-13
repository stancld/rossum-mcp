Examples
========

Real-world use cases from simple document processing to complex multi-queue setups.

.. note::
   Complete example prompts and results are available in the ``examples/`` directory of the repository.

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Example
     - Requires
     - Description
   * - :ref:`Organization Setup <example-org-setup>`
     - Agent
     - Full customer setup: queues, schemas, validations, duplicate detection, email notifications
   * - :ref:`Hook Analysis <example-hook-analysis>`
     - Agent
     - Analyze and document all hooks on a queue
   * - :ref:`Splitting & Sorting Pipeline <example-splitting>`
     - Agent
     - Document splitting with training queues, splitter engine, and automated routing
   * - :ref:`Queue with Knowledge Warmup <example-warmup>`
     - Agent
     - Create queue, warm up with training documents, test automation performance

.. _example-org-setup:

Organization Setup
------------------

Set up a complete customer organization from a single conversational prompt:

.. code-block:: text

   1. Create two new queues: Invoices and Credit Notes
   2. Update schemas (Invoices with 15 fields including line items, Credit Notes as-is)
   3. Add computed field "Net Terms" (Due Date - Issue Date)
   4. Implement duplicate document detection on Document ID
   5. Add business validations: total amount cap, line items sum check, quantity x unit price
   6. Add email notification on status change to 'to_review'
   7. Update Invoice queue UI to display 8 key fields
   8. Verify by uploading a sample invoice twice (testing duplicate detection)

**Demonstrates:** Queue & schema setup, computed fields, duplicate detection, business validations, email notifications, UI configuration, end-to-end verification.

.. _example-hook-analysis:

Hook Analysis & Documentation
------------------------------

Automatically analyze and document all hooks on a queue:

.. code-block:: text

   Briefly explain the functionality of every hook based on description and/or code
   one by one for queue `2042843`. Store output in extension_explanation.md

**Demonstrates:** Automated analysis of existing automation to help teams understand configured workflows.

.. _example-splitting:

Splitting & Sorting Pipeline
-----------------------------

Set up a complete document splitting and sorting pipeline:

.. code-block:: text

   1. Create three training queues: Air Waybills, Certificates of Origin, Invoices
   2. Set up schemas with Document Type enum field
   3. Upload training documents and annotate with correct types
   4. Create three test queues with same schemas
   5. Create a splitter engine, configure training queues
   6. Create inbox queue with splitting UI
   7. Create Splitting & Sorting hook with routing to test queues
   8. Upload test documents to inbox

**Demonstrates:** Queue orchestration (7 queues), knowledge warmup (90 training documents), splitter engine, hook automation with intelligent document routing.

.. _example-warmup:

Queue with Knowledge Warmup
----------------------------

Create a queue, warm it up, and test automation:

.. code-block:: text

   1. Create a new queue matching queue 3904204
   2. Set up same schema, update thresholds (>90% = automated)
   3. Copy knowledge from reference queue
   4. Upload training documents
   5. Wait for processing, return automation rate

**Result:**

.. code-block:: json

   {
     "queue_name": "MCP Air Waybills",
     "total_documents": 30,
     "exported_documents": 26,
     "automation_rate_percent": 86.7
   }

Achieves **86.7% automation rate** from just 30 training documents.
