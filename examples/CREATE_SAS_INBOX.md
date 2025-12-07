# Create Splitting & Sorting Inbox

Setup Inbox for Splitting & Sorting in workspace `1777693`.

## A. Setup

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

## B. Run test

4. Upload 10 documents from `examples/data/splitting_and_sorting/testing` folder to inbox queues.
