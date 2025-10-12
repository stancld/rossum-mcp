# Plotting Tool

Data visualization tool for the Rossum Agent supporting interactive (Plotly) and static (Matplotlib) charts.

📚 **[Full Documentation](../../docs/build/html/plotting.html)** - Complete guide with examples and API reference

## Quick Start

```bash
pip install -r requirements.txt
python quick_demo.py
```

## Features

- **Chart Types**: Bar, horizontal bar, line, pie, scatter, heatmap
- **Interactive (Plotly)**: Hover, zoom, pan - outputs HTML
- **Static (Matplotlib)**: Publication-ready PNG/PDF
- **Color Schemes**: Viridis, Plasma, Pastel, Bold, and more
- **Smart Defaults**: Automatic sorting, value labels, formatting

## Basic Usage

```python
import json
from plot_tools import plot_data

# Your data (e.g., aggregated invoice line items)
data = {
    'API Development': 26992.25,
    'System Design': 59209.98,
    'DevOps': 21064.31,
}

# Create chart
result = plot_data(
    data_json=json.dumps(data),
    chart_type='bar',
    title='Revenue by Service',
    y_label='Revenue ($)',
    output_path='revenue.html',
    interactive=True,
    color_scheme='viridis'
)

# Check result
result_dict = json.loads(result)
print(f"Status: {result_dict['status']}")
print(f"File: {result_dict['output_path']}")
```

## Chart Types

| Type | Best For | Example |
|------|----------|---------|
| `bar` | Comparing categories | `chart_type='bar'` |
| `horizontal_bar` | Long labels | `chart_type='horizontal_bar'` |
| `line` | Trends, time series | `chart_type='line'` |
| `pie` | Proportions | `chart_type='pie'` |
| `scatter` | Correlations | `chart_type='scatter'` |
| `heatmap` | Matrix data | `chart_type='heatmap'` |

## API Reference

```python
def plot_data(
    data_json: str,                    # JSON string (use json.dumps())
    chart_type: str = "bar",           # Chart type
    title: str = "Data Visualization", # Chart title
    x_label: str | None = None,        # X-axis label
    y_label: str | None = None,        # Y-axis label
    output_path: str = "plot.html",    # Output file
    interactive: bool = True,          # True=HTML, False=PNG
    color_scheme: str = "default",     # Color palette
    sort_values: bool = True,          # Sort data
    sort_descending: bool = True,      # Sort order
    show_values: bool = True,          # Show value labels
    width: int = 1000,                 # Width (px)
    height: int = 600,                 # Height (px)
) -> str:                              # Returns JSON string
```

**Returns:**
```json
{
  "status": "success",
  "output_path": "/path/to/plot.html",
  "chart_type": "bar",
  "interactive": true
}
```

## Color Schemes

- `default` - Modern, balanced
- `viridis` - Colorblind-friendly, scientific
- `plasma` - High contrast
- `pastel` - Soft, professional
- `bold` - Vibrant

## Real-World Example

```python
from rossum_agent_tools import rossum_mcp_tool, parse_annotation_content
from plot_tools import plot_data

# 1. Get annotations
annotations = json.loads(rossum_mcp_tool(
    'list_annotations',
    json.dumps({'queue_id': 12345, 'status': 'exported'})
))

# 2. Aggregate line items
revenue_by_service = {}
for ann in annotations['results']:
    ann_data = json.loads(rossum_mcp_tool(
        'get_annotation',
        json.dumps({'annotation_id': ann['id'], 'sideloads': ['content']})
    ))

    line_items = json.loads(parse_annotation_content(
        json.dumps(ann_data['content']),
        'extract_line_items',
        multivalue_schema_id='line_items'
    ))

    for item in line_items:
        desc = item.get('item_description', 'Unknown')
        amount = float(item.get('item_amount_total', '0').replace(' ', '').replace(',', ''))
        revenue_by_service[desc] = revenue_by_service.get(desc, 0) + amount

# 3. Create visualization
result = plot_data(
    json.dumps(revenue_by_service),
    chart_type='horizontal_bar',
    title='Revenue by Service',
    x_label='Total Revenue ($)',
    output_path='revenue.html',
    color_scheme='viridis'
)
```

## Tips

- **Long labels?** Use `horizontal_bar`
- **Time series?** Set `sort_values=False` to preserve order
- **Web dashboards?** Use `interactive=True` (HTML)
- **Reports/PDFs?** Use `interactive=False` (PNG)
- **Accessibility?** Use `viridis` or `cividis` color schemes

## Testing

```bash
pytest tests/test_plotting_tool.py -v
```

## Dependencies

- plotly>=5.18.0
- kaleido>=0.2.1
- matplotlib>=3.8.0
- seaborn>=0.13.0
- numpy>=1.26.0
