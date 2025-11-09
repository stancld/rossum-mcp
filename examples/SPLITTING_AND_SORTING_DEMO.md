# Showcase splitting and sorting demo (INTERNAL)

*This is a stretch task showcasing a various functionality of Rossum Agent completing S&S warm up, hook setup and demo.*

# A. Set up training queues
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

# D. Run test
12. Upload 10 documents from `examples/data/splitting_and_sorting/testing` folder to inbox queues.
