# Schema Patching Skill

**Goal**: Add, update, or remove individual schema fields.

## Tool

```
patch_schema_with_subagent(schema_id="12345", changes='[{"action": "add", "id": "invoice_number", "parent_section": "header_section", "type": "string", "label": "Invoice Number"}]')
```

Sub-agent handles fetching, applying, and verifying changes.

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
