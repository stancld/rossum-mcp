# Formula Fields Skill

**Goal**: Create or update formula fields that compute deterministic values from other fields using TxScript.

Use formula fields for clear rules, math, string ops, conditional logic, and aggregations. For ambiguous interpretation, use reasoning fields instead.

## Creating / Updating

Always use `execute_python` with `suggest_formula_field` to generate formulas — never write TxScript formulas by hand.

```python
result = suggest_formula_field(
    label="Net Terms",
    hint="Compute payment terms based on due date and issue date",
    schema_id=9389721,
    section_id="basic_info",
    field_schema_id="net_terms",
    field_type="number",  # string (default), number, date, enum — must match the formula's output
)
```

When updating an existing field, preserve its original type by passing the matching `field_type`.

Then apply via `patch_schema_with_subagent(schema_id, changes)` using `result["formula"]` or `result["field_definition"]`.

For simple formula updates on existing fields, `patch_schema` MCP tool works directly:

```
patch_schema(schema_id=12345, operation="update", node_id="field_id", node_data={"formula": "new_code"})
```

## Schema Config

Formula fields require:
- `ui_configuration`: `{"type": "formula", "edit": "disabled"}`
- `formula`: TxScript code string

## TxScript

Full reference: load `txscript` skill. Key formula-specific constraint: 2000 character limit per formula.

## Common Patterns

```python
# Date arithmetic
field.date_issue + timedelta(days=14)

# Conditional
field.amount_total * 0.8 if field.amount_total > 20000 else field.amount_total

# Fallback chain
default_to(default_to(field.amount_total, field.amount_total_base), sum(default_to(field.item_amount_total.all_values, 0)))

# Sum check with warning
line_items_sum = sum(default_to(field.item_amount_total.all_values, 0))
if round(line_items_sum, 2) != round(field.amount_total, 2):
    show_warning('Sum of line items does not equal total amount!', field.amount_total)

# Iterate line items
for row in field.line_items:
    if is_set(row.item_amount_total) and row.item_amount_total < 0:
        show_error("Negative amount", row.item_amount_total)

# Distribute header value to line items
if is_set(field.item_order_id):
    field.item_order_id
else:
    field.order_id
```

## Related Skills

- `python-execution` — shared Python helper reference
- `txscript` — full language reference
- `schema-patching` — adding fields to schema
- `reasoning-fields` — contextual AI inference (non-deterministic)
