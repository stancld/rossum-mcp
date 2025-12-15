# Changelog - Rossum Agent

All notable changes to this project will be documented in this file.

---

## [Unreleased] - YYYY-MM-DD
- Added `list_hook_logs` MCP tool for querying hook execution logs with filtering by hook_id, queue_id, log_level, timestamps, and full-text search [#73](https://github.com/stancld/rossum-mcp/pull/73)
- Added `evaluate_python_hook` internal tool for sandboxed hook execution against test annotation/schema data [#73](https://github.com/stancld/rossum-mcp/pull/73)
- Added `debug_hook` internal tool using Opus sub-agent for iterative hook debugging with root cause analysis and fix suggestions [#73](https://github.com/stancld/rossum-mcp/pull/73)
- Improved tool result serialization in agent core to handle pydantic models and dataclasses properly [#73](https://github.com/stancld/rossum-mcp/pull/73)
- Kept image in the context for the whole conversation [#72](https://github.com/stancld/rossum-mcp/pull/72)
- Enabled short answers [#72](https://github.com/stancld/rossum-mcp/pull/72)
- Improved list_hook and get_hook descriptions [#72](https://github.com/stancld/rossum-mcp/pull/72)


## [0.2.6] - 2025-12-15
- Made LLM response to be streamed in API [#70](https://github.com/stancld/rossum-mcp/pull/70)


## [0.2.5] - 2025-12-14
- Added SSRF protection via URL validation for Rossum API endpoints [#69](https://github.com/stancld/rossum-mcp/pull/69)
- Added path traversal and header injection protection for file downloads [#69](https://github.com/stancld/rossum-mcp/pull/69)
- Added XSS protection via DOMPurify in test client [#69](https://github.com/stancld/rossum-mcp/pull/69)


## [0.2.4] - 2025-12-14
- Added image input support [#67](https://github.com/stancld/rossum-mcp/pull/67)
- Added logging of chat metadata into Redis for auditing [#62](https://github.com/stancld/rossum-mcp/pull/62)
- Stopped replaying CoT in the model context [#61](https://github.com/stancld/rossum-mcp/pull/61)
- Introduced storing a final answer in memory when no tool is called [#61](https://github.com/stancld/rossum-mcp/pull/61)
- Added storing generated files in API and event to inform the client
- Added `preview` field to `/api/v1/chats` response with user request preview [#65](https://github.com/stancld/rossum-mcp/pull/65)
- Separated Streamlit components into `streamlit_app` submodule as a standalone test-bed component [#66](https://github.com/stancld/rossum-mcp/pull/66)


## [0.2.3] - 2025-12-10
- Handle invalid passed sideload to get_annotation gracefully [#60](https://github.com/stancld/rossum-mcp/pull/60)


## [0.2.2] - 2025-12-10
- Pass extra context from URL to the LLM [#59](https://github.com/stancld/rossum-mcp/pull/59)


## [0.2.1] - 2025-12-10
- Added FastAPI-based REST API with SSE streaming for real-time agent responses [#58](https://github.com/stancld/rossum-mcp/pull/58)
  - Chat session management endpoints (create, list, get, delete)
  - Message endpoint with Server-Sent Events (SSE) for streaming agent responses
  - File management endpoints (list, download) for agent-generated artifacts
  - Rate limiting (30/min for chat creation, 10/min for messages)
  - Rossum API credential validation via headers (`X-Rossum-Token`, `X-Rossum-Api-Url`)


## [0.2.0] - 2025-12-09

### Breaking Changes
- Removed `smolagents` and `LiteLLM` dependencies
- Removed `file_system_tools.py`, `hook_analysis_tools.py`, `plot_tools.py` modules (replaced by Claude's native code execution)
- Removed old `agent.py` implementation

### Changed
- Migrated from smolagents + LiteLLM to Claude Agents SDK with direct Anthropic Bedrock integration
- Started using structured outputs to streamline agent instructions [#52](https://github.com/stancld/rossum-mcp/pull/52)
- Streamlined system prompt [#53](https://github.com/stancld/rossum-mcp/pull/53), [#54](https://github.com/stancld/rossum-mcp/pull/54)
- Consolidated read_file and get_file_info tools into a single one [#54](https://github.com/stancld/rossum-mcp/pull/54)

### Added
- New `bedrock_client.py` for direct AWS Bedrock integration
- New `mcp_tools.py` for async MCP server connection
- New `agent/` package with `core.py`, `memory.py`, `models.py`


## [0.1.8] - 2025-12-06
- Updated Rossum MCP to 0.2.0. See more info in the [release notes](https://github.com/stancld/rossum-mcp/releases/tag/rossum-mcp-v0.2.0).


## [0.1.7] - 2025-12-04
- Fixed teleport user detection from JWT [#46](https://github.com/stancld/rossum-mcp/pull/46)
- Made permalinks shareable across users [#47](https://github.com/stancld/rossum-mcp/pull/47), [#48](https://github.com/stancld/rossum-mcp/pull/48)


## [0.1.6] - 2025-12-03
- Improved teleport user detection [#45](https://github.com/stancld/rossum-mcp/pull/45)


## [0.1.5] - 2025-12-03
- Added User ID to a Streamlit UI for debugging purposes


## [0.1.4] - 2025-12-03
- Added conversation permalinks persisted in Redis [#44](https://github.com/stancld/rossum-mcp/pull/44)


## [0.1.3] - 2025-12-02
- Fixed leaking Rossum API credentials across users' session [#41](https://github.com/stancld/rossum-mcp/pull/41)
- Fixed leaking generated files across users' session [#42](https://github.com/stancld/rossum-mcp/pull/42)


## [0.1.2] - 2025-12-01
- Fixed using AWS Bedrock Model ARN [#39](https://github.com/stancld/rossum-mcp/pull/39)


## [0.1.1] - 2025-12-01
- Fixed displaying mermaid diagrams in Streamlit UI [#36](https://github.com/stancld/rossum-mcp/pull/36)
- Added beep sound notification upon completing the agent answer [#37](https://github.com/stancld/rossum-mcp/pull/37)
- Added missing support for parsing AWS role params [#38](https://github.com/stancld/rossum-mcp/pull/38)
