# Automation Setup Skill

**Goal**: Analyze, project, and configure automation thresholds for document processing queues.

All functions below are available inside `execute_python`.

## Concepts

| Term | Meaning |
|------|---------|
| Automation rate | % of documents processed without human review |
| Touchless rate | % of documents processed without any human touch |
| Error rate | Estimated % of incorrect field extractions |
| Confidence threshold | Per-field minimum AI confidence score; below it the field is flagged for review |
| Blocker | Reason a document was not automated (low_score, error_message, no_value, business_rule, extension) |

## Workflow

1. **Assess current state** → `get_automation_current_stats(queue_id=...)`
2. **Run what-if projections** → `get_automation_projections(queue_id=..., fields=[...])`
3. **Review history** → `list_automation_targets(queue_id=...)`
4. **Apply targets** → `save_automation_target(queue_id=..., ...)`

## Functions

### get_automation_current_stats

```python
result = get_automation_current_stats(queue_id=12345)
```

Returns:
- `estimated_error_rate` — overall queue error rate
- `document_automation_rate`, `document_touchless_rate` — headline metrics
- `document_blockers` — list of `{blocker, granularity, document_count}` showing what prevents automation
- `datapoint_statistics` — per-field `{schema_id, blocked_document_counts, estimated_error_rate, confidence_threshold}`
- `document_automation_timeseries`, `estimated_error_rate_timeseries` — daily history

### get_automation_projections

```python
result = get_automation_projections(
    queue_id=12345,
    fields=[
        {"schema_id": "invoice_id", "error_rate_limit": 0.05},
        {"schema_id": "amount_total", "error_rate_limit": 0.02}
    ],
    exclude_blockers=["extension"]  # optional
)
```

Returns `baseline` (current state) and `projections` (projected state after applying the error rate limits). Compare them to show the user what would change.

### list_automation_targets

```python
result = list_automation_targets(queue_id=12345)
```

Returns `results` — list of saved targets with `automation_rate_target`, `error_rate_target`, `datapoint_automation_targets`, `type`, `datetime`.

### save_automation_target

```python
result = save_automation_target(
    queue_id=12345,
    automation_rate_target=0.8,
    error_rate_target=0.05,
    datapoint_automation_targets=[
        {"schema_id": "invoice_id", "error_rate_target": 0.03, "confidence_threshold": 0.9},
        {"schema_id": "amount_total", "error_rate_target": 0.02, "confidence_threshold": 0.95}
    ],
    target_type="automation_assistant_v1"  # or "legacy_thresholds"
)
```

## Constraints

| Rule | Detail |
|------|--------|
| Queue must have documents | Stats/projections require processed documents to compute meaningful metrics |
| error_rate_limit range | 0.0–1.0 (float); lower = stricter = fewer auto-approved documents |
| confidence_threshold range | 0.0–1.0 (float); higher = stricter |
| Projections are read-only | They show what *would* happen; use `save_automation_target` to apply |
| Target type | `automation_assistant_v1` for new setups; `legacy_thresholds` for backward compat |

## Typical Analysis Pattern

1. Fetch current stats to understand baseline automation rate
2. Identify top blockers (fields with most `low_score` or `error_message` blocked documents)
3. Run projections with relaxed error rate limits on those fields
4. Present the trade-off: projected automation gain vs acceptable error increase
5. Save the target once the user confirms

## Related Skills

- `python-execution` — shared Python helper reference
