# Changelog - Rossum Agent

All notable changes to this project will be documented in this file.

---

## [Unreleased] - YYYY-MM-DD
- Started using structured outputs to streamline agent instructions [#52](https://github.com/stancld/rossum-mcp/pull/52)
- Streamlined system prompt via inlining`smolagents` system prompt logic, and dropping their examples.
This change saves roughly 3.3k tokes from previous ~9,6k for the initial LLM call [#53](https://github.com/stancld/rossum-mcp/pull/53)


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
