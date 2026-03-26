---
name: Rules & Actions
description: create validation rules with TxScript conditions and actions
---

# Rules & Actions Skill

**Goal**: Translate user-described validations into Rossum rules via `execute_python` helper → `create_rule`.

## Creating Rules

Always use `execute_python` with `suggest_rule` to generate rules — never hand-write trigger conditions or actions.

```python
result = suggest_rule(
    user_query='Show error on amount_total when >= 400. Message: "Total exceeds 400."',
    queue_id=2519495,
)
```

Then apply immediately with `create_rule` — no confirmation needed.

## Testing Rules

To preview which actions would trigger, call `execute_python` with `evaluate_rules(queue_id, annotation_id, schema_rules)`. Requires an existing annotation — if none exist, upload test documents first via `generate_mock_pdf` + `upload_document`.

## Constraints

| Constraint | Detail |
|------------|--------|
| No hand-written rules | Always generate via `suggest_rule` |
| One rule per check | One `suggest_rule` + one `create_rule` per independent validation. The API allows at most one action of each type per rule — multiple checks require separate rules. |
| Concise `user_query` | Field, condition, error message — one sentence |
| `queue_ids` required | Scope every rule to at least one queue |
