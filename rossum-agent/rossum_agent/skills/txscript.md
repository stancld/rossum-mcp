# TxScript Reference Skill

**Goal**: Provide the complete TxScript language reference for writing formula fields, serverless functions, and rule trigger conditions. **IMPORTANT:** Use only if hooks from Rossum Store templates are not sufficient.

## What is TxScript

TxScript is a Python 3.12-based DSL for manipulating Rossum business transactions. It runs in three contexts: formula fields, serverless function hooks, and rule trigger conditions.

## Contexts

| Context | Entry point | Field access | Write | Return |
|---------|------------|--------------|-------|--------|
| Formula field | Implicit globals | `field.x` | Own value only (last expression) | Last expression = output |
| Serverless function | `TxScript.from_payload(payload)` | `t.field.x` | Any field: `t.field.x = val` | `return t.hook_response()` |
| Rule trigger condition | Inline expression | `field.x` | N/A | Must evaluate strictly to `True` |

## Imports

### Formula fields

No imports needed. All helpers and aliases are globals.

### Serverless functions

```python
from txscript import TxScript, is_set, is_empty, default_to, substitute
```

### Pre-imported aliases (available as globals in formula fields, importable in serverless)

| Identifier | Source |
|------------|--------|
| `date` | `datetime.date` |
| `datetime` | `datetime.datetime` |
| `timedelta` | `datetime.timedelta` |
| `re` | `import re` |

## Field Access

### Header fields

| Syntax | Context | Returns |
|--------|---------|---------|
| `field.amount_total` | Formula / rule | Pythonized value (`float`, `str`, `date`, or `None`-like) |
| `t.field.amount_total` | Serverless | Same |

### Field metadata

| Syntax | Returns |
|--------|---------|
| `field.amount.id` | Datapoint system ID (int) |
| `field.amount.rir_confidence` | AI confidence score |
| `field.amount.attr.ocr_raw_text` | Raw OCR text |
| `field.amount.attr.rir_raw_text` | Raw RIR text |

### Writable attributes (via `.attr`)

| Attribute | Type | Notes |
|-----------|------|-------|
| `position` | dict | Bounding box |
| `page` | int | Page number |
| `validation_sources` | list | Append `"connector"` to mark as validated |
| `hidden` | bool | Show/hide field |
| `options` | list[dict] | Enum options `[{"label": "A", "value": "a"}]` |

## Line Items & Tables

### Iteration

```python
# Formula field
for row in field.line_items:
    row.item_amount  # access column within row

# Serverless function
for row in t.field.line_items:
    row.item_amount
```

### TableColumn (`.all_values`)

`field.item_amount.all_values` returns a `TableColumn` — a NumPy-like sequence with elementwise operators.

| Operation | Example |
|-----------|---------|
| Elementwise arithmetic | `field.item_quantity.all_values * field.item_price.all_values` |
| Scalar broadcast | `field.item_amount.all_values * 0.9` |
| `sum()` | `sum(field.item_amount.all_values)` |
| `all()` / `any()` | `all(not is_empty(field.item_amount.all_values))` |
| `default_to()` | `default_to(field.item_amount.all_values, 0)` |
| `is_empty()` | `is_empty(field.item_amount.all_values)` |
| Supported operators | `+`, `-`, `*`, `/`, `//`, `%`, `**`, comparisons, `abs()`, `round()` |

### Multivalue manipulation (serverless only)

```python
# Filter rows
t.field.line_items = [row for row in t.field.line_items if not is_empty(row.item_amount)]

# Append row
t.field.line_items.append({"item_amount": 100, "item_description": "New item"})

# Remove row by value
t.field.po_numbers.all_values.remove(t.field.po_number_external)

# Set simple multivalue
t.field.multivalue_field.all_values = ["AAA", "BBB"]
```

## Helper Functions

| Function | Signature | Purpose |
|----------|-----------|---------|
| `is_empty(value)` | `(Any) -> bool` | `True` if field has no value. Use instead of `is None` |
| `is_set(value)` | `(Any) -> bool` | Opposite of `is_empty` |
| `default_to(value, default)` | `(Any, Any) -> Any` | Return `value` if set, else `default`. Works on `TableColumn` |
| `fallback(value, default)` | `(Any, Any) -> Any` | Alias for `default_to` |
| `substitute(pattern, repl, string, ...)` | Alias for `re.sub` | Regex substitution |

## Messaging Functions

Available as globals in formula fields, as methods on `t` in serverless functions.

| Function | Effect |
|----------|--------|
| `show_error("msg")` | Document-level error — blocks export and automation |
| `show_error("msg", field.x)` | Field-level error |
| `show_warning("msg")` | Document-level warning |
| `show_warning("msg", field.x)` | Field-level warning |
| `show_info("msg")` | Document-level info |
| `show_info("msg", field.x)` | Field-level info |
| `automation_blocker("msg")` | Blocks automation without error message |
| `automation_blocker("msg", field.x)` | Field-level automation blocker |

Column fields (e.g., `field.item_amount` as `TableColumnValue`) create document-level messages since they have no single datapoint ID.

## Annotation Actions (serverless only)

Requires `token_owner` enabled on the hook.

```python
t.annotation.action("reject", note_content="Amounts do not match")
t.annotation.action("postpone")
t.annotation.action("delete")
```

## Payload Access (serverless only)

```python
annotation_id = payload["annotation"]["id"]
page_count = len(payload["annotation"]["pages"])
original_file = payload["document"]["original_file_name"]
queue_name = payload["queues"][0]["name"]  # requires Queue sideload
base_url = payload.get("base_url", "https://api.elis.rossum.ai")
auth_token = payload.get("rossum_authorization_token")
settings = payload.get("settings", {})
secrets = payload.get("secrets", {})
updated_ids = payload.get("updated_datapoints", [])
```

## Enum Fields (serverless only)

```python
t.field.enum_field.attr.options = [{"label": "AAA", "value": "aaa"}, {"label": "BBB", "value": "bbb"}]
t.field.enum_field = "bbb"
```

## Rule Trigger Conditions

Trigger conditions are TxScript expressions evaluated in formula-field-like context (globals, no imports).

| Rule | Detail |
|------|--------|
| Must evaluate strictly to `True` | Not just truthy — wrap with `bool()` if needed |
| Line-item field reference triggers per-row evaluation | `field.item_x` evaluates once per row; duplicate actions deduplicated |
| Use `.all_values` for cross-row aggregation | `sum(field.item_amount.all_values)` |

## Deploying as Serverless Hook

Pass the TxScript source code via `config={"source": "<code>"}` — auto-renamed to `config.code`.

## Testing Serverless Hooks

| Rule | Detail |
|------|--------|
| Annotation required | `annotation_content` and `annotation_status` events need an annotation |
| Before calling `test_hook` | `search(query={"entity": "annotation", "queue_id": <queue_id>})` to check if annotations exist on the hook's queues |
| No annotations found | Pass an annotation URL from another queue via `annotation` parameter, or upload a document first |

## Critical Constraints

| Constraint | Detail |
|------------|--------|
| Never use `is None` | Fields evaluate to `None`-like but are not `None`. Use `is_empty()` / `is_set()` |
| Round floats for equality | `round(x, 2) == round(y, 2)` — floating-point equality is unreliable |
| No `return` in formula fields | Last expression is the output |
| Always return `t.hook_response()` in serverless | Omitting causes silent failures |
| Enable Schemas sideload for serverless TxScript | Required for `TxScript.from_payload()` to work |
| Formula field char limit | 2000 characters |
| Serverless timeout | 60 seconds max |
| Formula field values may be stale | If inputs modified in same TxScript context, recomputed after evaluation finishes |

## Common Patterns

```python
# Date arithmetic
field.date_issue + timedelta(days=14)

# Conditional discount
field.amount_total * 0.8 if field.amount_total > 20000 else field.amount_total

# Fallback chain
default_to(default_to(field.amount_total, field.amount_total_base), sum(default_to(field.item_amount_total.all_values, 0)))

# Sum check with warning
line_items_sum = sum(default_to(field.item_amount_total.all_values, 0))
if round(line_items_sum, 2) != round(field.amount_total, 2):
    show_warning("Sum mismatch", field.amount_total)

# Per-row validation
for row in field.line_items:
    if is_set(row.item_amount_total) and row.item_amount_total < 0:
        show_error("Negative amount", row.item_amount_total)

# Distribute header value to line items
if is_set(field.item_order_id):
    field.item_order_id
else:
    field.order_id

# Regex cleanup
substitute(r"[^a-z0-9]", "", field.sender_vat_id, flags=re.IGNORECASE)
```
