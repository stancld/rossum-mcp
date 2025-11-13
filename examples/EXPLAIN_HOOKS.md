# Explain Hook Functionality

```
Briefly explain the functionality of every hook based on description and/or code one by one for a queue `3885208`.

Store output in extestion_explanation.md
```

## Expected Format for Hook Descriptions

When describing hook functionality, use the following structured format:

**Functionality**: [Brief description of what the hook does]

**Trigger Events**:
- [event.type] (what happens at this event)
- [event.type] (what happens at this event)

**How it works**:
1. [Step-by-step explanation of the hook's operation]
2. [Include technical details about what happens]
3. [Describe data flow and transformations]
4. [Note any conditional behavior]

**Configuration**:
- [setting_name]: [What this setting does]
- [setting_name]: [What this setting does]

### Example: Document Splitting and Sorting

**Functionality**: Automatically splits multi-document uploads into separate annotations and routes them to appropriate queues.

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

**Configuration**:
- sorting_queues: Maps document types to target queue IDs for routing
- max_blank_page_words: Threshold for blank page detection (pages with fewer words are considered blank)
