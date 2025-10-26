# Rossum MCP Server

<div align="center">

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-mcp/)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![Rossum SDK](https://img.shields.io/badge/Rossum-SDK-orange.svg)](https://github.com/rossumai/rossum-sdk)
[![codecov](https://codecov.io/gh/stancld/rossum-mcp/branch/master/graph/badge.svg)](https://codecov.io/gh/stancld/rossum-mcp)

</div>

A Model Context Protocol (MCP) server and AI agent toolkit for intelligent document processing with Rossum. Upload documents, extract data with AI, and create visualizations - all through simple conversational prompts.

## What Can You Do?

### Example 1: Bulk Processing & Visualization

```md
1. Upload all invoices from `/Users/daniel.stancl/projects/rossum-mcp/examples/data` folder to Rossum to the queue 3901094.
    - Do not include documents from `knowledge` folder.
2. Once you send all annotations, wait for a few seconds.
3. Then, start checking annotation status. Once all are imported, return a list of all annotations_urls
4. Fetch the schema for the target queue.
5. Identify the schema field IDs for:
    - Line item description field
    - Line item total amount field
6. Retrieve all annotations in 'to_review' state from queue 3901094
7. For each document:
    - Extract all line items
    - Create a dictionary mapping {item_description: item_amount_total}
    - If multiple line items share the same description, sum their amounts
    - Print result for each document
8. Aggregate across all documents: sum amounts for each unique description
9. Return the final dictionary: {description: total_amount_across_all_docs}
10. Using the retrieved data, generate bar plot displaying revenue by services. Sort it in descending order. Store it interactive `revenue.html`.
```

<div align="center">
  <img src="revenue.png" alt="Revenue by Services Chart" width="700">
</div>

See the [complete example](examples/PROMPT.md) showing how a single prompt processed 30 invoices and generated this chart.

### Example 2: Queue Setup with Knowledge Warmup

Create a new queue, warm it up with training documents, and test automation performance:

```md
1. Create a new queue in the same namespace as queue `3904204`.
2. Set up the same schema field as queue `3904204`.
3. Update schema so that everything with confidence > 90% will be automated.
4. Rename the queue to: MCP Air Waybills
5. Copy the queue knowledge from `3904204`.
6. Return the queue status to check the queue status.
7. Upload all documents from `examples/data/splitting_and_sorting/knowledge/air_waybill` to the new queue.
8. Wait until all annotations are processed.
9. Finally, return queue URL and an automation rate (exported documents).
```

**Result:**
```json
{
  "queue_url": "https://api.elis.rossum.ai/v1/queues/3920572",
  "queue_id": 3920572,
  "queue_name": "MCP Air Waybills",
  "total_documents": 30,
  "exported_documents": 26,
  "to_review_documents": 4,
  "automation_rate_percent": 86.7
}
```

The agent automatically creates the queue, uploads documents, monitors processing, and calculates automation performance - achieving 86.7% automation rate from just 30 training documents.

### Example 3: Multi-Queue Setup with Sorting Engine

Set up multiple queues with training data, create a sorting engine, and test classification performance:

```md
1. Create three new queues in workspace `1777693` - Air Waybills, Certificates of Origin, Invoices.
2. Set up the schema with a single enum field on each queue with a name Document type (`document_type`).
3. Upload documents from folders air_waybill, certificate_of_origin, invoice in `examples/data/splitting_and_sorting/knowledge` to corresponding queues.
4. Annotate all uploaded documents with a correct Document type, and confirm the annotation.
    - Beware document types are air_waybill, invoice and certificate_of_origin (lower-case, underscores).
5. Create a new engine in organization `1`, with type = 'extractor'.
6. Configure engine training queues to be - Air Waybills, Certificates of Origin, Invoices.
    - DO NOT copy knowledge.
    - Update Engine object.
7. Create a new schema with a single enum field `Document type`.
8. Create a new queue with the created engine and schema in the same workspace called: Inbox.
9. Upload documents from folders air_waybill, certificate_of_origin, invoice in `examples/data/splitting_and_sorting/knowledge` to inbox queues.
10. Based on the file names and predicted values, generate a pie plot with correct/wrong for each document type.
```

**Result:**

```md
✅ Step 10: Generated accuracy reports
  • Overall Accuracy: 100.0% (90/90)

  Accuracy by document type:
    • air_waybill: 100.0% (30/30)
    • certificate_of_origin: 100.0% (30/30)
    • invoice: 100.0% (30/30)

📊 Generated Charts:
  • output/air_waybill_accuracy.html
  • output/certificate_of_origin_accuracy.html
  • output/invoice_accuracy.html
  • output/overall_accuracy_by_type.html

================================================================================
🎉 ALL TASKS COMPLETED SUCCESSFULLY!
================================================================================

📝 Key Findings:
  • The engine achieved 100% accuracy on all document types
  • All 90 test documents were correctly classified
  • The training data (88 confirmed annotations) was sufficient
  • No misclassifications occurred

**Reached max steps.**
```

## Installation

**Prerequisites**: Python 3.10+, Rossum account with API credentials

This repository contains two packages:
- **rossum_mcp**: MCP server for Rossum API interactions
- **rossum_agent**: AI agent with data manipulation and visualization tools

### Quick Start

```bash
git clone https://github.com/stancld/rossum-mcp.git
cd rossum-mcp

# Install both packages with all features
pip install -e "rossum_mcp[all]" -e "rossum_agent[all]"

# Set up environment variables
export ROSSUM_API_TOKEN="your-api-token"
export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
```

For individual package installation or other options, see [rossum_mcp/README.md](rossum_mcp/README.md) and [rossum_agent/README.md](rossum_agent/README.md).

## Usage

### MCP Server with Claude Desktop

Configure Claude Desktop to use the MCP server:

```json
{
  "mcpServers": {
    "rossum": {
      "command": "python",
      "args": ["/path/to/rossum-mcp/rossum_mcp/server.py"],
      "env": {
        "ROSSUM_API_TOKEN": "your-api-token",
        "ROSSUM_API_BASE_URL": "https://api.elis.rossum.ai/v1"
      }
    }
  }
}
```

Or run standalone: `rossum-mcp`

### AI Agent

```bash
# CLI interface
rossum-agent

# Streamlit web UI
streamlit run rossum_agent/app.py
```

The agent includes file system tools, plotting capabilities, and Rossum integration. See [examples/](examples/) for complete workflows.

## MCP Tools

The MCP server provides 17 tools organized into three categories:

**Document Processing**
- `upload_document` - Upload documents for AI extraction
- `get_annotation` - Retrieve extracted data and status
- `list_annotations` - List all annotations with filtering
- `start_annotation` - Start annotation for field updates
- `bulk_update_annotation_fields` - Update field values with JSON Patch
- `confirm_annotation` - Confirm and finalize annotations

**Queue & Schema Management**
- `get_queue`, `get_schema`, `get_queue_schema` - Retrieve configuration
- `get_queue_engine` - Get engine information
- `create_queue`, `create_schema` - Create new queues and schemas
- `update_queue`, `update_schema` - Configure automation thresholds

**Engine Management**
- `create_engine` - Create extraction or splitting engines
- `update_engine` - Configure learning and training queues
- `create_engine_field` - Define engine fields and link to schemas

For detailed API documentation, parameters, and workflows, see the [full documentation](https://stancld.github.io/rossum-mcp/).

## Documentation

- [Full Documentation](https://stancld.github.io/rossum-mcp/) - Complete API reference and guides
- [MCP Server](rossum_mcp/README.md) - Server setup and configuration
- [AI Agent](rossum_agent/README.md) - Agent features and interfaces
- [Examples](examples/README.md) - Working examples and tutorials

## Resources

- [Rossum API](https://elis.rossum.ai/api/docs/) - Official API documentation
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP specification
- [Rossum SDK](https://github.com/rossumai/rossum-sdk) - Python SDK
- [Smolagents](https://github.com/huggingface/smolagents) - Agent framework

## License

MIT License - see [LICENSE](LICENSE) for details. Contributions welcome via issues and pull requests.
