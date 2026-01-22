# Rossum MCP Tools Reference

Complete API reference for all 50 MCP tools. For quick start and setup, see [README.md](README.md).

## Document Processing (6 tools)

### upload_document

Uploads a document to Rossum for processing. Returns a task ID. Use `list_annotations` to get the annotation ID.

**Parameters:**
- `file_path` (string, required): Absolute path to the document file
- `queue_id` (integer, required): Rossum queue ID where the document should be uploaded

**Returns:**
```json
{
  "task_id": "12345",
  "task_status": "created",
  "queue_id": 12345,
  "message": "Document upload initiated. Use `list_annotations` to find the annotation ID for this queue."
}
```

### get_annotation

Retrieves annotation data for a previously uploaded document. Use this to check the status of a document.

**Parameters:**
- `annotation_id` (integer, required): The annotation ID obtained from list_annotations
- `sideloads` (array, optional): List of sideloads to include. Use `['content']` to fetch annotation content with datapoints

**Returns:**
```json
{
  "id": "12345",
  "status": "to_review",
  "url": "https://elis.rossum.ai/api/v1/annotations/12345",
  "schema": "67890",
  "modifier": "11111",
  "document": "22222",
  "content": [...],
  "created_at": "2024-01-01T00:00:00Z",
  "modified_at": "2024-01-01T00:00:00Z"
}
```

### list_annotations

Lists all annotations for a queue with optional filtering. Useful for checking the status of multiple uploaded documents.

**Parameters:**
- `queue_id` (integer, required): Rossum queue ID to list annotations from
- `status` (string, optional): Filter by annotation status (default: 'importing,to_review,confirmed,exported')

**Returns:**
```json
{
  "count": 42,
  "results": [
    {
      "id": "12345",
      "status": "to_review",
      "url": "https://elis.rossum.ai/api/v1/annotations/12345",
      "document": "67890",
      "created_at": "2024-01-01T00:00:00Z",
      "modified_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### start_annotation

Starts an annotation to move it from 'importing' to 'reviewing' status. This is required before you can update annotation fields.

**Parameters:**
- `annotation_id` (integer, required): Rossum annotation ID to start

**Returns:**
```json
{
  "annotation_id": 12345,
  "message": "Annotation 12345 started successfully. Status changed to 'reviewing'."
}
```

### bulk_update_annotation_fields

Bulk update annotation field values using JSON Patch operations. This is the correct way to update annotation field values. Must be called after `start_annotation`.

**Parameters:**
- `annotation_id` (integer, required): Rossum annotation ID to update
- `operations` (array, required): List of JSON Patch operations with format:
  ```json
  [
    {
      "op": "replace",
      "id": 1234,
      "value": {
        "content": {
          "value": "new_value",
          "page": 1,
          "position": [x, y, w, h]
        }
      }
    }
  ]
  ```

**Important:** Use the numeric datapoint `id` from `annotation.content`, NOT the `schema_id`.

**Returns:**
```json
{
  "annotation_id": 12345,
  "operations_count": 1,
  "message": "Annotation 12345 updated with 1 operations successfully."
}
```

### confirm_annotation

Confirms an annotation to move it to 'confirmed' status. Can be called after `bulk_update_annotation_fields`.

**Parameters:**
- `annotation_id` (integer, required): Rossum annotation ID to confirm

**Returns:**
```json
{
  "annotation_id": 12345,
  "message": "Annotation 12345 confirmed successfully. Status changed to 'confirmed'."
}
```

---

## Queue Management (8 tools)

### get_queue

Retrieves queue details including the schema_id.

**Parameters:**
- `queue_id` (integer, required): Rossum queue ID to retrieve

### list_queues

Lists all queues with optional filtering by ID, workspace, or name.

**Parameters:**
- `id` (integer, optional): Filter by queue ID
- `workspace_id` (integer, optional): Filter by workspace ID
- `name` (string, optional): Filter by queue name

**Returns:**
```json
[
  {
    "id": 12345,
    "name": "Invoice Processing",
    "url": "https://elis.rossum.ai/api/v1/queues/12345",
    "workspace": "https://elis.rossum.ai/api/v1/workspaces/100",
    "schema": "https://elis.rossum.ai/api/v1/schemas/200",
    "inbox": "https://elis.rossum.ai/api/v1/inboxes/300",
    "status": "active",
    "locale": "en_GB",
    "automation_enabled": true
  }
]
```

### get_queue_schema

Retrieves the complete schema for a queue in a single call. This is the recommended way to get a queue's schema.

**Parameters:**
- `queue_id` (integer, required): Rossum queue ID

### get_queue_engine

Retrieves the complete engine information for a given queue in a single call.

**Parameters:**
- `queue_id` (integer, required): Rossum queue ID

### create_queue

Creates a new queue with schema and optional engine assignment.

**Parameters:**
- `name` (string, required): Name of the queue to create
- `workspace_id` (integer, required): Workspace ID where the queue should be created
- `schema_id` (integer, required): Schema ID to assign to the queue
- `engine_id` (integer, optional): Optional engine ID to assign for document processing
- Additional optional parameters for automation, locale, training, etc.

### create_queue_from_template

Create queues from predefined regional templates (EU/US/UK/CZ/CN).

### get_queue_template_names

List available queue template names.

### update_queue

Updates an existing queue's settings including automation thresholds.

**Parameters:**
- `queue_id` (integer, required): Queue ID to update
- `queue_data` (object, required): Dictionary containing queue fields to update

---

## Schema Management (7 tools)

### get_schema

Retrieves schema details including the schema content/structure.

**Parameters:**
- `schema_id` (integer, required): Rossum schema ID to retrieve

### list_schemas

Lists all schemas with optional filtering by name or queue.

**Parameters:**
- `name` (string, optional): Filter by schema name
- `queue_id` (integer, optional): Filter by queue ID

**Returns:**
```json
[
  {
    "id": 12345,
    "name": "Invoice Schema",
    "url": "https://elis.rossum.ai/api/v1/schemas/12345",
    "queues": ["https://elis.rossum.ai/api/v1/queues/100"],
    "content": "<omitted>",
    "metadata": {},
    "modified_at": "2025-01-15T10:00:00Z"
  }
]
```

### create_schema

Creates a new schema with sections and datapoints.

**Parameters:**
- `name` (string, required): Schema name
- `content` (array, required): Schema content array containing sections with datapoints

**Example content structure:**
```json
[
  {
    "category": "section",
    "id": "document_info",
    "label": "Document Information",
    "children": [
      {
        "category": "datapoint",
        "id": "document_type",
        "label": "Document Type",
        "type": "enum",
        "rir_field_names": [],
        "constraints": {"required": false},
        "options": [
          {"value": "invoice", "label": "Invoice"},
          {"value": "receipt", "label": "Receipt"}
        ]
      }
    ]
  }
]
```

### update_schema

Updates an existing schema, typically used to set field-level automation thresholds.

**Parameters:**
- `schema_id` (integer, required): Schema ID to update
- `schema_data` (object, required): Dictionary containing schema fields to update

### patch_schema

Patch a schema by adding, updating, or removing individual nodes without replacing the entire content.

**Parameters:**
- `schema_id` (integer, required): Schema ID to patch
- `operation` (string, required): One of "add", "update", or "remove"
- `node_id` (string, required): ID of the node to operate on
- `node_data` (object, optional): Data for add/update operations
- `parent_id` (string, optional): Parent node ID for add operation
- `position` (integer, optional): Position for add operation

**Example usage:**
```python
# Add a new datapoint to a section
patch_schema(
    schema_id=123,
    operation="add",
    node_id="vendor_name",
    parent_id="header_section",
    node_data={"label": "Vendor Name", "type": "string", "category": "datapoint"}
)

# Update a field's label and threshold
patch_schema(
    schema_id=123,
    operation="update",
    node_id="invoice_number",
    node_data={"label": "Invoice #", "score_threshold": 0.9}
)

# Remove a field
patch_schema(schema_id=123, operation="remove", node_id="old_field")
```

### get_schema_tree_structure

Get lightweight tree view of schema with only ids, labels, categories, and types.

### prune_schema_fields

Efficiently remove multiple fields from schema at once (for organization setup).

---

## Engine Management (6 tools)

### get_engine

Retrieves detailed information about a specific engine by its ID.

**Parameters:**
- `engine_id` (integer, required): Engine ID to retrieve

**Returns:**
```json
{
  "id": 12345,
  "name": "Invoice Extractor",
  "url": "https://elis.rossum.ai/api/v1/engines/12345",
  "type": "extractor",
  "learning_enabled": true,
  "training_queues": ["https://elis.rossum.ai/api/v1/queues/100"],
  "description": "Extracts invoice data",
  "agenda_id": "agenda-123",
  "organization": "https://elis.rossum.ai/api/v1/organizations/10"
}
```

### list_engines

Lists all engines with optional filtering.

**Parameters:**
- `id` (integer, optional): Filter by engine ID
- `engine_type` (string, optional): Filter by engine type ('extractor' or 'splitter')
- `agenda_id` (string, optional): Filter by agenda ID

### create_engine

Creates a new engine for document processing.

**Parameters:**
- `name` (string, required): Engine name
- `organization_id` (integer, required): Organization ID
- `engine_type` (string, required): Engine type - 'extractor' or 'splitter'

### update_engine

Updates an existing engine's settings including learning and training queues.

**Parameters:**
- `engine_id` (integer, required): Engine ID to update
- `engine_data` (object, required): Dictionary containing engine fields to update

### create_engine_field

Creates a new engine field and links it to schemas.

**Parameters:**
- `engine_id` (integer, required): Engine ID
- `name` (string, required): Field name (slug format, max 50 chars)
- `label` (string, required): Human-readable label (max 100 chars)
- `field_type` (string, required): Field type - 'string', 'number', 'date', or 'enum'
- `schema_ids` (array, required): List of schema IDs to link

### get_engine_fields

Retrieves engine fields for a specific engine or all engine fields.

**Parameters:**
- `engine_id` (integer, optional): Engine ID to filter fields by

---

## Extensions & Rules (9 tools)

### get_hook

Get hook/extension details.

**Parameters:**
- `hook_id` (integer, required): Hook ID

### list_hooks

Lists all hooks/extensions configured in your organization.

**Parameters:**
- `queue_id` (integer, optional): Filter hooks by queue ID
- `active` (boolean, optional): Filter by active status

### create_hook

Creates a new hook (webhook or serverless function).

**Parameters:**
- `name` (string, required): Hook name
- `type` (string, required): Hook type - 'webhook' or 'function'
- `queues` (array, optional): List of queue URLs
- `events` (array, optional): List of trigger events
- `config` (object, optional): Hook configuration
- `settings` (object, optional): Hook settings
- `secret` (string, optional): Secret key for webhooks

**Common events:**
- `annotation_content.initialize` - When annotation is first created
- `annotation_content.confirm` - When annotation is confirmed
- `annotation_content.export` - When annotation is exported
- `annotation_status` - When annotation status changes

### update_hook

Updates an existing hook.

**Parameters:**
- `hook_id` (integer, required): Hook ID to update
- `name`, `queues`, `events`, `config`, `settings`, `active` (optional): Fields to update

### list_hook_templates

Lists available hook templates from Rossum Store.

### create_hook_from_template

Creates a hook from a Rossum Store template.

**Parameters:**
- `name` (string, required): Name for the new hook
- `hook_template_id` (integer, required): Template ID from `list_hook_templates`
- `queues` (array, required): List of queue URLs
- `events` (array, optional): Override template defaults
- `token_owner` (string, optional): User URL for token ownership

### list_hook_logs

Lists hook execution logs for debugging.

**Parameters:**
- `hook_id`, `queue_id`, `annotation_id` (optional): Filter options
- `log_level` (string, optional): 'INFO', 'ERROR', or 'WARNING'
- `timestamp_before`, `timestamp_after` (string, optional): ISO 8601 timestamps

### get_rule

Get business rule details.

**Parameters:**
- `rule_id` (integer, required): Rule ID

### list_rules

Lists all business rules.

**Parameters:**
- `schema_id` (integer, optional): Filter by schema ID
- `organization_id` (integer, optional): Filter by organization ID
- `enabled` (boolean, optional): Filter by enabled status

---

## Workspace Management (3 tools)

### get_workspace

Retrieves workspace details by ID.

**Parameters:**
- `workspace_id` (integer, required): Workspace ID

### list_workspaces

Lists all workspaces with optional filtering.

### create_workspace

Creates a new workspace.

---

## User Management (3 tools)

### get_user

Retrieves a single user by ID.

**Parameters:**
- `user_id` (integer, required): User ID

### list_users

Lists users in the organization. Use this to find a user's URL for `token_owner` in `create_hook_from_template`.

**Parameters:**
- `username`, `email`, `first_name`, `last_name` (optional): Filter options
- `is_active` (boolean, optional): Filter by active status
- `is_organization_group_admin` (boolean, optional): Filter by admin role

### list_user_roles

Lists all user roles (groups of permissions) in the organization.

---

## Relations Management (4 tools)

### get_relation

Retrieves annotation relation details by ID.

**Parameters:**
- `relation_id` (integer, required): Relation ID

### list_relations

Lists all relations between annotations.

**Relation types:**
- `edit` - Created after editing annotation (rotation/split)
- `attachment` - Documents attached to another
- `duplicate` - Same document imported twice

**Parameters:**
- `type` (string, optional): Filter by type
- `parent` (integer, optional): Filter by parent annotation ID

### get_document_relation

Retrieves document relation details by ID.

**Parameters:**
- `document_relation_id` (integer, required): Document relation ID

### list_document_relations

Lists all document relations.

**Relation types:**
- `export` - Documents generated from exporting
- `einvoice` - Electronic invoice documents

**Parameters:**
- `type` (string, optional): Filter by type
- `annotation` (integer, optional): Filter by annotation ID

---

## Email Templates (3 tools)

### get_email_template

Retrieves email template details by ID.

**Parameters:**
- `email_template_id` (integer, required): Email template ID

### list_email_templates

Lists all email templates.

**Parameters:**
- `queue_id` (integer, optional): Filter by queue ID
- `type` (string, optional): 'rejection', 'rejection_default', 'email_with_no_processable_attachments', 'custom'

### create_email_template

Creates a new email template.

**Parameters:**
- `name` (string, required): Template name
- `queue` (string, required): Queue URL
- `subject` (string, required): Email subject
- `message` (string, required): Email body (HTML supported)
- `type` (string, optional): Template type (default: 'custom')
- `automate` (boolean, optional): Auto-send on trigger (default: false)
- `to`, `cc`, `bcc` (array, optional): Recipient objects

**Recipient types:**
- `{"type": "annotator", "value": ""}` - Document annotator
- `{"type": "constant", "value": "email@example.com"}` - Fixed email
- `{"type": "datapoint", "value": "email_field_id"}` - From field

---

## Tool Discovery (1 tool)

### list_tool_categories

Lists all available tool categories with descriptions, tool names, and keywords for dynamic tool loading.

**Available Categories:**
- `annotations` - Document processing (6 tools)
- `queues` - Queue management (8 tools)
- `schemas` - Schema management (7 tools)
- `engines` - AI engine management (6 tools)
- `hooks` - Extensions/webhooks (7 tools)
- `email_templates` - Email templates (3 tools)
- `document_relations` - Document relations (2 tools)
- `relations` - Annotation relations (2 tools)
- `rules` - Validation rules (2 tools)
- `users` - User management (3 tools)
- `workspaces` - Workspace management (3 tools)

---

## Annotation Status Workflow

When a document is uploaded, the annotation progresses through various states:

1. **importing** - Initial state after upload. Document is being processed.
2. **to_review** - Extraction complete, ready for user validation.
3. **reviewing** - Annotation is being reviewed (triggered by `start_annotation`).
4. **confirmed** - Validated and confirmed (via `confirm_annotation`).
5. **exporting** - Being exported.
6. **exported** - Final state for successfully processed documents.

Other states: `created`, `failed_import`, `split`, `in_workflow`, `rejected`, `failed_export`, `postponed`, `deleted`, `purged`.

**Important:**
- Wait for annotations to transition from `importing` to `to_review` before considering them processed.
- Call `start_annotation` before updating field values.
- Call `confirm_annotation` after updating fields to finalize.

---

## Example Workflows

### Single Document Upload

1. Upload using `upload_document`
2. Get annotation ID using `list_annotations`
3. Check status using `get_annotation`
4. Wait until status is `to_review`, `confirmed`, or `exported`

### Document Upload with Field Updates

1. Upload using `upload_document`
2. Get annotation ID using `list_annotations`
3. Wait until status is `importing` or `to_review`
4. Start annotation using `start_annotation`
5. Get content using `get_annotation` with `sideloads=['content']`
6. Update fields using `bulk_update_annotation_fields`
7. Confirm using `confirm_annotation`

### Create Queue with Engine

1. Create schema using `create_schema`
2. Create engine using `create_engine`
3. Create engine fields using `create_engine_field`
4. Create queue using `create_queue`
5. Optionally update engine training queues using `update_engine`
