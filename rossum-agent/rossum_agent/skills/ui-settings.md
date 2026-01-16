# UI Settings Skill

**Goal**: Update queue UI settings (`settings.annotation_list_table.columns`) without corrupting structure.

## Workflow

1. Fetch current settings via `get_queue`
2. Modify only `columns` array, preserve all other keys
3. Patch via `update_queue(queue_id, queue_data={"settings": settings})`

## Column Types

| Type | Required Fields | Optional |
|------|-----------------|----------|
| `meta` | `column_type`, `meta_name`, `visible` | `width` (default: 170.0) |
| `schema` | `column_type`, `schema_id`, `data_type`, `visible` | `width` |

### Meta `meta_name` Values

`status`, `original_file_name`, `labels`, `assignees`, `queue`, `details`, `created_at`, `modified_at`, `confirmed_at`, `exported_at`, `rejected_at`, `deleted_at`, `assigned_at`, `modifier`, `confirmed_by`, `exported_by`, `rejected_by`, `deleted_by`

### Schema `data_type` Values

`string`, `number`, `date`

## Constraints

| Rule | Rationale |
|------|-----------|
| `width` must be float | `170.0` not `170` |
| Validate `schema_id` exists | Check queue schema before adding |
| Preserve column order | Unless explicitly reordering |

## Column List Behavior

| User Request | Action |
|--------------|--------|
| "Add column X" | Keep existing columns, append new |
| Provides full list | Use ONLY listed columns, discard unlisted |
