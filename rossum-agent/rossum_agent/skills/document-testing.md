---
name: Document Testing
description: generate mock PDFs, upload, verify extraction, test hooks
---

# Document Testing Skill

**Goal**: Test document processing end-to-end — generate a schema-aware mock PDF, upload it, verify extraction, optionally trigger hooks.

## Workflow

1. Get schema: `search(query={"entity": "queue"})` → `get_schema_tree_structure(queue_id=queue_id)`
2. Filter tree to relevant fields: `required: true`, `hidden: false`, leaf nodes (`category: "datapoint"` or tuple children)
3. `generate_mock_pdf(fields=[...], document_type="invoice")`
4. `upload_document(file_path, queue_id)`
5. Poll: `search(query={"entity": "annotation", "queue_id": queue_id, "ordering": ["-created_at"], "first_n": 1})` every 5s, max 12 attempts
6. Verify: `get_annotation_content(annotation_id)` → compare vs `expected_values` and `line_items`
7. Optional: `test_hook(hook_id, event, action, annotation=annotation_url)`

## Field Extraction from Schema Tree

`get_schema_tree_structure` returns a lightweight tree with `id`, `label`, `category`, `type`, `required`, `hidden`, and `children`. Walk it recursively applying these filters:

| Filter | Rule |
|--------|------|
| `required: true` | Include only required fields |
| `hidden: false` | Exclude hidden fields |
| Leaf nodes | Include `category: "datapoint"` and tuple children (line item columns) |

| Schema node | Mapping |
|-------------|---------|
| `category: "section"` | Container — recurse into `children` |
| `category: "datapoint"` | Header field → `{id, label, type}` |
| `category: "multivalue"` | Table container — children are tuples |
| `category: "tuple"` | Table row template — children are line item columns |

Line item fields: `id` starting with `item_`.

## Constraints

| Constraint | Detail |
|------------|--------|
| Schema first | Always call `get_schema_tree_structure` before generating — field list must match the queue's schema |
| Required fields only | Include only fields with `required: true` from the tree. Omit optional fields to keep the mock PDF simple. Exception: user explicitly requests specific optional fields |
| No hidden fields | Exclude fields with `hidden: true` — internal/system fields not visible in the UI |
| Aurora-critical naming | Use labels "Total Amount" and "Total Amount Base" on the invoice in the PDF — Aurora relies on these exact names for capture |
| Overrides for specifics | Use `overrides={field_id: value}` to force values for edge-case testing |
| One queue at a time | Upload to a single queue, verify there, then repeat for others |
| Poll with backoff | Extraction takes 5-30s; poll `search(query={"entity": "annotation", ...})` with 5s intervals, 12 max attempts |

## Verification

Compare both `expected_values` (header) and `line_items` (table rows) from `generate_mock_pdf` output against extracted annotation content. Report mismatches with field ID, expected value, and extracted value.

### Match criteria

| Field type | Match criteria |
|------------|---------------|
| IDs, dates, VAT numbers | Exact match |
| Amounts | Approximate (±0.01) — rounding differences |
| Addresses, names | Partial/fuzzy — extraction may split or reformat |
| Enums | Exact match on value |

### Line item per-row math

For each extracted row, verify internal consistency:

| Check | Formula |
|-------|---------|
| Row total | `item_quantity × item_rate ≈ item_amount_total` (±0.01) |
| Row base | `item_amount_total_base ≈ item_amount_total / (1 + tax_rate)` (±0.01) |
| Column sum | `sum(item_amount_total) ≈ amount_total` (±0.01) |

**Edge cases — field equality when dimensions collapse:**

| Condition | Consequence |
|-----------|-------------|
| No `item_quantity` in schema (implicit qty=1) | `item_unit_price = item_amount_total` |
| `item_quantity = 1` | `item_unit_price = item_amount_total` |
| Tax rate = 0 | `item_amount_total = item_amount_total_base` |
| qty=1 + no tax | `item_unit_price = item_amount_total = item_amount_total_base` |

These equalities must hold in both mock PDF generation and extraction verification. When the schema lacks a quantity column, treat quantity as 1 for all consistency checks.

Report any row where the math doesn't hold — this indicates an extraction error even if individual field values matched.

## Cross-Reference

- Hook testing after upload: load `hooks` skill
- Schema field configuration: load `schema-patching` skill
- Formula field verification: load `formula-fields` skill
