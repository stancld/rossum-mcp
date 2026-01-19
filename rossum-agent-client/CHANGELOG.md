# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial release of the Rossum Agent Python client
- Synchronous `RossumAgentClient` with full API coverage
- Asynchronous `AsyncRossumAgentClient` for async/await usage
- SSE streaming support for `send_message` endpoint
- Pydantic v2 models for all request/response types
- Comprehensive error handling with typed exceptions
- Support for multimodal messages (images and PDF documents)
- File download support for agent-generated files
- OpenAPI 3.1.0 specification included

### API Endpoints

- `GET /api/v1/health` - Health check
- `POST /api/v1/chats` - Create chat session
- `GET /api/v1/chats` - List chat sessions
- `GET /api/v1/chats/{chat_id}` - Get chat details
- `DELETE /api/v1/chats/{chat_id}` - Delete chat session
- `POST /api/v1/chats/{chat_id}/messages` - Send message (SSE stream)
- `GET /api/v1/chats/{chat_id}/files` - List files
- `GET /api/v1/chats/{chat_id}/files/{filename}` - Download file

### Models

- Request models: `CreateChatRequest`, `MessageRequest`, `ImageContent`, `DocumentContent`
- Response models: `ChatResponse`, `ChatDetail`, `ChatListResponse`, `ChatSummary`, `HealthResponse`, `DeleteResponse`, `FileListResponse`, `FileInfo`
- Event models: `StepEvent`, `StreamDoneEvent`, `FileCreatedEvent`
- Content models: `Message`, `TextContent`

[Unreleased]: https://github.com/stancld/rossum-agents/tree/master/rossum-agent-client
