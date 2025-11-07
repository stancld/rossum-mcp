SETUP_QUEUE_PROMPT = """1. Create a new queue in the same namespace as queue `3904204`.
2. Set up the same schema field as queue `3904204`.
3. Update schema so that everything with confidence > 90% will be automated.
4. Rename the queue to: MCP Air Waybills
5. Copy the queue knowledge from `3904204`.
6. Return the queue status to check the queue status.
7. Upload all documents from `examples/data/splitting_and_sorting/knowledge/air_waybill` to the new queue.
8. Wait until all annotations are processed.
9. Finally, return queue URL and an automation rate (exported documents)."""

SORTING_WARMUP_PROMPT = """1. Create three new queues in workspace `1777693` - Air Waybills, Certificates of Origin, Invoices.
2. Set up the schema with a single enum field on each queue with a name Document type (`document_type`).
3. Upload documents from folders air_waybill, certificate_of_origin, invoice in `examples/data/splitting_and_sorting/knowledge` to corresponding queues.
4. Annotate all uploaded documents with a correct Document type, and confirm the annotation.
    - Beware document types are air_waybill, invoice and certificate_of_origin (lower-case, underscores).
5. Create a new engine in organization `1`, with type = 'extractor'.
6. Configure engine training queues to be - Air Waybills, Certificates of Origin, Invoices.
    - DO NOT copy knowledge.
    - Update Engine object.
7. Create a new schema with a single enum field `Document type`.
8. Create a new queue with the created engine and schema in the same workspace called: Inbox.
9. Upload documents from folders air_waybill, certificate_of_origin, invoice in `examples/data/splitting_and_sorting/knowledge` to inbox queues.
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

Return it as a dictionary: `hook name -> description`.

Store output in extestion_explanation.md
"""


PROMPTS = {
    "setup_queue": SETUP_QUEUE_PROMPT,
    "sorting_warmup": SORTING_WARMUP_PROMPT,
    "data_insight": DATA_INSIGHT_PROMPT,
    "explain_extensions": EXPLAIN_EXTENSIONS_PROMPT,
}
