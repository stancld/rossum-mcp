# Rossum MCP Tools Reference

Complete API reference for all 31 MCP tools. For quick start and setup, see [README.md](README.md).

---

## Unified Read Layer (2 tools)

The read layer replaces all individual `get_X` and `list_X` tools with two generic tools that cover every entity type.

### get

Retrieves one or more entities by ID.

**Parameters:**
- `entity` (EntityType, required): One of `queue`, `schema`, `hook`, `engine`, `rule`, `user`, `workspace`, `email_template`, `organization_group`, `annotation`, `relation`, `document_relation`, `organization_limit`, `hook_secrets_keys`
- `entity_id` (integer or list of integers, required): Single ID or list of IDs for batch retrieval
- `include_related` (boolean, optional, default: false): Enriches with related data:
  - `queue` → `schema_tree`, `engine`, `hooks`
  - `schema` → `queues`, `rules`
  - `hook` → `queues`, `events`

**Returns:**
```json
{
  "entity": "queue",
  "id": 12345,
  "data": { "...": "full entity data" },
  "_related": { "...": "only when include_related=true" }
}
```

Batch retrieval (list of IDs) returns an array of the same structure.

---

### search

Lists/searches entities with typed, entity-specific filters. Pass a query object with an `entity` discriminator field.

**Supported entities and their filters:**

| Entity | Filters |
|--------|---------|
| `queue` | `id`, `workspace_id`, `name`, `use_regex` |
| `schema` | `name`, `queue_id`, `use_regex` |
| `hook` | `queue_id`, `active`, `first_n` |
| `engine` | `id`, `engine_type` (`extractor`\|`splitter`), `agenda_id` |
| `rule` | `schema_id`, `organization_id`, `enabled` |
| `user` | `username`, `email`, `first_name`, `last_name`, `is_active`, `is_organization_group_admin` |
| `workspace` | `organization_id`, `name`, `use_regex` |
| `email_template` | `queue_id`, `type`, `name`, `first_n`, `use_regex` |
| `organization_group` | `name`, `use_regex` |
| `annotation` | `queue_id` (required), `status`, `ordering`, `first_n` |
| `relation` | `id`, `type`, `parent`, `key`, `annotation` |
| `document_relation` | `id`, `type`, `annotation`, `key`, `documents` |
| `hook_log` | `hook_id`, `queue_id`, `annotation_id`, `email_id`, `log_level`, `status`, `status_code`, `request_id`, `timestamp_before`, `timestamp_after`, `start_before`, `start_after`, `end_before`, `end_after`, `search`, `page_size` |
| `hook_template` | _(no filters)_ |
| `user_role` | _(no filters)_ |
| `queue_template_name` | _(no filters)_ |

**Example:**
```json
{
  "entity": "annotation",
  "queue_id": 12345,
  "status": "to_review,confirmed",
  "first_n": 10
}
```

**Returns:** Array of entity objects.

---

## Delete Layer (1 tool)

The delete layer replaces all individual `delete_X` tools with a single unified `delete` tool.

### delete

Deletes any supported entity by ID.

**Parameters:**
- `entity` (string, required): One of `queue`, `schema`, `hook`, `rule`, `workspace`, `annotation`
- `entity_id` (integer, required): ID of the entity to delete

**Entity-specific behavior:**
- **queue** — Deletion begins after ~24h; cascades to annotations/documents
- **schema** — Fails with `409 Conflict` if linked to any queue/annotation
- **workspace** — Fails if workspace still contains queues
- **annotation** — Soft delete (moves to `deleted` status)

**Returns:**
```json
{
  "message": "Queue 12345 scheduled for deletion (starts after 24 hours)"
}
```

---

## Document Processing (6 tools)

### upload_document

Uploads a document to Rossum for processing. Returns a task ID. Use `search` with `entity='annotation'` to find the created annotation.

**Parameters:**
- `file_path` (string, required): Absolute path to the document file
- `queue_id` (integer, required): Rossum queue ID where the document should be uploaded

**Returns:**
```json
{
  "task_id": "12345",
  "task_status": "created",
  "queue_id": 12345,
  "message": "Document upload initiated. Use `search(query={\"entity\": \"annotation\", \"queue_id\": ...})` to find the annotation ID for this queue."
}
```

### get_annotation_content

Fetches annotation extracted content and saves it to a local JSON file. Returns the path for `jq`/`grep` processing.

**Parameters:**
- `annotation_id` (integer, required): The annotation ID

**Returns:**
```json
{
  "path": "/tmp/rossum_annotation_12345_content.json"
}
```

### start_annotation

Sets annotation status to `reviewing` (from `to_review`). Required before updating annotation fields.

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

Bulk updates annotation field values using JSON Patch operations. Requires annotation in `reviewing` status. Call `start_annotation` first.

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

Confirms an annotation to move it to `confirmed` status. Call after `bulk_update_annotation_fields`.

**Parameters:**
- `annotation_id` (integer, required): Rossum annotation ID to confirm

**Returns:**
```json
{
  "annotation_id": 12345,
  "message": "Annotation 12345 confirmed successfully. Status changed to 'confirmed'."
}
```

### copy_annotations

Copies annotations to another queue. Use `reimport=True` to re-extract data in the target queue (e.g. when moving documents between queues). Use `reimport=False` to preserve the original extracted data as-is.

**Parameters:**
- `annotation_ids` (array of integers, required): List of annotation IDs to copy
- `target_queue_id` (integer, required): Queue ID to copy annotations into
- `target_status` (string, optional): Target annotation status after copying
- `reimport` (boolean, optional, default: false): Whether to re-extract data in the target queue

**Returns:**
```json
{
  "copied": 2,
  "failed": 0,
  "results": [
    {"annotation_id": 12345, "copied_annotation": {"...": "..."}},
    {"annotation_id": 12346, "copied_annotation": {"...": "..."}}
  ],
  "errors": []
}
```

---

## Queue Management (2 tools)

### update_queue

Updates an existing queue's settings.

**Parameters:**
- `queue_id` (integer, required): Queue ID to update
- `queue_data` (object, required): Dictionary containing queue fields to update. Supported keys: `name`, `automation_enabled`, `automation_level`, `locale`, `metadata`, `settings`, `engine`, `dedicated_engine`, `training_enabled`, `webhooks`, `hooks`, `default_score_threshold`, `session_timeout`, `document_lifetime`, `delete_after`, `schema`, `workspace`, `connector`, `inbox`

### create_queue_from_template

Creates a queue from a predefined regional template. Automatically creates a matching schema and optionally assigns an engine.

**Parameters:**
- `name` (string, required): Name for the new queue
- `template_name` (string, required): Template name (use `search` with `entity: "queue_template_name"` to list)
- `workspace_id` (integer, required): Workspace ID where the queue should be created
- `include_documents` (boolean, optional, default: false): Include sample documents from the template
- `engine_id` (integer, optional): Engine ID to assign; if not provided, the template's default engine is used

**Returns:** Queue object with `_tracked_resources` listing the schema and engine created as side effects.

---

## Schema Management (3 tools)

### patch_schema

Patches a schema by adding, updating, or removing individual nodes without replacing the entire content.

**Parameters:**
- `schema_id` (integer, required): Schema ID to patch
- `operation` (string, required): One of `add`, `update`, or `remove`
- `node_id` (string, required): ID of the node to operate on
- `node_data` (object, optional): Data for `add`/`update` operations
- `parent_id` (string, optional): Parent node ID for `add` operation
- `position` (integer, optional): Position for `add` operation

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

Gets a lightweight tree view of a schema with only ids, labels, categories, and types. Accepts either `schema_id` or `queue_id`.

**Parameters:**
- `schema_id` (integer, optional): Schema ID
- `queue_id` (integer, optional): Queue ID (resolves the queue's schema)

### prune_schema_fields

Efficiently removes multiple fields from a schema at once.

**Parameters:**
- `schema_id` (integer, required): Schema ID to prune
- `fields_to_keep` (array of strings, optional): Keep only these leaf field IDs; parent containers are preserved automatically; pass section IDs to preserve them as empty containers
- `fields_to_remove` (array of strings, optional): Remove these leaf field IDs

Provide exactly one of `fields_to_keep` or `fields_to_remove`.

**Returns:**
```json
{
  "removed_fields": ["old_field_1", "old_field_2"],
  "remaining_fields": ["vendor_name", "invoice_number"]
}
```

---

## Engine Management (4 tools)

### create_engine

Creates a new engine for document processing. After creating an engine, immediately create matching engine fields for the target schema.

**Parameters:**
- `name` (string, required): Engine name
- `organization_id` (integer, required): Organization ID
- `engine_type` (string, required): `extractor` or `splitter`

### update_engine

Updates an existing engine's settings.

**Parameters:**
- `engine_id` (integer, required): Engine ID to update
- `engine_data` (object, required): Dictionary with fields to update. Supported keys: `name`, `description`, `learning_enabled`, `training_queues`

### create_engine_field

Creates a new engine field and links it to schemas.

**Parameters:**
- `engine_id` (integer, required): Engine ID
- `name` (string, required): Field name (slug format, max 50 chars)
- `label` (string, required): Human-readable label (max 100 chars)
- `field_type` (string, required): `string`, `number`, `date`, or `enum`
- `schema_ids` (array of integers, required): List of schema IDs to link (at least one required)
- `tabular` (boolean, optional, default: false): Whether the field is tabular (line item)
- `multiline` (boolean, optional, default: false): Whether the field is multiline
- `subtype` (string, optional): Field subtype
- `pre_trained_field_id` (string, optional): Pre-trained field ID to link

### get_engine_fields

Retrieves engine fields for a specific engine or all engine fields.

**Parameters:**
- `engine_id` (integer, optional): Engine ID to filter fields; omit to retrieve all engine fields

---

## Extensions — Hooks (4 tools)

### create_hook

Creates a new hook (webhook or serverless function).

**Parameters:**
- `name` (string, required): Hook name
- `type` (string, required): `webhook` or `function`
- `queues` (array of strings, optional): List of queue URLs
- `events` (array of strings, optional): List of trigger events in `event.action` format
- `config` (object, optional): Hook configuration. For function hooks: `config.source` is auto-renamed to `config.code`, default runtime is `python3.12`, `timeout_s` is capped at 60
- `settings` (object, optional): Hook settings
- `secrets` (dict[str, str], optional): Secret key-value pairs for the hook
- `token_owner` (string, optional): User URL for token ownership; cannot be an `organization_group_admin` user
- `run_after` (array of strings, optional): List of hook URLs that must run before this hook
- `sideload` (array of HookSideload, optional): Sideload configuration for the hook

**Common events:**
- `annotation_content.initialize` — When annotation is first created
- `annotation_content.confirm` — When annotation is confirmed
- `annotation_content.export` — When annotation is exported
- `annotation_status.changed` — When annotation status changes

### update_hook

Patches an existing hook; only provided fields change.

**Parameters:**
- `hook_id` (integer, required): Hook ID to update
- `name` (string, optional): New hook name
- `queues` (array of strings, optional): New list of queue URLs
- `events` (array of strings, optional): New list of trigger events
- `config` (object, optional): New hook configuration
- `settings` (object, optional): New hook settings
- `active` (boolean, optional): Enable or disable the hook
- `secrets` (dict[str, str], optional): Secret key-value pairs for the hook
- `token_owner` (string, optional): User URL for token ownership
- `run_after` (array of strings, optional): List of hook URLs that must run before this hook
- `sideload` (array of HookSideload, optional): Sideload configuration for the hook

### create_hook_from_template

Creates a hook from a Rossum Store template. Use `search(query={"entity": "hook_template"})` to browse available templates.

**Parameters:**
- `name` (string, required): Name for the new hook
- `hook_template_id` (integer, required): Template ID from `search`
- `queues` (array of strings, required): List of queue URLs
- `events` (array of strings, optional): Override template default events
- `token_owner` (string, optional): User URL for token ownership (required if template has `use_token_owner`; cannot be an `organization_group_admin` user)

### test_hook

Tests a hook by auto-generating a realistic payload and executing it. For `annotation_content`/`annotation_status` events, annotation and status are auto-resolved from the hook's queues if not provided.

**Parameters:**
- `hook_id` (integer, required): Hook ID to test
- `event` (HookEvent, required): Hook event (e.g., `annotation_content`, `annotation_status`)
- `action` (HookAction, required): Hook action (e.g., `initialize`, `confirm`, `export`)
- `annotation` (string, optional): Annotation URL to use for real data
- `status` (string, optional): Annotation status
- `previous_status` (string, optional): Previous annotation status
- `config` (object, optional): Config override for the test run

**Returns:** Dict with hook response and execution logs.

---

## Rules & Actions (3 tools)

### create_rule

Creates a new business rule. At least one of `schema_id` or `queue_ids` is required to scope the rule.

**Parameters:**
- `name` (string, required): Rule name
- `trigger_condition` (string, required): TxScript formula (e.g., `"field.amount > 10000"`)
- `actions` (array, required): List of actions. Each action requires: `id` (unique string), `type`, `event`, `payload`
- `enabled` (boolean, optional, default: true): Whether the rule is enabled
- `schema_id` (integer, optional): Schema ID to scope the rule
- `queue_ids` (array of integers, optional): Queue IDs to scope the rule to specific queues

**Action types:** `show_message`, `add_automation_blocker`, `add_validation_source`, `change_queue`, `send_email`, `hide_field`, `show_field`, `show_hide_field`, `change_status`, `add_label`, `remove_label`, `custom`

**Example:**
```json
{
  "name": "High Value Alert",
  "trigger_condition": "field.amount > 10000",
  "actions": [
    {
      "id": "show_high_value_message",
      "type": "show_message",
      "event": "validation",
      "payload": {"type": "error", "content": "High value invoice detected", "schema_id": "amount"}
    }
  ],
  "enabled": true,
  "schema_id": 12345,
  "queue_ids": [101, 102]
}
```

### patch_rule

Partial update (PATCH) of a business rule. Only provided fields are updated.

**Parameters:**
- `rule_id` (integer, required): Rule ID to update
- `name` (string, optional): Rule name
- `trigger_condition` (string, optional): TxScript formula
- `actions` (array, optional): List of actions
- `enabled` (boolean, optional): Whether the rule is enabled
- `queue_ids` (array of integers, optional): Queue IDs; pass `[]` to clear queue scoping

**Example:**
```python
# Disable a rule
patch_rule(rule_id=67890, enabled=False)

# Update only the trigger condition
patch_rule(rule_id=67890, trigger_condition="field.amount > 20000")

# Assign rule to specific queues
patch_rule(rule_id=67890, queue_ids=[101, 102])

# Remove all queue associations (rule applies to all queues using its schema)
patch_rule(rule_id=67890, queue_ids=[])
```

---

## Workspace Management (1 tool)

### create_workspace

Creates a new workspace.

**Parameters:**
- `name` (string, required): Workspace name
- `organization_id` (integer, required): Organization ID
- `metadata` (object, optional): Custom metadata

---

## User Management (2 tools)

### create_user

Creates a new user. Use `search(query={"entity": "user_role"})` to get role/group URLs.

**Parameters:**
- `username` (string, required): Username for the new user
- `email` (string, required): Email address for the new user
- `queues` (array of strings, optional): List of queue URLs to assign
- `groups` (array of strings, optional): List of group/role URLs to assign
- `first_name` (string, optional): User's first name
- `last_name` (string, optional): User's last name
- `is_active` (boolean, optional, default: true): Whether the user is active
- `metadata` (object, optional): Custom metadata
- `oidc_id` (string, optional): OIDC identity for SSO
- `auth_type` (string, optional, default: `password`): Authentication type

### update_user

Patches a user; only provided fields change. Use `search(query={"entity": "user_role"})` for role/group URLs.

**Parameters:**
- `user_id` (integer, required): User ID to update
- `username` (string, optional): Updated username
- `email` (string, optional): Updated email
- `first_name` (string, optional): Updated first name
- `last_name` (string, optional): Updated last name
- `queues` (array of strings, optional): New list of queue URLs
- `groups` (array of strings, optional): New list of group/role URLs
- `is_active` (boolean, optional): Active status
- `metadata` (object, optional): Updated metadata
- `oidc_id` (string, optional): Updated OIDC identity
- `auth_type` (string, optional): Updated authentication type
- `ui_settings` (object, optional): Updated UI settings

---

## Email Templates (1 tool)

### create_email_template

Creates a new email template.

**Parameters:**
- `name` (string, required): Template name
- `queue` (integer, required): Queue ID
- `subject` (string, required): Email subject
- `message` (string, required): Email body (HTML supported)
- `type` (string, optional, default: `custom`): Template type — `rejection`, `rejection_default`, `email_with_no_processable_attachments`, or `custom`
- `automate` (boolean, optional, default: false): Auto-send on trigger
- `to` (array, optional): Recipient objects
- `cc` (array, optional): CC recipient objects
- `bcc` (array, optional): BCC recipient objects
- `triggers` (array of strings, optional): Trigger event names for automatic sending

**Recipient object types:**
- `{"type": "annotator", "value": ""}` — Document annotator
- `{"type": "constant", "value": "email@example.com"}` — Fixed email address
- `{"type": "datapoint", "value": "email_field_id"}` — Value from a document field

---

## MCP Mode (1 tool)

### get_mcp_mode

Get the current MCP operation mode (read-only or read-write).

**Returns:** `{"mode": "read-only" | "read-write"}`

---

## Discovery (1 tool)

### list_tool_categories

Lists all available tool categories with descriptions, tool names, read/write status, and keywords for dynamic tool loading.

**Available categories:** `read`, `annotations`, `queues`, `schemas`, `engines`, `hooks`, `email_templates`, `rules`, `users`, `workspaces`

---

## Annotation Status Workflow

When a document is uploaded, the annotation progresses through various states:

1. **importing** — Initial state after upload. Document is being processed.
2. **to_review** — Extraction complete, ready for user validation.
3. **reviewing** — Annotation is being reviewed (triggered by `start_annotation`).
4. **confirmed** — Validated and confirmed (via `confirm_annotation`).
5. **exporting** — Being exported.
6. **exported** — Final state for successfully processed documents.

Other states: `created`, `failed_import`, `split`, `in_workflow`, `rejected`, `failed_export`, `postponed`, `deleted`, `purged`.

**Important:**
- Wait for annotations to transition from `importing` to `to_review` before considering them processed.
- Call `start_annotation` before updating field values.
- Call `confirm_annotation` after updating fields to finalize.

---

## Example Workflows

### Single Document Upload

1. Upload using `upload_document`
2. Get annotation ID using `search(query={"entity": "annotation", "queue_id": ..., "status": "importing,to_review"})`
3. Check status using `get(entity='annotation', entity_id=...)`
4. Wait until status is `to_review`, `confirmed`, or `exported`

### Document Upload with Field Updates

1. Upload using `upload_document`
2. Get annotation ID using `search(query={"entity": "annotation", "queue_id": ...})`
3. Start annotation using `start_annotation`
4. Get content using `get_annotation_content`
5. Update fields using `bulk_update_annotation_fields`
6. Confirm using `confirm_annotation`

### Create Queue with Engine

1. Create queue using `create_queue_from_template` (creates schema as byproduct)
2. Patch schema as needed using `patch_schema`
3. Create engine using `create_engine`
4. Create engine fields using `create_engine_field`
5. Optionally update engine training queues using `update_engine`

### Explore a Queue

```python
# Get queue with all related data in one call
get(entity="queue", entity_id=12345, include_related=True)
# Returns queue data + schema_tree + engine + hooks summary
```

### Find and Test a Hook

```python
# Browse available templates
search(query={"entity": "hook_template"})

# List hooks for a specific queue
search(query={"entity": "hook", "queue_id": 12345})

# View hook logs for debugging
search(query={"entity": "hook_log", "hook_id": 678, "log_level": "ERROR"})
```
