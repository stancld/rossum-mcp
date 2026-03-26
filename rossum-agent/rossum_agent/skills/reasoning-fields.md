---
name: Reasoning Fields
description: create AI-powered reasoning fields with prompt + context
---

# Reasoning Fields Skill

**Goal**: Create reasoning fields that use AI to interpret document context and generate values from natural language instructions.

Use reasoning fields for ambiguous formats, contextual interpretation (sentiment, categorization), and unstructured text extraction. For deterministic math/logic, use formula fields instead.

## Creating

Call `patch_schema_with_subagent(schema_id, changes)` with `id`, `label`, `type`, `parent_section`, and the reasoning-specific fields (`prompt`, `context`).

## Schema Config

| Property | Description |
|----------|-------------|
| `prompt` | Instructions for the AI (max 2000 chars) |
| `context` | Field references the AI can read (TxScript format, e.g. `["field.notes", "field.terms"]`) |
| `ui_configuration` | `{"type": "reasoning", "edit": "disabled"}` |
| `score_threshold` | Float, default `0.8` |

## Writing Prompt Instructions

| Principle | Example |
|-----------|---------|
| Be specific | "Extract the early payment discount percentage from field.notes" |
| Use field_ids | "Look at field.vendor_name and field.sender_address" |
| Say what to exclude | "Ignore shipping-related terms" |
| Provide examples | "Output: 'Net 30', 'Net 60', '2/10 Net 30'" |
| Define fallback | "If not found, output 'N/A'" |
| Define output format | "Return as 'YYYY-MM-DD' date string" |

## Common Use Cases

| Use Case | Context Fields | Instructions Pattern |
|----------|---------------|---------------------|
| Early payment discounts | `field.notes`, `field.terms` | "Extract discount % and deadline" |
| Categorize line items | `field.item_description` | "Classify as: Office Supplies, Equipment, Services" |
| Email sentiment | `field.email_body` | "Rate urgency: Low, Medium, High" |
| Header from email | `field.email_body` | "Extract sender company name" |

## Related Skills

- `formula-fields` — deterministic transformations (faster, cheaper, no AI)
- `schema-patching` — adding fields to schema
