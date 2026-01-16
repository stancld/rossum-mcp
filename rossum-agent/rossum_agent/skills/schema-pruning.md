# Schema Pruning Skill

**Goal**: Remove unwanted fields from schema in one call.

## Tool

```
prune_schema_fields(schema_id=12345, fields_to_keep=["invoice_number", "invoice_date", "total_amount"])
```

Returns `{removed_fields: [...], remaining_fields: [...]}`.

## Behavior

- Specify leaf field IDs only
- Parent containers (sections, multivalues, tuples) preserved automatically
- Sections with no remaining children are removed automatically (API rejects empty sections)
- Alternative: use `fields_to_remove` to remove specific fields instead

## Cross-Reference

- Adding fields after pruning: load `schema-patching` skill
- Queue creation: load `organization-setup` skill
