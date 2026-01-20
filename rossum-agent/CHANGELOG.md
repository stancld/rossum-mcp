# Changelog - Rossum Agent

All notable changes to this project will be documented in this file.

---

## [Unreleased] - YYYY-MM-DD

### Added
- Added dynamic tool loading to reduce initial context usage (~8K → ~800 tokens) [#113](https://github.com/stancld/rossum-agents/pull/113)
- Added `load_tool_category(["queues", "schemas"])` internal tool to load MCP tools on-demand [#113](https://github.com/stancld/rossum-agents/pull/113)
- Added automatic pre-loading of tool categories based on keywords in user's first message [#113](https://github.com/stancld/rossum-agents/pull/113)
- Added PDF document upload support for both REST API and Streamlit UI. Documents are stored in session output directory for agent use (e.g., upload to Rossum) [#102](https://github.com/stancld/rossum-agents/pull/102)
- Added lightweight request classifier using Claude Haiku to filter out-of-scope requests before invoking the main agent
- Added skills system for dynamic skill loading from markdown files [#73](https://github.com/stancld/rossum-agents/pull/73)
- Added `hook-debugging` skill for systematic hook debugging workflow [#73](https://github.com/stancld/rossum-agents/pull/73)
- Added `rossum-deployment` skill for workspace deployment workflows [#73](https://github.com/stancld/rossum-agents/pull/73)
- Added deployment-related internal tools: `pull_workspace`, `compare_workspaces`, `copy_workspace`, `get_id_mapping` [#73](https://github.com/stancld/rossum-agents/pull/73)
- Added `list_local_files` and `clean_schema_dict` internal tools [#73](https://github.com/stancld/rossum-agents/pull/73)
- Added logging for deploy tools usage [#73](https://github.com/stancld/rossum-agents/pull/73)
- Added extended thinking support with configurable budget (default 10k tokens) for improved reasoning [#92](https://github.com/stancld/rossum-agents/pull/92)
- Added `organization-setup` skill for new customer onboarding with template-based queue creation [#102](https://github.com/stancld/rossum-agents/pull/102)
- Added `schema-pruning` skill for efficient removal of unwanted schema fields [#102](https://github.com/stancld/rossum-agents/pull/102)
- Added `patch_schema_with_subagent` tool for safe schema patching with Opus sub-agent verification [#102](https://github.com/stancld/rossum-agents/pull/102)
- Added MCP helpers module for shared sub-agent utilities [#102](https://github.com/stancld/rossum-agents/pull/102)
- Added Rossum Local Copilot integration for formula field suggestions [#102](https://github.com/stancld/rossum-agents/pull/102)

### Changed
- Execute multiple tool calls in parallel using `asyncio.wait()` instead of sequential execution
- Migrated knowledge base search from sync `requests` to async `httpx` with parallel webpage fetching via `asyncio.gather()`
- Refactored sub-agents (hook_debug, schema_patching, knowledge_base) to shared `SubAgent` base class with unified iteration loop [#107](https://github.com/stancld/rossum-agents/pull/107)
- Added token tracking to all sub-agents with counts propagated via `SubAgentResult` [#107](https://github.com/stancld/rossum-agents/pull/107)
- Migrated default model from Sonnet 4.5 to Opus 4.5 with significantly simplified prompts [#99](https://github.com/stancld/rossum-agents/pull/99)
- Separated model's chain-of-thought reasoning (thinking blocks) from response text (text blocks) in stream processing [#92](https://github.com/stancld/rossum-agents/pull/92)
- Updated Streamlit UI to display thinking blocks with "🧠 **Thinking:**" label [#92](https://github.com/stancld/rossum-agents/pull/92)
- Refactored `internal_tools.py` into modular `tools/` subpackage with separate modules for file tools, spawn MCP, knowledge base search, hook debugging, and skills [#78](https://github.com/stancld/rossum-agents/pull/78)
- Reorganized sub-agent tools into `tools/subagents/` module (hook_debug, knowledge_base, schema_patching)
- Improved multi-turn conversation by passing context properly [#73](https://github.com/stancld/rossum-agents/pull/73)
- Improved sub-agent knowledge base info panel [#73](https://github.com/stancl/rossum-mcp/pull/73)
- Made token owner selection stricter in deployment tools [#73](https://github.com/stancld/rossum-agents/pull/73)
- Display workspace diffs in a concise way [#73](https://github.com/stancld/rossum-agents/pull/73)
- Improved result analyzing UX for sub-agent responses [#85](https://github.com/stancld/rossum-agents/pull/85)

### Removed
- Removed test front-end from rossum-agent API as it doesn't fit the repo scope [#83](https://github.com/stancld/rossum-agents/pull/83)

### Fixed
- Fixed displaying generated files in Streamlit UI [#73](https://github.com/stancld/rossum-agents/pull/73)


## [0.2.7] - 2025-12-16

### Added
- Added `search_knowledge_base` internal tool for searching Rossum Knowledge Base documentation with Opus-powered analysis [#72](https://github.com/stancld/rossum-agents/pull/72)
- Added `evaluate_python_hook` internal tool for sandboxed hook execution against test annotation/schema data [#72](https://github.com/stancld/rossum-agents/pull/72)
- Added `debug_hook` internal tool using Opus sub-agent for iterative hook debugging with root cause analysis and fix suggestions [#72](https://github.com/stancld/rossum-agents/pull/72)
- Added `web_search` and `read_web_page` internal tools for web search capabilities [#72](https://github.com/stancld/rossum-agents/pull/72)
- Added multi-turn conversation guidelines to prompts [#72](https://github.com/stancld/rossum-agents/pull/72)

### Changed
- Improved tool result serialization in agent core to handle pydantic models and dataclasses properly [#72](https://github.com/stancld/rossum-agents/pull/72)
- Kept image in the context for the whole conversation [#72](https://github.com/stancld/rossum-agents/pull/72)
- Enabled short, concise answers by default [#72](https://github.com/stancld/rossum-agents/pull/72)
- Improved `list_hook` and `get_hook` MCP tool descriptions [#72](https://github.com/stancld/rossum-agents/pull/72)

### Fixed
- Fixed sending generated files to front-end in API responses [#72](https://github.com/stancld/rossum-agents/pull/72)


## [0.2.6] - 2025-12-15
- Made LLM response to be streamed in API [#70](https://github.com/stancld/rossum-agents/pull/70)


## [0.2.5] - 2025-12-14
- Added SSRF protection via URL validation for Rossum API endpoints [#69](https://github.com/stancld/rossum-agents/pull/69)
- Added path traversal and header injection protection for file downloads [#69](https://github.com/stancld/rossum-agents/pull/69)
- Added XSS protection via DOMPurify in test client [#69](https://github.com/stancld/rossum-agents/pull/69)


## [0.2.4] - 2025-12-14
- Added image input support [#67](https://github.com/stancld/rossum-agents/pull/67)
- Added logging of chat metadata into Redis for auditing [#62](https://github.com/stancld/rossum-agents/pull/62)
- Stopped replaying CoT in the model context [#61](https://github.com/stancld/rossum-agents/pull/61)
- Introduced storing a final answer in memory when no tool is called [#61](https://github.com/stancld/rossum-agents/pull/61)
- Added storing generated files in API and event to inform the client
- Added `preview` field to `/api/v1/chats` response with user request preview [#65](https://github.com/stancld/rossum-agents/pull/65)
- Separated Streamlit components into `streamlit_app` submodule as a standalone test-bed component [#66](https://github.com/stancld/rossum-agents/pull/66)


## [0.2.3] - 2025-12-10
- Handle invalid passed sideload to get_annotation gracefully [#60](https://github.com/stancld/rossum-agents/pull/60)


## [0.2.2] - 2025-12-10
- Pass extra context from URL to the LLM [#59](https://github.com/stancld/rossum-agents/pull/59)


## [0.2.1] - 2025-12-10
- Added FastAPI-based REST API with SSE streaming for real-time agent responses [#58](https://github.com/stancld/rossum-agents/pull/58)
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
- Started using structured outputs to streamline agent instructions [#52](https://github.com/stancld/rossum-agents/pull/52)
- Streamlined system prompt [#53](https://github.com/stancld/rossum-agents/pull/53), [#54](https://github.com/stancld/rossum-agents/pull/54)
- Consolidated read_file and get_file_info tools into a single one [#54](https://github.com/stancld/rossum-agents/pull/54)

### Added
- New `bedrock_client.py` for direct AWS Bedrock integration
- New `mcp_tools.py` for async MCP server connection
- New `agent/` package with `core.py`, `memory.py`, `models.py`


## [0.1.8] - 2025-12-06
- Updated Rossum MCP to 0.2.0. See more info in the [release notes](https://github.com/stancld/rossum-agents/releases/tag/rossum-mcp-v0.2.0).


## [0.1.7] - 2025-12-04
- Fixed teleport user detection from JWT [#46](https://github.com/stancld/rossum-agents/pull/46)
- Made permalinks shareable across users [#47](https://github.com/stancld/rossum-agents/pull/47), [#48](https://github.com/stancld/rossum-agents/pull/48)


## [0.1.6] - 2025-12-03
- Improved teleport user detection [#45](https://github.com/stancld/rossum-agents/pull/45)


## [0.1.5] - 2025-12-03
- Added User ID to a Streamlit UI for debugging purposes


## [0.1.4] - 2025-12-03
- Added conversation permalinks persisted in Redis [#44](https://github.com/stancld/rossum-agents/pull/44)


## [0.1.3] - 2025-12-02
- Fixed leaking Rossum API credentials across users' session [#41](https://github.com/stancld/rossum-agents/pull/41)
- Fixed leaking generated files across users' session [#42](https://github.com/stancld/rossum-agents/pull/42)


## [0.1.2] - 2025-12-01
- Fixed using AWS Bedrock Model ARN [#39](https://github.com/stancld/rossum-agents/pull/39)


## [0.1.1] - 2025-12-01
- Fixed displaying mermaid diagrams in Streamlit UI [#36](https://github.com/stancld/rossum-agents/pull/36)
- Added beep sound notification upon completing the agent answer [#37](https://github.com/stancld/rossum-agents/pull/37)
- Added missing support for parsing AWS role params [#38](https://github.com/stancld/rossum-agents/pull/38)
