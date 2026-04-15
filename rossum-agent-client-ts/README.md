# Rossum Agent Client (TypeScript)

<div align="center">

**TypeScript client for Rossum Agent API - AI-powered document processing assistant.**

[![npm](https://img.shields.io/npm/v/rossum-agent-client.svg)](https://www.npmjs.com/package/rossum-agent-client)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7+-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Node.js](https://img.shields.io/badge/Node.js-18+-339933?logo=node.js&logoColor=white)](https://nodejs.org/)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-3.1-6BA539?logo=openapiinitiative&logoColor=white)](https://www.openapis.org/)
[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-agents/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

> [!NOTE]
> This is not an official Rossum project. It is a community-developed integration built on top of the Rossum API, not a product (yet).

## Overview

Typed TypeScript client generated from the [Rossum Agent OpenAPI spec](../rossum-agent/rossum_agent/api/openapi.json). Provides full type safety for all REST API endpoints and request/response models.

Used by [`rossum-agent-tui`](../rossum-agent-tui/) as the single source of truth for API types.

Streaming is handled natively via the [AI SDK UI Message Stream v1](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol) protocol — use `useChat` from `@ai-sdk/react` or parse the `data: <json>\n\n` stream directly. This package provides REST operations and OpenAPI types only.

## Installation

```bash
npm install rossum-agent-client
```

## Quick Start

```typescript
import { createChat, buildHeaders, type ClientConfig } from "rossum-agent-client";

const config: ClientConfig = {
  apiUrl: "https://your-agent-api.example.com",
  token: "your-rossum-api-token",
  rossumUrl: "https://elis.rossum.ai/api/v1",
};

// Create a chat session
const chat = await createChat(config, "read-only");

// Stream a message (AI SDK UI Message Stream v1)
const response = await fetch(
  `${config.apiUrl}/api/v1/chats/${chat.chat_id}/messages`,
  {
    method: "POST",
    headers: { ...buildHeaders(config) },
    body: JSON.stringify({ content: "List all queues" }),
  },
);

const reader = response.body!.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  for (const line of decoder.decode(value).split("\n")) {
    if (!line.startsWith("data: ") || line === "data: [DONE]") continue;
    const event = JSON.parse(line.slice(6));
    if (event.type === "text-delta") process.stdout.write(event.textDelta);
  }
}
```

> For React/Next.js apps, use `useChat` from `@ai-sdk/react` which handles the stream protocol automatically.

## API Reference

### Client Functions

| Function | Description |
|----------|-------------|
| `healthCheck(config)` | Check API health |
| `createChat(config, mcpMode?, persona?)` | Create a new chat session |
| `listChats(config, limit?, offset?)` | List all chat sessions |
| `getChat(config, chatId)` | Get chat details |
| `deleteChat(config, chatId)` | Delete a chat session |
| `cancelMessage(config, chatId)` | Cancel an in-progress message |
| `listCommands(config)` | List available agent commands |
| `listFiles(config, chatId)` | List files in a chat |
| `downloadFile(config, chatId, filename)` | Download a file |
| `submitFeedback(config, chatId, turnIndex, isPositive)` | Submit feedback on a turn |
| `getFeedback(config, chatId)` | Get feedback for a chat |
| `deleteFeedback(config, chatId, turnIndex)` | Delete feedback |
| `listCommits(config, chatId)` | List config commits from a chat |
| `reportToSlack(config, chatId, rossumUrl?)` | Report chat to Slack |
| `buildHeaders(config)` | Build auth headers for custom fetch calls |

### Streaming Protocol

The message endpoint (`POST /api/v1/chats/{id}/messages`) returns an AI SDK UI Message Stream v1 response. Each line is `data: <json>\n\n` discriminated by the `type` field. Stream ends with `data: [DONE]\n\n`.

| Wire `type` | Description |
|-------------|-------------|
| `start` / `finish` | Stream lifecycle |
| `reasoning-start` / `reasoning-delta` / `reasoning-end` | Extended thinking blocks |
| `text-start` / `text-delta` / `text-end` | Text content blocks |
| `tool-input-start` / `tool-input-available` | Tool call begins and args ready |
| `tool-output-available` | Tool result |
| `error` | Agent execution error |
| `data-agent-question` | Structured question from agent |
| `data-task-snapshot` | Full task list snapshot |
| `data-file-created` | File created during agent run |

## Type Generation

Types are generated from the OpenAPI spec. To regenerate after API changes:

```bash
npm run generate
```

This runs `openapi-typescript` against `rossum-agent/rossum_agent/api/openapi.json` and outputs `src/generated.ts`.

## Development

```bash
npm install          # Install dependencies
npm run build        # Build to dist/
npm run typecheck    # Type check without emitting
npm run format       # Format with Prettier
npm run format:check # Check formatting
```

## License

MIT License - see [LICENSE](../LICENSE) for details.

## Resources

- [Full Documentation](https://stancld.github.io/rossum-agents/)
- [Python Client](../rossum-agent-client/README.md)
- [Rossum Agent README](../rossum-agent/README.md)
- [Main Repository](https://github.com/rossumai/rossum-agents)
