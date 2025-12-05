from __future__ import annotations

SETUP_QUEUE_PROMPT = """1. Create a new queue in the same namespace as queue `3947889`.
2. Set up the same schema field as queue `3947889`.
3. Update schema so that everything with confidence > 90% will be automated.
4. Rename the queue to: MCP Air Waybills (Regression test)
5. Copy the queue knowledge from `3947889`.
6. Return the queue status to check the queue status.
7. Upload all documents from `examples/data/splitting_and_sorting/knowledge/air_waybill` to the new queue.
8. Wait until all annotations are processed.
9. Finally, return queue URL and an automation rate (exported documents)."""

SORTING_WARMUP_PROMPT = """1. Create three new queues in workspace `1777693` - Air Waybills (Regression test), Certificates of Origin (Regression test), Invoices (Regression test).
2. Set up the schema with a single enum field on each queue with a name Document type (`document_type`).
3. Upload documents from folders air_waybill, certificate_of_origin, invoice in `examples/data/splitting_and_sorting/knowledge` to corresponding queues.
4. Annotate all uploaded documents with a correct Document type, and confirm the annotation.
    - Beware document types are air_waybill, invoice and certificate_of_origin (lower-case, underscores).
5. Create a new engine in organization `1`, with type = 'extractor'.
6. Configure engine training queues to be - Air Waybills (Regression test), Certificates of Origin (Regression test), Invoices (Regression test).
    - DO NOT copy knowledge.
    - Update Engine object.
7. Create a new schema with a single enum field `Document type`.
8. Create a new queue with the created engine and schema in the same workspace called: Inbox (Regression test).
9. Upload 10 documents from each folder air_waybill, certificate_of_origin, invoice in `examples/data/splitting_and_sorting/knowledge` to inbox queue.
10. Based on the file names and predicted values, generate a pie plot with correct/wrong for each document type."""

DATA_INSIGHT_PROMPT = """1. Upload all invoices from `/Users/daniel.stancl/projects/rossum-mcp/examples/data` folder to Rossum to the queue 3901094.
    - Do not include documents from `knowledge` folder.
2. Once you send all annotations, wait for a few seconds.
3. Then, start checking annotation status. Once all are imported, return a list of all annotations_urls
4. Fetch the schema for the target queue.
5. Identify the schema field IDs for:
    - Line item description field
    - Line item total amount field
6. Retrieve all annotations in 'to_review' state from queue 3901094
7. For each document:
    - Extract all line items
    - Create a dictionary mapping {item_description: item_amount_total}
    - If multiple line items share the same description, sum their amounts
    - Print result for each document
8. Aggregate across all documents: sum amounts for each unique description
9. Return the final dictionary: {description: total_amount_across_all_docs}
10. Using the retrieved data, generate bar plot displaying revenue by services. Sort it in descending order. Store it interactive `revenue.html`."""

EXPLAIN_EXTENSIONS_PROMPT = """Briefly explain the functionality of every hook based on description and/or code one by one for a queue `2042843`.

Store output in extestion_explanation.md
"""

EXPLAIN_RULES_AND_ACTIONS_PROMPT = """Briefly explain the functionality of all rules and their actions for a queue `2042844`.

Store output in extension_explanation.md
"""

SPLITTING_AND_SORTING_DEMO_PROMPT = """# A. Set up training queues
1. Create three new queues in workspace `1777693` - Air Waybills, Certificates of Origin, Invoices.
2. Set up the schema with a single enum field on each queue with a name Document type (`document_type`).
3. Upload documents from folders air_waybill, certificate_of_origin, invoice in `examples/data/splitting_and_sorting/knowledge` to corresponding queues.
4. Annotate all uploaded documents with a correct Document type, and confirm the annotation.
    - Beware document types are air_waybill, invoice and certificate_of_origin (lower-case, underscores).
    - IMPORTANT: After confirming all annotations, double check, that all are confirmed/exported, and fix those that are not.

# B. Set up test target queues
5. Create three new queues in workspace `1777693` - Air Waybills Test, Certificates of Origin Test, Invoices Test.
6. Set up the schema with a single enum field on each queue with a name Document type (`document_type`).

# C. Set up inbox queue
7. Create a new engine in organization `1`, with type = 'splitter'.
8. Configure engine training queues to be - Air Waybills, Certificates of Origin, Invoices.
    - DO NOT copy knowledge.
    - Update Engine object.
9. Create a new schema that will be the same as the schema from the queue `3885208`.
10. Create a new queue (with splitting UI feature flag!) with the created engine and schema in the same workspace called: Inbox.
11. Create a python function-based the **`Splitting & Sorting`** hook on the new inbox queue with this settings:
    **Functionality**: Automatically splits multi-document uploads into separate annotations and routes them to appropriate queues.
    Split documents should be routed to the following queues: Air Waybills Test, Certificates of Origin Test, Invoices Test

    **Trigger Events**:
    - annotation_content.initialize (suggests split to user)
    - annotation_content.confirm (performs actual split)
    - annotation_content.export (performs actual split)

    **How it works**: Python code

    **Settings**:
    - sorting_queues: Maps document types to target queue IDs for routing
    - max_blank_page_words: Threshold for blank page detection (pages with fewer words are considered blank)

# C. Run test
12. Upload 10 documents from `examples/data/splitting_and_sorting/testing` folder to inbox queues.
"""

CREATE_SAS_INBOX = """Setup Inbox for Splitting & Sorting in worksapce `1777693`.

# A. Setup
1. Create a new schema that will be the same as the schema from the queue `3885208`
2. Create a new queue (with splitting screen feature flag!) with the created schema and engine `37245` in the same workspace called: Inbox.
3. Create a python function-based the **`Splitting & Sorting`** hook on the new inbox queue with this configuration:
    **Functionality**: Automatically splits multi-document uploads into separate annotations and routes them to appropriate queues.
    Split documents should be routed to the following queues: 3947302, 3947303, 3947304.

    **Trigger Events**:
    - annotation_content.initialize (suggests split to user)
    - annotation_content.confirm (performs actual split)
    - annotation_content.export (performs actual split)

    **How it works**:
    1. Identifies document boundaries using the 'doc_split_subdocument' field values
    2. Detects and removes blank pages based on 'doc_split_blank_page' field and configurable word threshold
    3. Groups pages into subdocuments based on detected split points
    4. On initialize: Creates a "suggested edit" for user review showing proposed split
    5. On confirm/export: Actually splits the annotation into separate documents via the edit_pages API
    6. Can optionally route each split document to a different queue based on document type (configured via 'sorting_queues' setting)
    7. Filters out splits that contain only blank pages

    **Settings**:
    - sorting_queues: Maps document types to target queue IDs for routing. IMPORTANT: Must match document type enum values!
    - max_blank_page_words: Threshold for blank page detection (pages with fewer words are considered blank)

# B. Run test
4. Upload 10 documents from `examples/data/splitting_and_sorting/testing` folder to inbox queues.
"""


PROMPTS = {
    "setup_queue": SETUP_QUEUE_PROMPT,
    "sorting_warmup": SORTING_WARMUP_PROMPT,
    "data_insight": DATA_INSIGHT_PROMPT,
    "explain_extensions": EXPLAIN_EXTENSIONS_PROMPT,
    "explain_rules_and_actions": EXPLAIN_RULES_AND_ACTIONS_PROMPT,
    "sas_demo": SPLITTING_AND_SORTING_DEMO_PROMPT,
    "create_sas_inbox": CREATE_SAS_INBOX,
}
