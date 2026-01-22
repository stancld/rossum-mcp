# Rossum Agent Client

<div align="center">

**Python client for Rossum Agent API - AI-powered document processing assistant.**

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-agents/)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI - rossum-agent-client](https://img.shields.io/pypi/v/rossum-agent-client?label=rossum-agent-client)](https://pypi.org/project/rossum-agent-client/)
[![Coverage](https://codecov.io/gh/stancld/rossum-agents/branch/master/graph/badge.svg?flag=rossum-agent-client)](https://codecov.io/gh/stancld/rossum-agents)

[![Rossum API](https://img.shields.io/badge/Rossum-API-orange.svg)](https://github.com/rossumai/rossum-api)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

</div>

## Installation

```bash
uv pip install rossum-agent-client
```

## CLI Usage

The package provides a `rossum-agent-client` command for single-turn interactions:

```bash
# Execute a prompt directly (single-turn conversation)
rossum-agent-client -x "List all queues"

# Read prompt from a markdown file (single-turn conversation)
rossum-agent-client -r prompt.md

# With explicit configuration
rossum-agent-client \
    --agent-api-url https://your-agent-api.example.com \
    --rossum-api-base-url https://elis.rossum.ai/api/v1 \
    --rossum-api-token your-token \
    -x "List all queues"

# Use read-write mode
rossum-agent-client --mcp-mode read-write -x "Create a new queue"
```

Files created by the agent (via `write_file` tool) are automatically downloaded and saved to the current directory.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `ROSSUM_AGENT_API_URL` | Agent API URL |
| `ROSSUM_API_BASE_URL` | Rossum API base URL |
| `ROSSUM_API_TOKEN` | Rossum API authentication token |
| `ROSSUM_MCP_MODE` | MCP mode: `read-only` (default) or `read-write` |

## Quick Start

```python
from rossum_agent_client import RossumAgentClient

# Initialize client
client = RossumAgentClient(
    agent_api_url="https://your-agent-api.example.com",
    rossum_api_base_url="https://elis.rossum.ai/api/v1",
    token="your-rossum-api-token",
)

# Create a chat session
chat = client.create_chat(mcp_mode="read-only")
print(f"Created chat: {chat.chat_id}")

# Send a message and stream the response
last_content = ""
for event in client.send_message_stream(chat.chat_id, "List all queues"):
    if event.type == "tool_start":
        print(f"\n[Tool] {event.tool_name}")
    elif event.type == "final_answer":
        # Print only new content (events contain cumulative text)
        print(event.content[len(last_content):], end="", flush=True)
        last_content = event.content
    elif event.type == "done":
        print(f"\n({event.input_tokens} in, {event.output_tokens} out)")
```

## Async Usage

```python
import asyncio
from rossum_agent_client import AsyncRossumAgentClient

async def main():
    async with AsyncRossumAgentClient(
        agent_api_url="https://your-agent-api.example.com",
        rossum_api_base_url="https://elis.rossum.ai/api/v1",
        token="your-rossum-api-token",
    ) as client:
        # Create chat
        chat = await client.create_chat()

        # Stream response
        async for event in client.send_message_stream(chat.chat_id, "Hello!"):
            print(event)

asyncio.run(main())
```

## API Reference

### Client Initialization

```python
RossumAgentClient(
    agent_api_url: str,         # Agent API URL
    rossum_api_base_url: str,   # Rossum API base URL (e.g., https://elis.rossum.ai/api/v1)
    token: str,                 # Rossum API authentication token
    timeout: float = 300.0      # Request timeout in seconds
)
```

### Methods

#### Health Check

```python
health = client.health_check()
# Returns: HealthResponse(status="healthy", redis_connected=True, version="1.0.0dev")
```

#### Chat Management

```python
# Create a new chat
chat = client.create_chat(mcp_mode="read-only")  # or "read-write"

# List all chats
chats = client.list_chats(limit=50, offset=0)

# Get chat details
chat_detail = client.get_chat(chat_id)

# Delete a chat
result = client.delete_chat(chat_id)
```

#### Messages

```python
# Send message and stream response (recommended)
last_content = ""
for event in client.send_message_stream(chat_id, "Your message"):
    match event.type:
        case "tool_start":
            print(f"\n[Tool] {event.tool_name}")
        case "final_answer":
            # Print only new content (events contain cumulative text)
            print(event.content[len(last_content):], end="", flush=True)
            last_content = event.content
        case "done":
            print()  # Final newline

# Send message with images
from rossum_agent_client.models import ImageContent
import base64

with open("invoice.png", "rb") as f:
    image_data = base64.b64encode(f.read()).decode()

images = [ImageContent(media_type="image/png", data=image_data)]
for event in client.send_message_stream(chat_id, "Extract data from this invoice", images=images):
    print(event)

# Send message with PDF documents
from rossum_agent_client.models import DocumentContent

with open("invoice.pdf", "rb") as f:
    pdf_data = base64.b64encode(f.read()).decode()

documents = [DocumentContent(media_type="application/pdf", data=pdf_data, filename="invoice.pdf")]
for event in client.send_message_stream(chat_id, "Process this document", documents=documents):
    print(event)
```

#### Files

```python
# List files in a chat
files = client.list_files(chat_id)

# Download a file
content = client.download_file(chat_id, "report.csv")
```

## SSE Event Types

When streaming messages, you'll receive these event types:

| Event Type | Field | Description |
|------------|-------|-------------|
| `thinking` | `event.content` | Agent's reasoning |
| `intermediate` | `event.content` | Partial response |
| `tool_start` | `event.tool_name` | Tool being called |
| `tool_result` | `event.result` | Tool output |
| `final_answer` | `event.content` | Final response |
| `error` | `event.content` | Error message |
| `file_created` | `event.filename`, `event.url` | Generated file |
| `sub_agent_progress` | `event.tool_name`, `event.iteration` | Sub-agent status |
| `sub_agent_text` | `event.text` | Sub-agent output |
| `done` | `event.input_tokens`, `event.output_tokens`, `event.token_usage_breakdown` | Token usage with optional breakdown by main agent vs sub-agents |

**Note:** Text events (`thinking`, `intermediate`, `final_answer`) contain cumulative content - each event includes all previous text plus new tokens. To display live progress, print only the delta: `event.content[len(last_content):]`.

## Models

All request/response models are available in `rossum_agent_client.models`:

```python
from rossum_agent_client.models import (
    # Requests
    CreateChatRequest,
    MessageRequest,
    ImageContent,
    DocumentContent,

    # Responses
    ChatResponse,
    ChatDetail,
    ChatListResponse,
    ChatSummary,
    HealthResponse,
    DeleteResponse,
    FileListResponse,
    FileInfo,

    # Events
    StepEvent,
    StreamDoneEvent,
    FileCreatedEvent,
    SubAgentProgressEvent,
    SubAgentTextEvent,
    Message,
    TextContent,

    # Token usage
    TokenUsageBySource,
    SubAgentTokenUsageDetail,
    TokenUsageBreakdown
)
```

## Error Handling

```python
from rossum_agent_client.exceptions import (
    RossumAgentError,      # Base exception
    AuthenticationError,   # 401 errors
    NotFoundError,         # 404 errors
    RateLimitError,        # 429 errors
    ValidationError,       # 422 errors
    ServerError            # 5xx errors
)

try:
    chat = client.get_chat("non-existent-id")
except NotFoundError as e:
    print(f"Chat not found: {e}")
except RateLimitError as e:
    print(f"Rate limited, retry after: {e.retry_after}")
```

## OpenAPI Specification

The full OpenAPI specification is available at `openapi.json` in this package, or at runtime:

```python
# From running server
GET /api/openapi.json

# Interactive docs
GET /api/docs      # Swagger UI
GET /api/redoc     # ReDoc
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Resources

- [Full Documentation](https://stancld.github.io/rossum-agents/)
- [Rossum Agent README](../rossum-agent/README.md)
- [Rossum API Documentation](https://rossum.app/api/docs/)
- [Main Repository](https://github.com/stancld/rossum-agents)
