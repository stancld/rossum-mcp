# Master Data Hub Skill

**Goal**: Explore and query Master Data Hub (MDH) datasets to debug matching issues and understand available data.

## When to Use

| Scenario | Use This Skill |
|----------|---------------|
| "What datasets exist?" | Yes — `list_datasets()` |
| "Search this dataset for a vendor" | Yes — `search_dataset(...)` |
| "Why didn't this match?" | Yes — search the dataset, then check lookup field config via `lookup-fields` skill |
| "What columns does this dataset have?" | Yes — `list_datasets()` shows field names per dataset |
| Configure a lookup field | No — use `lookup-fields` skill instead |

## Tools

All MDH helpers are Python functions available inside `execute_python`. Never try to call them as standalone tools.

### list_datasets

Discover all available MDH datasets with their IDs, names, and field schemas.

```python
result = list_datasets()
# Returns: {
#   "status": "success",
#   "count": 5,
#   "datasets": [
#     {"id": "imported-0d652b68-...", "name": "Approved Vendors", "fields": ["Name", "VAT ID", "Address"]},
#     {"id": "imported-a1b2c3d4-...", "name": "Cost Centers", "fields": ["Code", "Description", "Department"]}
#   ]
# }
```

### search_dataset

Query dataset entries directly using MongoDB-style filters. No caching step needed.

**Simple match** (most common — field:value filter):

```python
result = search_dataset(dataset="Approved Vendors", match={"VAT ID": "DE811234567"})
# Returns: {"status": "success", "dataset": "imported-...", "row_count": 1, "rows": [...]}
```

**Regex search** (case-insensitive):

```python
result = search_dataset(
    dataset="Approved Vendors",
    match={"Name": {"$regex": "acme", "$options": "i"}},
)
```

**Multiple conditions**:

```python
result = search_dataset(
    dataset="Approved Vendors",
    match={"Country": "DE", "Status": "Active"},
)
```

**Advanced pipeline** (aggregation, sorting, projection):

```python
result = search_dataset(
    dataset="Approved Vendors",
    pipeline=[
        {"$match": {"Status": "Active"}},
        {"$sort": {"Name": 1}},
        {"$project": {"Name": 1, "VAT ID": 1}},
    ],
    limit=100,
)
```

**Combine match + pipeline** (match is prepended as first `$match` stage):

```python
result = search_dataset(
    dataset="Approved Vendors",
    match={"Country": "DE"},
    pipeline=[{"$sort": {"Name": 1}}],
)
```

**Browse first rows** (no filters):

```python
result = search_dataset(dataset="Approved Vendors", limit=5)
```

### get_lookup_dataset_raw_values + query_lookup_dataset

For bulk analysis with jq (cache-then-query pattern). Use when you need to run multiple queries against the same dataset without repeated HTTP calls.

```python
get_lookup_dataset_raw_values(dataset="Approved Vendors")
columns = query_lookup_dataset(dataset="Approved Vendors", jq_query=".[0] | keys")
sample = query_lookup_dataset(dataset="Approved Vendors", jq_query=".[:3]")
unique_countries = query_lookup_dataset(dataset="Approved Vendors", jq_query='[.[] | ."Country"] | unique')
```

## Debugging MDH Matching

When a user asks "why didn't this match?", follow this sequence:

| Step | Action |
|------|--------|
| 1. Identify the dataset | `list_datasets()` or check the lookup field's `matching.configuration.dataset` |
| 2. Verify data exists | `search_dataset(dataset=..., match={...})` with the expected key values |
| 3. Check column names | Field names in dataset often contain spaces (e.g. `"VAT ID"` not `"vat_id"`) |
| 4. Check value format | Compare the document's extracted value against dataset values — look for case, whitespace, prefix differences |
| 5. Inspect lookup config | Load `lookup-fields` skill to review `matching.configuration.queries` |

## Constraints

| Rule | Detail |
|------|--------|
| Dataset names | `search_dataset` accepts human-readable names (e.g. "Approved Vendors") — automatic resolution to `imported-*` IDs |
| Column names with spaces | Use exact names from `list_datasets()` fields — MDH columns often have spaces |
| Rate limiting | MDH API returns 429 on heavy usage — functions retry automatically |
| Large datasets | Default limit is 50 rows; increase with `limit` param (max 10000) |
| Related skill | Use `lookup-fields` for configuring matching logic, this skill for data exploration |
