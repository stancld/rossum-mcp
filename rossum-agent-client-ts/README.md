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

## Overview

Typed TypeScript client generated from the [Rossum Agent OpenAPI spec](../rossum-agent/rossum_agent/api/openapi.json). Provides full type safety for all API endpoints, SSE events, and request/response models.

Used by [`rossum-agent-tui`](../rossum-agent-tui/) as the single source of truth for API types.

## Installation

```bash
npm install rossum-agent-client
```

## Quick Start

```typescript
import {
  createChat,
  streamMessage,
  type ClientConfig,
  type SSEEvent,
} from "rossum-agent-client";

const config: ClientConfig = {
  apiUrl: "https://your-agent-api.example.com",
  token: "your-rossum-api-token",
  rossumUrl: "https://elis.rossum.ai/api/v1",
};

// Create a chat session
const chat = await createChat(config, "read-only");

// Stream a message
await streamMessage({
  config,
  chatId: chat.chat_id,
  message: "List all queues",
  onEvent: (event: SSEEvent) => {
    switch (event.event) {
      case "step":
        if (event.data.type === "final_answer") {
          process.stdout.write(event.data.content ?? "");
        }
        break;
      case "done":
        console.log(`\n(${event.data.input_tokens} in, ${event.data.output_tokens} out)`);
        break;
    }
  },
  onError: (err) => console.error(err),
  onDone: () => console.log("Stream complete"),
});
```

## API Reference

### Client Functions

| Function | Description |
|----------|-------------|
| `healthCheck(config)` | Check API health |
| `createChat(config, mcpMode?, persona?)` | Create a new chat session |
| `listChats(config, limit?, offset?)` | List all chat sessions |
| `getChat(config, chatId)` | Get chat details |
| `deleteChat(config, chatId)` | Delete a chat session |
| `streamMessage(opts)` | Send a message and stream SSE response |
| `cancelMessage(config, chatId)` | Cancel an in-progress message |
| `listCommands(config)` | List available agent commands |
| `listFiles(config, chatId)` | List files in a chat |
| `downloadFile(config, chatId, filename)` | Download a file |
| `submitFeedback(config, chatId, turnIndex, isPositive)` | Submit feedback on a turn |
| `getFeedback(config, chatId)` | Get feedback for a chat |
| `deleteFeedback(config, chatId, turnIndex)` | Delete feedback |
| `listCommits(config, chatId)` | List config commits from a chat |
| `reportToSlack(config, chatId, rossumUrl?)` | Report chat to Slack |

### SSE Event Types

When streaming messages, you receive these event types:

| Event | Data Type | Description |
|-------|-----------|-------------|
| `step` | `StepEvent` | Agent execution step (thinking, tool use, final answer) |
| `sub_agent_progress` | `SubAgentProgressEvent` | Sub-agent iteration updates |
| `sub_agent_text` | `SubAgentTextEvent` | Sub-agent text streaming |
| `task_snapshot` | `TaskSnapshotEvent` | Task tracker state |
| `agent_question` | `AgentQuestionEvent` | Structured question from agent |
| `file_created` | `FileCreatedEvent` | Output file notification |
| `done` | `StreamDoneEvent` | Final event with token usage |

### StepEvent Types

| Type | Description |
|------|-------------|
| `thinking` | Agent's chain-of-thought reasoning |
| `intermediate` | Partial response before tool calls |
| `tool_start` | Tool execution begins |
| `tool_result` | Tool execution completes |
| `final_answer` | Final response text |
| `error` | Agent execution error |

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

MIT License - see [LICENSE](LICENSE) for details.

## Resources

- [Full Documentation](https://stancld.github.io/rossum-agents/)
- [Python Client](../rossum-agent-client/README.md)
- [Rossum Agent README](../rossum-agent/README.md)
- [Main Repository](https://github.com/stancld/rossum-agents)
