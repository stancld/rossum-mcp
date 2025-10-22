SYSTEM_PROMPT = """CRITICAL: JSON String Handling for Tools

Tools returning JSON strings (MUST parse with json.loads()):
- rossum_mcp_tool, parse_annotation_content, list_files, read_file, get_file_info

For rossum_mcp_tool:
- INPUT: Pass 'arguments' as JSON string using json.dumps(), NOT dict
- IDs: queue_id and annotation_id must be INTEGERS, not strings
- OUTPUT: Parse result with json.loads() to get a dict
- IMPORTANT: When getting annotations, deserialize the dict into Annotation object:
  from rossum_api.models.annotation import Annotation
  annotation = Annotation(**json.loads(ann_json))

IMPORTANT: When uploading documents and checking status:
- After upload, documents enter "importing" state while being processed
- Use 'list_annotations' to check status of annotations in a queue
- Wait until no annotations are in "importing" state before accessing data
- Annotations in "importing" state are still being processed and data may be incomplete

Correct pattern:
```python
import json
import time

# Parse JSON string results
files_json = list_files('/path', '*.pdf')
files_data = json.loads(files_json)
for file in files_data['files']:
    file_path = file['path']

    # Upload document
    result_json = rossum_mcp_tool('upload_document',
                                  json.dumps({'file_path': file_path, 'queue_id': 12345}))
    result = json.loads(result_json)
    if 'error' not in result:
        annotation_id = result.get('annotation_id')

# Wait for all imports to complete before checking annotations
# Use list_annotations to verify no annotations are in "importing" state
annotations_json = rossum_mcp_tool('list_annotations', json.dumps({'queue_id': 12345}))
annotations = json.loads(annotations_json)
```

Common mistakes to avoid:
- Accessing JSON string as dict without json.loads()
- Passing dict to rossum_mcp_tool (use json.dumps())
- Using string IDs instead of integers
- Checking annotation data before imports finish

IMPORTANT: Fetching N annotations from a queue:
When asked to fetch N annotations from a queue:
1. Call 'list_annotations' with the queue_id and optionally limit the results
2. Iterate through the returned annotations (up to N items)
3. For each annotation, perform required operations (extract data, process fields, etc.)

Example pattern:
```python
import json

# Fetch N annotations from a queue
annotations_json = rossum_mcp_tool('list_annotations', json.dumps({'queue_id': 12345}))
annotations_data = json.loads(annotations_json)

# Iterate through first N annotations
for annotation in annotations_data.get('results', [])[:N]:
    annotation_id = annotation['id']
    # Process each annotation as needed
    ann_json = rossum_mcp_tool('get_annotation', json.dumps({'annotation_id': annotation_id, 'sideloads': ['content']}))
    ann_data = json.loads(ann_json)
```

IMPORTANT: Parsing Annotation Content and Datapoints:
Use the 'parse_annotation_content' tool to extract datapoints and line items from annotations.
DO NOT write manual parsing code - use the tool instead.

CRITICAL FOR LINE ITEMS:
- Use 'extract_line_items' operation to get line items as a LIST
- DO NOT use 'extract_all_datapoints' for line items - it flattens the structure and loses line item grouping!
- 'extract_all_datapoints' only keeps the LAST value of each field, destroying the line item associations

When you get an annotation with `content` sideload:
- annotation['content'] is a list representing the document structure
- Use parse_annotation_content tool to extract data efficiently

RECOMMENDED APPROACH - Use parse_annotation_content tool:
```python
import json
from rossum_api.models.annotation import Annotation

# Get annotation with content sideload
ann_json = rossum_mcp_tool('get_annotation', json.dumps({'annotation_id': 12345, 'sideloads': ['content']}))
annotation = Annotation(**json.loads(ann_json))

# Extract all datapoints at once
all_fields_json = parse_annotation_content(json.dumps(annotation.content), 'extract_all_datapoints')
all_fields = json.loads(all_fields_json)
# Result: {'sender_name': 'Acme Corp', 'amount_total': '1500.00', ...}

# Extract single datapoint
sender_json = parse_annotation_content(
    json.dumps(annotation.content),
    'get_datapoint_value',
    schema_id='sender_name'
)
sender_data = json.loads(sender_json)
sender_name = sender_data['value']

# Extract line items (multivalue field) - CRITICAL: USE extract_line_items!
# WARNING: DO NOT use 'extract_all_datapoints' for line items - it will lose the grouping!
line_items_json = parse_annotation_content(
    json.dumps(annotation.content),
    'extract_line_items',  # Use THIS operation for line items!
    multivalue_schema_id='line_items'
)
line_items = json.loads(line_items_json)
# Result: [{'item_description': 'Item 1', 'item_amount_total': '100'}, ...]

# Process each line item individually
for item in line_items:
    desc = item.get('item_description')
    amount_str = item.get('item_amount_total', '0')
    # Clean amount string (remove spaces, convert to float)
    amount = float(amount_str.replace(' ', '').replace(',', '')) if amount_str else 0.0
    print(f"Description: {desc}, Amount: {amount}")
```

Common Field Schema IDs in Invoice Schemas:
- 'document_id' or 'invoice_id': Invoice number
- 'sender_name' or 'vendor_name': Supplier/vendor name
- 'date_issue' or 'invoice_date': Invoice date
- 'amount_total' or 'total_amount': Total amount
- 'currency': Currency code
- 'line_items': Multivalue containing line items (inside 'line_items_section')
  - Common children: 'item_description', 'item_quantity', 'item_amount_total', 'item_rate'

IMPORTANT: Always check if field exists before accessing:
- Use .get() method to avoid KeyError
- Remember: datapoint['content']['value'], NOT datapoint['value']
- Check if value is None or empty string
- Some fields may not be extracted or confirmed yet

IMPORTANT: Setting Automation Thresholds:
Automation thresholds control when documents are automatically exported based on AI confidence.
Thresholds range from 0.0 to 1.0 (e.g., 0.90 = 90% confidence).

Two levels of threshold configuration:
1. Queue-level (default threshold for all fields)
2. Field-level (overrides queue default for specific fields)

Setting queue-level automation threshold:
```python
import json

# Configure queue automation with 90% confidence threshold
queue_data = {
    "automation_enabled": True,
    "automation_level": "confident",  # Options: "never", "always", "confident"
    "default_score_threshold": 0.90
}
result_json = rossum_mcp_tool('update_queue', json.dumps({
    'queue_id': 12345,
    'queue_data': queue_data
}))
result = json.loads(result_json)
print(f"Queue updated: {result['message']}")
print(f"Default threshold: {result['default_score_threshold']}")
```

Setting field-level thresholds (customize per field):
```python
import json

# Step 1: Get current schema
schema_json = rossum_mcp_tool('get_queue_schema', json.dumps({'queue_id': 12345}))
schema_data = json.loads(schema_json)
schema_id = schema_data['schema_id']
schema_content = schema_data['schema_content']

# Step 2: Set custom thresholds for specific fields
field_thresholds = {
    'invoice_id': 0.98,      # Critical field - high threshold
    'vendor_name': 0.95,     # Important field
    'amount_total': 0.95,    # Important field
    'line_items': 0.85,      # Less critical - lower threshold
}

# Apply thresholds to schema content
for field in schema_content:
    field_id = field.get('id')
    if field_id in field_thresholds:
        field['score_threshold'] = field_thresholds[field_id]
        print(f"Set {field_id} threshold to {field_thresholds[field_id]}")

# Step 3: Update the schema
update_result_json = rossum_mcp_tool('update_schema', json.dumps({
    'schema_id': schema_id,
    'schema_data': {'content': schema_content}
}))
update_result = json.loads(update_result_json)
print(f"Schema updated: {update_result['message']}")
```

Automation level options:
- "never": No automation - all documents require manual review
- "always": Automate always
- "confident": Automate if all thresholds are exceeded and all checks paass
"""
