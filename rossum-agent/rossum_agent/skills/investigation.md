---
name: Document Investigation
description: systematically investigate document processing issues — trace annotations through hooks, match failures, automation blocks, and export errors
---

# Document Investigation Skill

**Goal**: Diagnose why a document was processed incorrectly — wrong matches, automation blocks, hook errors, export failures, or unexpected field values.

## Input Parsing

Users provide document references in various formats. Extract the annotation ID first — it's the universal key.

| Input format | How to extract annotation_id |
|---|---|
| `https://*.rossum.app/document/{id}` | `{id}` is the annotation_id |
| `https://elis.rossum.ai/document/{id}` | `{id}` is the annotation_id |
| `https://...?annotation={id}&hook={hid}` | `{id}` = annotation_id, `{hid}` = hook_id |
| `document 12345` or `annotation 12345` | `12345` is the annotation_id |

Rossum UI uses `/document/{id}` but the ID is an **annotation ID**. Never use `entity="document"` — always `entity="annotation"`.

## Investigation Workflow

### Phase 1: Context Gathering

Fetch these three in parallel:

```
get(entity="annotation", entity_id=<id>)
get_annotation_content(<id>)
get(entity="queue", entity_id=<queue_id>)  # queue_id from annotation
```

From the annotation, extract:

| Field | Why |
|---|---|
| `status` | Current state (e.g. `to_review`, `exported`, `rejected`) |
| `queue` | Queue URL → queue_id |
| `schema` | Schema URL → schema_id |
| `modifier` / `modified_by` | Last editor |
| `automated` | Whether automation was attempted |
| `automation_blockers` | What prevented automation (if any) |
| `relations` | Linked POs, credit notes, etc. |

### Phase 2: Hook Log Analysis

Search hook logs for the annotation:

```
search(query={"entity": "hook_log", "annotation_id": <id>})
```

Narrow with filters when needed:

| Filter | When to use |
|---|---|
| `hook_id` | Investigating a specific hook |
| `log_level: ["ERROR", "WARNING"]` | Looking for failures |
| `status_code` | HTTP error codes (4xx, 5xx) |
| `timestamp_after` / `timestamp_before` | Time-scoped investigation |
| `search` | Full-text search in log content |

Hook logs contain request/response payloads. Extract key data with `run_jq`:

```
# Extract error messages from hook log results
run_jq('[.[] | {hook: .hook_id, level: .log_level, status: .status_code, message: .response_data.messages // .response_data.error // ""}]', <hook_logs>)

# Get hook response payload for a specific log entry
run_jq('.[0].response_data', <hook_logs>)
```

### Phase 3: Root Cause Analysis

Choose the investigation path based on the symptom:

| Symptom | Investigation Path |
|---|---|
| **Matching failure** | Check PO/vendor relations → hook log response → matching criteria vs extracted values |
| **Automation blocked** | Check `automation_blockers` → trace each blocker source (formula error, low score, extension, business rule) |
| **Hook error** | Get hook config → check hook log error → trace code/config issue |
| **Export failure** | Check export hook logs → look for post-export hook failures (auth, timeout) |
| **Wrong field value** | Compare annotation content value vs expected → check formula/hook that writes the field |
| **Document stuck** | Check status + modifier → look for pending hooks or blocked transitions |

### Phase 4: Report

Present findings in this structure:

```
## Investigation: [Annotation ID]

**Root cause**: [One sentence]

| Aspect | Detail |
|---|---|
| Document | [annotation_id], queue [name] |
| Status | [current status] |
| Issue | [what went wrong] |
| Cause | [why it happened] |
| Evidence | [key data points — field values, hook log excerpts, config references] |

**Recommendation**: [what to fix or next step]
```

## Common Investigation Patterns

### Matching Failures (PO, Vendor, MDH)

The most frequent investigation type. Matching hooks compare extracted values against datasets or PO data.

1. Get the annotation content and identify the relevant extracted field values
2. Search hook logs for the matching hook on this annotation
3. Extract the hook response to see what was matched (or why not)
4. For MDH matching: load the `master-data-hub` skill and search the dataset for the expected record
5. Compare extracted values against dataset/PO values — check case, whitespace, normalization

Common root causes:

| Cause | How to confirm |
|---|---|
| JMESPath expression returns null | Hook config references a field path that doesn't exist or is null in the data |
| Subsidiary/company filter excludes match | Dataset record exists but company code doesn't match |
| Value normalization mismatch | Extracted "DE 811234567" vs dataset "DE811234567" |
| Dataset record missing or stale | `search_dataset` returns no results for the expected key |
| Matching criteria too strict | Exact match required but values have minor differences |

### Automation Blockers

When a document should have been automated but wasn't:

1. Check `automation_blockers` on the annotation (via `get` or sideload)
2. For each blocker, trace the source:

| Blocker type | How to trace |
|---|---|
| `low_score` | Field confidence below threshold — check `get_automation_current_stats` |
| `error_message` | Formula field producing an error — check formula code via schema |
| `no_value` | Required field has no extracted value — check document content |
| `business_rule` | Rule triggered a blocker — check rules on the schema |
| `extension` | Hook called `automation_blocker()` — check hook logs for which hook and why |

### Hook Errors

When a hook fails or produces unexpected results:

1. Get the hook: `get(entity="hook", entity_id=<hook_id>)`
2. Search hook logs: `search(query={"entity": "hook_log", "hook_id": <hook_id>, "annotation_id": <ann_id>})`
3. Check the error:

| Error pattern | Likely cause |
|---|---|
| Status 400 | Bad request — malformed payload, invalid API call in hook code |
| Status 401/403 | Auth failure — expired token_owner, wrong permissions |
| Status 422 | Validation error — hook tried to set invalid value |
| Status 500 | Internal error — runtime exception in hook code |
| Status 504 / timeout | Hook exceeded 60s timeout |
| `"error_message"` in response | Hook intentionally signaled an error via `show_error()` |

### Export Failures

When export fails or produces unexpected results:

1. Search hook logs for export event hooks: `search(query={"entity": "hook_log", "annotation_id": <id>, "search": "export"})`
2. Check for post-export hooks that failed (e.g., writing back relations, updating external systems)
3. Common: export succeeded externally but a post-export API call got 401 (token expired)

## Useful jq Recipes

```
# Extract a specific field value from annotation content
[.. | objects | select(.schema_id == "amount_total")] | .[0].content.value

# List all fields with their values (flat view)
[.. | objects | select(.schema_id != null and .content != null)] | map({id: .schema_id, value: .content.value}) | sort_by(.id)

# Extract line item table as rows
[.. | objects | select(.schema_id == "line_items")] | .[0].children | map(.children | map({(.schema_id): .content.value}) | add)

# Find fields with error messages
[.. | objects | select(.content.value != null and (.content.value | tostring | test("error|warning"; "i")))]

# Extract automation blockers from annotation
.automation_blockers // []

# Summarize hook logs by status
group_by(.log_level) | map({level: .[0].log_level, count: length})
```

## Constraints

| Rule | Detail |
|---|---|
| Hook log retention | 7 days max — older logs are unavailable |
| Hook log page size | Max 100 per search call — use time filters to narrow |
| Read-only investigation | Investigation itself never modifies data — only reads |
| Annotation content file | `get_annotation_content` saves to a file — use the returned path with `run_jq` |

## Cross-Reference

- Matching issues → `master-data-hub` and `lookup-fields` skills for dataset exploration
- Hook debugging → `hooks` skill for hook configuration details
- Automation setup → `automation-setup` skill for threshold analysis
- Customer communication → `customer-email` skill to draft findings email
