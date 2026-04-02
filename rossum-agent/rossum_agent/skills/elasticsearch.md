---
name: Elasticsearch
description: query Elasticsearch indices for datapoint statistics and annotation analytics
---

# Elasticsearch Skill

**Goal**: Compute datapoint-level statistics and annotation analytics from Elasticsearch indices.

## Annotation Search Index

Index alias: `elis_ann_alias_*`

| Field | Path | Notes |
|-------|------|-------|
| Queue ID | `queue_id` | Top-level integer |
| Status | `status` | Top-level (`importing`, `to_review`, `confirmed`, `exported`) |
| Created | `created_at` | ISO 8601 timestamp |
| Exported | `exported_at` | ISO 8601 timestamp |
| Organization | `organization_id` | Top-level integer |
| Datapoints | `datapoints` | **Nested** - must use nested queries/aggs |

### Datapoint Fields (nested under `datapoints`)

| Field | Description |
|-------|-------------|
| `datapoints.schema_id` | Field identifier (e.g., `currency`, `amount_total`, `sender_name`) |
| `datapoints.text` | Text value - always present, use `.keyword` subfield for exact match |
| `datapoints.number` | Numeric value - only if convertible from text |
| `datapoints.date` | Date value - only if convertible from text |

## Query Patterns

### Top values for a field (terms aggregation)

```json
{
  "size": 0,
  "query": {"bool": {"filter": [{"terms": {"queue_id": [123]}}]}},
  "aggs": {
    "dp": {
      "nested": {"path": "datapoints"},
      "aggs": {
        "filtered": {
          "filter": {"term": {"datapoints.schema_id": "currency"}},
          "aggs": {"result": {"terms": {"field": "datapoints.text.keyword", "size": 20}}}
        }
      }
    }
  }
}
```

### Numeric statistics (min/max/avg/sum)

```json
{
  "size": 0,
  "query": {"bool": {"filter": [{"terms": {"queue_id": [123]}}]}},
  "aggs": {
    "dp": {
      "nested": {"path": "datapoints"},
      "aggs": {
        "filtered": {
          "filter": {"term": {"datapoints.schema_id": "amount_total"}},
          "aggs": {"result": {"stats": {"field": "datapoints.number"}}}
        }
      }
    }
  }
}
```

### Find documents by datapoint value

```json
{
  "query": {
    "bool": {
      "must": [
        {
          "nested": {
            "path": "datapoints",
            "query": {
              "bool": {
                "must": [
                  {"term": {"datapoints.schema_id": "invoice_id"}},
                  {"match": {"datapoints.text": "INV-2025-001"}}
                ]
              }
            }
          }
        }
      ]
    }
  }
}
```

### Multi-field filter (combine datapoint conditions)

```json
{
  "query": {
    "bool": {
      "must": [
        {
          "nested": {
            "path": "datapoints",
            "query": {"bool": {"must": [
              {"term": {"datapoints.schema_id": "currency"}},
              {"match": {"datapoints.text": "GBP"}}
            ]}}
          }
        },
        {
          "nested": {
            "path": "datapoints",
            "query": {"bool": {"must": [
              {"term": {"datapoints.schema_id": "sender_name"}},
              {"match": {"datapoints.text": "Acme"}}
            ]}}
          }
        }
      ]
    }
  }
}
```

## Constraints

| Rule | Detail |
|------|--------|
| Always use alias | `elis_ann_alias_*`, never raw index names |
| Nested queries required | Datapoint fields require `nested` path `"datapoints"` |
| `.keyword` for exact match | `datapoints.text.keyword` for `term`/`terms` aggs |
| `size: 0` for aggs | When only aggregations are needed |
| Empty text = null | `datapoints.text == ""` means null for number/date fields |
| No `organization_id` | Injected automatically — never include it |
