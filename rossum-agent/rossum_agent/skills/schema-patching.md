# Schema Patching Skill

**Goal**: Modify document schemas safely with validation and error recovery.

## Usage

**Use `patch_schema_with_subagent` tool** for all schema modifications.

```json
patch_schema_with_subagent(
  schema_id="12345",
  changes='[{"action": "add", "id": "invoice_number", "parent_section": "header_section", "type": "string", "label": "Invoice Number"}]'
)
```

The sub-agent:
- Fetches schema, applies changes one at a time (max 3 before re-fetching)
- Verifies only requested fields are present after patching
- Returns summary of changes made

## Changes Format

Each change object in the `changes` array:

| Field | Required | Description |
|-------|----------|-------------|
| `action` | No | "add" (default) or "remove" |
| `id` | Yes | Field ID (schema_id) |
| `parent_section` | For add | Section ID to add field to |
| `type` | For add | string, number, date, enum |
| `label` | No | Defaults to id |

## Field Types

| Type | Extra Fields |
|------|--------------|
| `string` | `default_value`, `constraints` |
| `number` | `default_value` |
| `date` | `format` |
| `enum` | `options: [{"value": "v1", "label": "Label 1"}]` |

## Formula Fields

```json
{"id": "total", "type": "number", "is_formula": true, "formula": "field.amount + field.tax", "score_threshold": 0.8}
```

`score_threshold` is required for formula fields (default `0.8`).

## AI/Reasoning Fields

```json
{"id": "category", "type": "string", "is_reasoning": true, "prompt": "Extract the document category", "score_threshold": 0.8}
```

## Cross-Reference

- Schema customization during queue creation: load `organization-setup` skill
- Sandbox testing before production: load `rossum-deployment` skill
