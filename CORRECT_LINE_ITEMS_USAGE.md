# Correct Line Items Extraction and Aggregation

## The Problem

If you're seeing results like this:
```python
Document 8624069: {'API Integration Development': 0.0, 'System Architecture Design': 660.15, 'DevOps Automation Setup': 0.0}
```

Where descriptions are correct but amounts are `0.0`, it means you're using the **WRONG** operation.

## ❌ INCORRECT: Using `extract_all_datapoints`

```python
# DON'T DO THIS for line items!
all_fields = parse_annotation_content(
    json.dumps(annotation.content),
    'extract_all_datapoints'  # ❌ This flattens everything!
)
all_data = json.loads(all_fields)

# This only gives you the LAST value of each field:
# {'item_description': 'DevOps Automation Setup', 'item_amount_total': '2782.13'}
# You've lost all other line items!
```

**Why this fails:**
- `extract_all_datapoints` creates a flat dictionary
- If you have 3 line items, all with `item_description` and `item_amount_total`, it keeps only the LAST one
- You lose the grouping/association between description and amount for individual line items

## ✅ CORRECT: Using `extract_line_items`

```python
from collections import defaultdict
import json

# Step 1: Extract line items as a LIST
line_items_json = parse_annotation_content(
    json.dumps(annotation.content),
    'extract_line_items',  # ✅ Use THIS!
    multivalue_schema_id='line_items'
)
line_items = json.loads(line_items_json)

# Now you have a proper list:
# [
#   {'item_description': 'API Integration Development', 'item_amount_total': '2147.29'},
#   {'item_description': 'System Architecture Design', 'item_amount_total': '660.15'},
#   {'item_description': 'DevOps Automation Setup', 'item_amount_total': '2782.13'}
# ]

# Step 2: Aggregate by description
aggregated = defaultdict(float)
for item in line_items:
    desc = item.get('item_description', 'Unknown')
    amount_str = item.get('item_amount_total', '0')

    # IMPORTANT: Clean the amount string (Rossum may return '2 147.29' with spaces)
    try:
        amount = float(amount_str.replace(' ', '').replace(',', ''))
    except (ValueError, AttributeError):
        amount = 0.0

    aggregated[desc] += amount

# Now you have correct results:
# {
#   'API Integration Development': 2147.29,
#   'System Architecture Design': 660.15,
#   'DevOps Automation Setup': 2782.13
# }
```

## Complete Example: Processing Multiple Documents

```python
import json
from collections import defaultdict

# Track aggregation across all documents
total_aggregated = defaultdict(float)

for ann_data in annotation_list:
    annotation_id = ann_data['id']

    # Fetch annotation with content
    ann_json = rossum_mcp_tool(
        'get_annotation',
        json.dumps({'annotation_id': annotation_id, 'sideloads': ['content']})
    )
    annotation = json.loads(ann_json)

    # Extract line items using the CORRECT operation
    line_items_json = parse_annotation_content(
        json.dumps(annotation['content']),
        'extract_line_items',
        multivalue_schema_id='line_items'
    )
    line_items = json.loads(line_items_json)

    # Process this document's line items
    doc_aggregated = defaultdict(float)
    for item in line_items:
        desc = item.get('item_description', 'Unknown')
        amount_str = item.get('item_amount_total', '0')

        # Clean and convert amount
        try:
            amount = float(amount_str.replace(' ', '').replace(',', ''))
        except (ValueError, AttributeError):
            amount = 0.0

        doc_aggregated[desc] += amount
        total_aggregated[desc] += amount

    print(f"Document {annotation_id}: {dict(doc_aggregated)}")

print(f"\nTotal across all documents: {dict(total_aggregated)}")
```

## Key Takeaways

1. **For line items**: Always use `'extract_line_items'` operation
2. **For single fields**: Use `'extract_all_datapoints'` or `'get_datapoint_value'`
3. **Clean numeric values**: Rossum may return amounts with spaces (e.g., `"2 147.29"`)
4. **Handle missing values**: Use `.get()` with defaults and try/except for conversions
