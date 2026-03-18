# Rossum Agent Client

<div align="center">

**Python client for Rossum Agent API - AI-powered document processing assistant.**

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-agents/)
[![Python](https://img.shields.io/pypi/pyversions/rossum-agent-client.svg)](https://pypi.org/project/rossum-agent-client/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI - rossum-agent-client](https://img.shields.io/pypi/v/rossum-agent-client?label=rossum-agent-client)](https://pypi.org/project/rossum-agent-client/)
[![Coverage](https://codecov.io/gh/stancld/rossum-agents/branch/master/graph/badge.svg?flag=rossum-agent-client)](https://codecov.io/gh/stancld/rossum-agents)

[![Rossum API](https://img.shields.io/badge/Rossum-API-orange.svg)](https://github.com/rossumai/rossum-api)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

</div>

> [!NOTE]
> This is not an official Rossum project. It is a community-developed integration built on top of the Rossum API, not a product (yet).

> [!IMPORTANT]
> The `send_message_stream` method still parses the legacy SSE protocol (`event:` + `data:` lines). The server now uses the [AI SDK UI Message Stream v1](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol) format (`data: <json>\n\n` with `type` inside JSON). Streaming will be migrated in a future release. REST operations (chat CRUD, files, feedback) work as expected.

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
chat = client.create_chat(mcp_mode="read-only", persona="default")
print(f"Created chat: {chat.chat_id}")
```

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

# Use cautious persona
rossum-agent-client --persona cautious -x "List all queues"
```

Files created by the agent (via `write_file` tool) are automatically downloaded and saved to the current directory.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `ROSSUM_AGENT_API_URL` | Agent API URL |
| `ROSSUM_API_BASE_URL` | Rossum API base URL |
| `ROSSUM_API_TOKEN` | Rossum API authentication token |
| `ROSSUM_MCP_MODE` | MCP mode: `read-only` (default) or `read-write` |
| `ROSSUM_AGENT_PERSONA` | Agent persona: `default` (default) or `cautious` |

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

        # List chats
        chats = await client.list_chats()
        print(f"Total chats: {chats.total}")

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
chat = client.create_chat(mcp_mode="read-only", persona="default")  # or "cautious"

# List all chats
chats = client.list_chats(limit=50, offset=0)

# Get chat details
chat_detail = client.get_chat(chat_id)

# Delete a chat
result = client.delete_chat(chat_id)
```

#### Messages

> [!NOTE]
> `send_message_stream` currently parses the legacy SSE protocol. It will be updated to parse the AI SDK UI Message Stream v1 format in a future release.

```python
# Send message with images
from rossum_agent_client.models import ImageContent, MessageRequest
import base64

with open("invoice.png", "rb") as f:
    image_data = base64.b64encode(f.read()).decode()

images = [ImageContent(media_type="image/png", data=image_data)]

# Send message with PDF documents
from rossum_agent_client.models import DocumentContent

with open("invoice.pdf", "rb") as f:
    pdf_data = base64.b64encode(f.read()).decode()

documents = [DocumentContent(media_type="application/pdf", data=pdf_data, filename="invoice.pdf")]
```

#### Files

```python
# List files in a chat
files = client.list_files(chat_id)

# Download a file
content = client.download_file(chat_id, "report.csv")
```

## Streaming Protocol

The message endpoint (`POST /api/v1/chats/{id}/messages`) returns an AI SDK UI Message Stream v1 response (`x-vercel-ai-ui-message-stream: v1`). Each line is `data: <json>\n\n` discriminated by the `type` field. Stream ends with `data: [DONE]\n\n`.

| Wire `type` | Description |
|-------------|-------------|
| `start` / `finish` | Stream lifecycle |
| `text-start` / `text-delta` / `text-end` | Text content blocks |
| `error` | Agent execution error |
| `data-agent-question` | Structured question from agent |

All JSON fields use camelCase keys (`toolCallId`, `toolName`, `textDelta`, etc.).

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
    Message,
    TextContent,
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

MIT License - see [LICENSE](../LICENSE) for details.

## Resources

- [Full Documentation](https://stancld.github.io/rossum-agents/)
- [Rossum Agent README](../rossum-agent/README.md)
- [Rossum API Documentation](https://rossum.app/api/docs/)
- [Main Repository](https://github.com/stancld/rossum-agents)
