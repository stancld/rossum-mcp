# Changelog - Rossum Agent

All notable changes to this project will be documented in this file.

---

## [Unreleased] - YYYY-MM-DD

## [1.5.6] - 2026-03-18

### Changed
- Schema-patching skill: Added `disable_prediction` to unsupported properties list and documented `ui_configuration.type` (`manual`/`data`) as the alternative for fields without AI extraction [#277](https://github.com/rossumai/rossum-agents/pull/277)
- `execute_python`: Add `time` to allowed imports; factor out allowed-modules list into `ALLOWED_MODULES_CSV` constant used by tool definition [#278](https://github.com/rossumai/rossum-agents/pull/278)
- Document-testing skill: Include only required fields in mock PDFs, exclude hidden fields, use "Total Amount" / "Total Amount Base" labels for Aurora capture [#279](https://github.com/rossumai/rossum-agents/pull/279)
- Schema-patching skill: Added engine constraint guidance — captured fields on Aurora schemas require a matching engine field via `create_engine_field` before schema patching; non-captured types (`formula`, `reasoning`, `manual`, `data`) are exempt [#280](https://github.com/rossumai/rossum-agents/pull/280)

## [1.5.5] - 2026-03-17

### Changed
- Bump `rossum-api` dependency from `>=3.11.2` to `>=3.12.0` [#276](https://github.com/rossumai/rossum-agents/pull/276)

### Fixed
- `generate_mock_pdf`: Improved `_find_item_total_key` to resolve line-item total fields via `rir_field_names` and broader key-name patterns (`item_total`, `*total*`) — fixes amount consistency breaking when the schema uses custom field IDs like `item_total` instead of `item_amount_total` [#275](https://github.com/rossumai/rossum-agents/pull/275)

## [1.5.4] - 2026-03-17

### Fixed
- `get_chat`: Normalize multimodal content blocks (Anthropic image `source` format → flat `ImageContent`) in `task_step` and regular user messages — fixes incorrect serialization when chat history contains images [#273](https://github.com/rossumai/rossum-agents/pull/273)

## [1.5.3] - 2026-03-17

### Fixed
- `list_chats`: Handle multimodal content blocks (e.g. image + text) in `first_message` and `preview` fields — fixes 500 error when chat history contains image messages [#273](https://github.com/rossumai/rossum-agents/pull/273)

## [1.5.2] - 2026-03-17

### Added
- `generate_mock_pdf`: Accept numeric overrides (`int`/`float`), per-row `line_item_overrides`, and `consistent_amounts` toggle for mismatch testing [#270](https://github.com/rossumai/rossum-agents/pull/270)
- `execute_python`: Allow `fpdf` (fpdf2) imports for custom PDF generation [#270](https://github.com/rossumai/rossum-agents/pull/270)

### Fixed
- `PostgresStorage`: Added `sslmode` support via constructor parameter and `POSTGRES_SSLMODE` env var — fixes connections to PostgreSQL servers that require SSL [#272](https://github.com/rossumai/rossum-agents/pull/272)

## [1.5.1] - 2026-03-16

### Added
- Added `ord` to `execute_python` safe builtins
- Bundled `rossum-kb.json` as package data and load it via `importlib.resources` instead of `Path(__file__)` traversal — works correctly when installed from wheel/zip
- Allowed `try/except` blocks in `execute_python` sandbox — removes `ast.Try` from disallowed nodes and exposes common exception types (`Exception`, `ValueError`, `KeyError`, `TypeError`, etc.) as safe builtins
- Allowed `with` statements in `execute_python` sandbox — enables context managers (e.g. `with open(...) as f`)
- Added `context_usage_fraction` field to `StreamDoneEvent` — reports the fraction of the model's input context window used after each turn, enabling clients to display context budget warnings [#267](https://github.com/rossumai/rossum-agents/pull/267)

### Fixed
- `run_jq` now accepts `dict` data directly — prevents `TypeError` when the model passes parsed JSON instead of a string [#261](https://github.com/rossumai/rossum-agents/pull/261)
- Switched MDH dataset listing to `/v2/datasets` endpoint [#261](https://github.com/rossumai/rossum-agents/pull/261)
- Clarified in lookup-fields skill and base prompt that lookup fields are native schema-level matching, not hook-based — prevents agent from incorrectly creating hooks for lookup fields [#261](https://github.com/rossumai/rossum-agents/pull/261)

## [1.5.0] - 2026-03-13

### Added
- Added PostgreSQL as chat persistence backend — `CHAT_STORAGE_BACKEND=postgres` (default) uses SQLAlchemy Core with `psycopg` for durable chat/file/feedback storage with configurable TTL; `redis` remains available as an alternative; added `docker-compose.yml` for local development [#248](https://github.com/rossumai/rossum-agents/pull/248)
- Cautious persona now gates write operations (MCP + internal) behind a user confirmation prompt — blocked tools emit an `agent_question` SSE event with yes/no/chat options; only explicit approval pre-approves the tool for the next turn [#252](https://github.com/stancld/rossum-agents/pull/252)

### Changed
- Tool result serialization now uses compact JSON (`separators=(",", ":")`) instead of pretty-printed (`indent=2`) to reduce token usage in LLM context [#254](https://github.com/stancld/rossum-agents/pull/254)

### Fixed
- Chat summary generation now receives URL context (queue ID, document ID, etc.) so the summarizer understands the user's current Rossum page context
- Preload info is now stored separately in `TaskStep` instead of being baked into the user's prompt text — keeps original task clean in DB while still injecting system hints into API messages; includes backward-compatible extraction of legacy format [#256](https://github.com/stancld/rossum-agents/pull/256)
- SSE streaming now emits finalization events (`is_streaming: false`) for all step types — fixes step type misclassification where text streamed as `final_answer` was never corrected to `intermediate` when tool_use blocks arrived later
- First streaming step now defaults to `intermediate` type — prevents initial text from being briefly misclassified as `final_answer` before tool_use blocks arrive

## [1.4.0] - 2026-03-09

### Added
- Auto-spillover for large tool results — results exceeding 30k chars are automatically saved to `{output_dir}/workspace/` and replaced with a compact summary + file path; agent uses `run_jq` or `run_grep` to query full content on demand [#240](https://github.com/rossumai/rossum-agents/pull/240)
- Per-message boolean feedback (thumbs up/down) — `PUT/GET/DELETE /api/v1/chats/{chat_id}/feedback` endpoints for rating agent responses by turn index [#222](https://github.com/rossumai/rossum-agents/pull/222)
- Streaming progress logging — logs model/message count at stream start, periodic progress every 10s (phase, elapsed time, character throughput), and total elapsed time on completion for visibility into long Bedrock generations
- Added `ask_user_question` tool — agent can ask the user structured questions (free-text or multiple-choice) mid-execution when it needs information it cannot determine on its own; streamed via SSE `agent_question` event [#224](https://github.com/rossumai/rossum-agents/pull/224)

### Changed
- Updated hooks skill prompt to show `token_owner` and `run_after` in `create_hook` example [#247](https://github.com/stancld/rossum-agents/pull/247)
- Removed `elis_openapi_grep` and `elis_openapi_jq` as direct agent tools — Elis API reference lookups now route exclusively through the `search_elis_docs` sub-agent ([#220](https://github.com/rossumai/rossum-agents/pull/220))
- Replaced individual copilot tools (`suggest_formula_field`, `suggest_lookup_field`, `evaluate_lookup_field`, `get_lookup_dataset_raw_values`, `query_lookup_dataset`) with a single `execute_python` tool — copilot functions are now called via Python execution instead of dedicated agent tools [#242](https://github.com/stancld/rossum-agents/pull/242)
- Removed `load_tool_category` tool — agent now loads MCP tools individually via `load_tool` by name; `load_tool` description updated with category listing guidance [#243](https://github.com/stancld/rossum-agents/pull/243)

### Removed
- Removed `organization-setup` skill — queue creation is handled directly via `create_queue_from_template` without needing a dedicated skill [#245](https://github.com/rossumai/rossum-agents/pull/245)
- Removed `create_schema_with_subagent` tool and `schema-creation` skill — schema creation is handled by the agent directly using `patch_schema_with_subagent` (via schema-patching sub-agent) [#244](https://github.com/stancld/rossum-agents/pull/244)
- Removed `HIDDEN_TOOLS` concept — `update_schema` and `create_queue` MCP tools are fully removed; schema patching subagent now calls the Rossum API directly via `httpx` instead of routing through `update_schema` MCP tool [#245](https://github.com/stancld/rossum-agents/pull/245)
- Removed `rossum-deployment` skill and all deploy/spawn tools — unused and unsolved [#241](https://github.com/stancld/rossum-agents/pull/241)
- Removed `schema-pruning` skill — use `prune_schema_fields` MCP tool directly [#225](https://github.com/stancld/rossum-agents/pull/225)
- Updated skills and MCP integration for rossum-mcp's unified `get`/`search` read layer — base prompt, 5 skill files (document-testing, hooks, rossum-deployment, rules-and-actions, ui-settings), and copilot tools now reference new tool names instead of removed `get_*/list_*` tools [#221](https://github.com/stancld/rossum-agents/pull/221)
- Removed `kb_grep` and `kb_get_article` from main agent tools — knowledge base lookups now route through `search_knowledge_base` sub-agent only [#221](https://github.com/stancld/rossum-agents/pull/221)
- Formula tools (`suggest_formula_field`) and lookup tools (`suggest_lookup_field`, `evaluate_lookup_field`, `get_lookup_dataset_raw_values`, `query_lookup_dataset`) are now skill-gated — only available after loading `formula-fields` or `lookup-fields` skill respectively [#221](https://github.com/stancld/rossum-agents/pull/221)

### Fixed
- Fixed `packages.find` in `pyproject.toml` — removed `rossum_mcp*` and `rossum_deploy*` from the `include` list; only `rossum_agent*` belongs in this package's build
- Fixed Slack reporter name blank when using support access — `/v1/users/{id}` returns 404 for cross-org support tokens; now falls back to `first_name last_name (email)` from `/v1/auth/user` response [#223](https://github.com/rossumai/rossum-agents/pull/223)
- Schema patching sub-agent now auto-recovers from engine restriction errors — when `update_schema` fails with "extracted field '...' is not present among names of engine fields", invalid `rir_field_names` are auto-stripped and the update retried [#221](https://github.com/stancld/rossum-agents/pull/221)

## [1.3.6] - 2026-03-02

### Fixed
- Fixed Rossum Elis OpenAPI spec URL — upstream renamed `openapi.external.json` to `openapi.json`, breaking spec downloads
- Fixed path traversal vulnerability in document upload — `DocumentContent.filename` is now stripped to its bare name via `Path.name` at both the schema validation layer and the file write site, preventing absolute path injection (e.g. `/etc/cron.d/backdoor`) from writing outside the session output directory

## [1.3.5] - 2026-02-26

### Fixed
- Haiku model calls now respect `AWS_BEDROCK_MODEL_ARN_SMALL` env var (mirrors `AWS_BEDROCK_MODEL_ARN` for Opus)

## [1.3.4] - 2026-02-26

### Changed
- Hidden `create_queue` tool — agent now uses `create_queue_from_template` exclusively; if the template is unknown, the agent asks the user and presents options grouped by category ([#218](https://github.com/rossumai/rossum-agents/pull/218))
- Added queue template guidance to base prompt — lists available templates grouped by category (standard invoices, AP&R, tax invoices, specialty, other) ([#218](https://github.com/rossumai/rossum-agents/pull/218))
- Chat summary generation now uses AWS Bedrock (`create_async_bedrock_client`) instead of the direct Anthropic API

## [1.3.3] - 2026-02-26

### Added
- Added `/history` slash command — lists past chat sessions with timestamps, message counts, and summaries/previews; accepts optional `<limit>` argument (default: 20)
- Added `run_jq` and `run_grep` tools — general-purpose data tools for querying and filtering JSON/structured data with jq expressions and searching tool results with regex patterns ([#217](https://github.com/stancld/rossum-agents/pull/217))

### Fixed
- Fixed several chat summary issues: now updates incrementally instead of regenerating from scratch, correctly extracts `first_message` from `task_step` format, and no longer overwrites an existing summary with `None` on failure
- Fixed rule creation workflow — added `suggest_rule` tool that uses Rossum Local Copilot to generate trigger conditions and actions from natural language; updated rules-and-actions skill to use suggest-then-create flow and removed `schema_id` from scope requirements ([#217](https://github.com/rossumai/rossum-agents/pull/217))

## [1.3.2] - 2026-02-25

### Fixed
- Fixed MDH dataset metadata lookup failing when the endpoint returns a redirect

## [1.3.1] - 2026-02-25

### Changed
- Agent now calls `update_task` with `in_progress`/`completed` status transitions during multi-step operations for real-time progress visibility

### Fixed
- MDH dataset metadata endpoint failures now log the full exception traceback for easier debugging

## [1.3.0] - 2026-02-24

### Added
- Added `summary` field to chat list response (`GET /api/v1/chats`) — auto-generated one-line summary via Claude Haiku after each turn, persisted in chat metadata [#208](https://github.com/stancld/rossum-agents/pull/208)
- Added agent persona support (`default`, `cautious`) — settable at chat creation (`POST /api/v1/chats`) and overridable per message; persisted in chat metadata [#199](https://github.com/stancld/rossum-agents/pull/199)
- Added `/persona` slash command with argument suggestions for dynamic persona switching [#213](https://github.com/stancld/rossum-agents/pull/213)
- Added `SnapshotStore` — Redis-backed store (7-day TTL) that indexes full entity snapshots by `(entity_type, entity_id, commit_hash)` for point-in-time restore [#200](https://github.com/stancld/rossum-agents/pull/200)
- Added `show_entity_history` tool — lists all historical versions of a specific entity [#200](https://github.com/stancld/rossum-agents/pull/200)
- Added `restore_entity_version` tool — restores an entity to a specific historical version by commit hash [#200](https://github.com/stancld/rossum-agents/pull/200)
- Added `diff_objects` tool — computes unified diff between two JSON objects for explicit comparison requests [#200](https://github.com/stancld/rossum-agents/pull/200)
- Added slash commands — intercepted in the message endpoint before reaching the agent, with `GET /commands` endpoint for TUI discovery [#207](https://github.com/stancld/rossum-agents/pull/207): `/list-commands` (list all slash commands), `/list-commits` (list configuration commits in current chat), `/list-skills` (list loadable agent skills with slugs), `/list-mcp-tools` (list MCP tools grouped by category from cached catalog), `/list-agent-tools` (list built-in agent tools with descriptions)
- Reverted commits are now marked with a `[REVERTED]` badge in `/list-commits` output; `show_change_history` also exposes a `reverted` field per commit [#210](https://github.com/stancld/rossum-agents/pull/210)
- Added `document-testing` skill and `generate_mock_pdf` tool for uploading mocked documents to Rossum queues — generates realistic multi-page PDFs with configurable field values for testing extraction pipelines [#215](https://github.com/stancld/rossum-agents/pull/215)

### Changed
- `revert_commit` no longer restricted to the latest commit — any historical commit can now be reverted [#200](https://github.com/stancld/rossum-agents/pull/200)
- Increased max tool result length from 20 000 to 30 000 characters
- Upgraded FastMCP dependency from 2.x to 3.0 [#201](https://github.com/stancld/rossum-agents/pull/201)

### Fixed
- Fixed schema revert failing under concurrent modifications — now retries with backoff on HTTP 412 (up to 5 attempts) using fetch-then-patch to register current state before each write [#200](https://github.com/stancld/rossum-agents/pull/200)
- Fixed Bedrock 400 errors silently hanging the agent — producer exceptions are now propagated through the event queue so the client receives a proper error response

## [1.2.1] - 2026-02-18

### Added
- Added `lookup-fields` skill and `suggest_lookup_field`, `evaluate_lookup_field`, `get_lookup_dataset_raw_values`, `query_lookup_dataset` tools for creating and testing lookup fields backed by Master Data Hub datasets [#183](https://github.com/stancld/rossum-agents/pull/183)

### Changed
- Schema patching sub-agent pre-fetches schema tree structure and full schema content before invoking Opus, eliminating 2 redundant tool calls per patching run and reducing `max_iterations` from 5 to 3 [#196](https://github.com/stancld/rossum-agents/pull/196)

## [1.2.0] - 2026-02-17

### Added
- Added tool call and result persistence in conversation history for full replay in multi-turn conversations [#184](https://github.com/stancld/rossum-agents/pull/184)
- Moved `rossum-kb.json` into the `rossum_agent` package so it is included in installed distributions [#185](https://github.com/stancld/rossum-agents/pull/185)
- Added tool call argument logging in `_execute_tool_with_progress` for debugging agent behavior [#192](https://github.com/stancld/rossum-agents/pull/192)
- Added configuration change tracking system that records every mutation as a `ConfigCommit` with before/after snapshots, LLM-generated commit messages, and Redis persistence [#185](https://github.com/stancld/rossum-agents/pull/185)
- Added `show_change_history`, `show_commit_details`, and `revert_commit` agent tools for querying and managing configuration changes [#185](https://github.com/stancld/rossum-agents/pull/185)
- Extended `MCPConnection` with transparent read caching and write interception for change tracking [#185](https://github.com/stancld/rossum-agents/pull/185)
- Added config commit info (`config_commit_hash`, `config_commit_message`, `config_changes_count`) to `StreamDoneEvent` for TUI integration [#185](https://github.com/stancld/rossum-agents/pull/185)

### Changed
- Collapse repeated collapsible tool results (e.g. `patch_schema`) in `AgentMemory.write_to_messages()` — only the last result is sent in full to the LLM, earlier results are replaced with a short summary to reduce context bloat [#192](https://github.com/stancld/rossum-agents/pull/192)
- Changed `prune_schema_fields` `fields_to_keep` behavior — sections are no longer auto-included; list section IDs explicitly to preserve them as empty containers for `patch_schema` [#191](https://github.com/stancld/rossum-agents/pull/191)
- Simplified Knowledge Base cache — use bundled `data/rossum-kb.json` instead of downloading from a remote URL with disk caching [#187](https://github.com/stancld/rossum-agents/pull/187)

### Fixed
- Fixed schema patching sub-agent silently dropping fields when `parent_section` doesn't exist — now auto-creates the missing section [#189](https://github.com/stancld/rossum-agents/pull/189)
- Stagger concurrent `patch_schema` tool calls (0.5s delay between each) to avoid HTTP 412 conflicts from simultaneous schema writes [#192](https://github.com/stancld/rossum-agents/pull/192)

### Removed
- Removed `refresh_knowledge_base` function and `ROSSUM_KB_DATA_URL` env var (no longer needed with bundled data) [#187](https://github.com/stancld/rossum-agents/pull/187)
- Removed `httpx` dependency from `knowledge_base_search` module [#187](https://github.com/stancld/rossum-agents/pull/187)


## [1.1.4] - 2026-02-12

### Added
- Added `txscript` skill — standalone TxScript language reference for formula fields, serverless functions, and rule trigger conditions [#176](https://github.com/stancld/rossum-agents/pull/176)
- Added `fields_to_update` support to schema patching sub-agent for updating existing field properties (formula, label, type, ui_configuration) without removing and re-adding fields [#181](https://github.com/stancld/rossum-agents/pull/181)
- Added `formula` property support to `_build_field_node` so new formula fields retain their formula code [#181](https://github.com/stancld/rossum-agents/pull/181)

### Fixed
- Fixed schema patching sub-agent inability to update existing formula fields — previously only supported add/remove, now supports in-place updates via `action: "update"` [#181](https://github.com/stancld/rossum-agents/pull/181)
- Updated `schema-patching` and `formula-fields` skills with guidance on updating existing fields and explanation of why `update_schema` is intentionally hidden [#181](https://github.com/stancld/rossum-agents/pull/181)

### Changed
- Replaced local hook sandbox (`evaluate_python_hook`, `debug_hook`) with native Rossum API endpoint (`test_hook` MCP tool) [#176](https://github.com/stancld/rossum-agents/pull/176)
- Refactored `formula-fields` and `rules-and-actions` skills — extracted inline TxScript reference to the new `txscript` skill [#176](https://github.com/stancld/rossum-agents/pull/176)

### Removed
- Removed `hook-debugging` skill (hook testing now uses MCP tools directly) [#176](https://github.com/stancld/rossum-agents/pull/176)
- Removed hook debug sub-agent (`HookDebugSubAgent`, `debug_hook`, `evaluate_python_hook`) [#176](https://github.com/stancld/rossum-agents/pull/176)

## [1.1.3] - 2026-02-12

### Fixed
- Upgraded `rossum-api` dependency to fix hook-template deserialization


## [1.1.2] - 2026-02-11

### Added
- Added Slack integration: `POST /chats/{chat_id}/report-to-slack` endpoint to send chat transcripts to a Slack channel via `slack-sdk`, available as an optional `slack` extra [#178](https://github.com/stancld/rossum-agents/pull/178)

### Fixed
- Fixed output files lost after SSE keepalive by moving chat-bound state (`output_dir`, `last_memory`) off context vars to `_ChatRunState` keyed by chat_id — `asyncio.create_task()` in keepalive copied the context, so mutations inside the task never propagated back to the caller

## [1.1.1] - 2026-02-10

### Added
- Added SSE keepalive mechanism to prevent reverse proxies from dropping connections during prolonged agent thinking periods [#174](https://github.com/stancld/rossum-agents/pull/174)

## [1.1.0] - 2026-02-09

### Added
- Added API request cancellation: explicit `POST /chats/{chat_id}/cancel` endpoint, automatic cancellation on client disconnect, and automatic cancellation of superseded requests when a new message is sent to the same chat [#165](https://github.com/stancld/rossum-agents/pull/165)
- Added prompt caching (`cache_control`) for system prompt, tools, and conversation history to reduce input token costs by up to 90% on cached content [#161](https://github.com/stancld/rossum-agents/pull/161)
- Added `kb_grep` and `kb_get_article` tools for direct regex search and article retrieval from pre-scraped Knowledge Base articles [#161](https://github.com/stancld/rossum-agents/pull/161)
- Added `scrape_knowledge_base.py` script to scrape Rossum Knowledge Base via sitemap + Jina Reader and produce S3-hosted JSON [#161](https://github.com/stancld/rossum-agents/pull/161)
- Added task tracking system (`create_task`, `update_task`, `list_tasks` tools) for real-time progress visibility on multi-step operations, streamed via SSE `task_snapshot` events [#157](https://github.com/stancld/rossum-agents/pull/157)
- Added `search_elis_docs` sub-agent tool with `elis_openapi_jq` and `elis_openapi_grep` for querying the Rossum API OpenAPI specification directly [#154](https://github.com/stancld/rossum-agents/pull/154)
- Added Gunicorn server support for production deployments via `--server gunicorn` CLI flag [#152](https://github.com/stancld/rossum-agents/pull/152)
  - Gunicorn is now bundled with the `api` extra
  - Uses UvicornWorker for ASGI compatibility
- Added `prompt` and `context` field support to schema patching sub-agent for reasoning fields [#162](https://github.com/stancld/rossum-agents/pull/162)
- Added `rules-and-actions` skill for creating validation rules with TxScript trigger conditions and actions via `create_rule` [#167](https://github.com/stancld/rossum-agents/pull/167)
- Added `formula-fields` skill for creating/configuring formula fields with TxScript reference, messaging functions, and common patterns [#169](https://github.com/stancld/rossum-agents/pull/169)
- Added `reasoning-fields` skill for creating AI-powered reasoning fields with prompt/context configuration and instruction-writing guidance [#169](https://github.com/stancld/rossum-agents/pull/169)

### Changed
- Token usage breakdown now includes cache creation and cache read input token metrics [#161](https://github.com/stancld/rossum-agents/pull/161)
- Replaced live DuckDuckGo-based `search_knowledge_base` with pre-scraped KB articles using local `kb_grep`/`kb_get_article` tools [#161](https://github.com/stancld/rossum-agents/pull/161)
- Migrated default model from Opus 4.5 to Opus 4.6 [#156](https://github.com/stancld/rossum-agents/pull/156)
- Refactored API to use FastAPI's `app.state` for service instances instead of module-level globals [#153](https://github.com/stancld/rossum-agents/pull/153)
- Replaced `websockets` dependency with `wsproto` to fix deprecation warnings on Python 3.14
- Lazy load deploy tools only when `rossum-deployment` skill is activated [#164](https://github.com/stancld/rossum-agents/pull/164)

### Fixed
- Fixed default column list in `ui-settings` skill — removed non-existent `created_by`/`modified_by` meta names, added correct `modifier` [#172](https://github.com/stancld/rossum-agents/pull/172)
- Added read-only mode warning: agent now immediately stops and warns the user when a write operation is requested in read-only mode, instead of attempting and failing [#172](https://github.com/stancld/rossum-agents/pull/172)
- Task tracker tasks are now created in planned execution order for consistent progress display [#172](https://github.com/stancld/rossum-agents/pull/172)
- Fixed schema patching sub-agent: excluded `update_schema` from available tools to prevent accidental full-schema overwrites [#161](https://github.com/stancld/rossum-agents/pull/161)
- Fixed token counting to include cache creation and cache read tokens in input totals for accurate usage reporting [#161](https://github.com/stancld/rossum-agents/pull/161)
- Fixed incorrect field names (`is_formula`/`is_reasoning`) in base prompt — replaced with correct API field names [#161](https://github.com/stancld/rossum-agents/pull/161)

### Removed
- Removed `ddgs` dependency (replaced by pre-scraped KB article search) [#161](https://github.com/stancld/rossum-agents/pull/161)
- Removed Streamlit UI (`streamlit_app` submodule and all Streamlit dependencies) [#160](https://github.com/stancld/rossum-agents/pull/160)
- Removed Teleport JWT user isolation (`user_detection.py`, `PyJWT`, `cryptography` dependencies) [#155](https://github.com/stancld/rossum-agents/pull/155)

## [1.0.0] - 2026-02-05

### Added
- Added `create_schema_with_subagent` tool for creating new schemas from scratch via Opus sub-agent [#151](https://github.com/stancld/rossum-agents/pull/151)
- Added `schema-creation` skill documenting content array structure (sections, datapoints, multivalues, tuples) [#151](https://github.com/stancld/rossum-agents/pull/151)
- Added message-level `mcp_mode` parameter to override chat's mode per-message and persist for subsequent messages [#147](https://github.com/stancld/rossum-agents/pull/147)
- Added token usage visibility with breakdown by main agent vs sub-agents in API responses and Streamlit UI [#141](https://github.com/stancld/rossum-agents/pull/141)
- Added dynamic tool loading to reduce initial context usage (~8K → ~800 tokens) [#113](https://github.com/stancld/rossum-agents/pull/113)
- Added `load_tool_category(["queues", "schemas"])` internal tool to load MCP tools on-demand [#113](https://github.com/stancld/rossum-agents/pull/113)
- Added automatic pre-loading of tool categories based on keywords in user's first message [#113](https://github.com/stancld/rossum-agents/pull/113)
- Added read-only mode support - write tools (`read_only=false`) are excluded when MCP runs in read-only mode [#141](https://github.com/stancld/rossum-agents/pull/141)
- Added PDF document upload support for both REST API and Streamlit UI. Documents are stored in session output directory for agent use (e.g., upload to Rossum) [#102](https://github.com/stancld/rossum-agents/pull/102)
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
- Execute multiple tool calls in parallel using `asyncio.wait()` instead of sequential execution [#127](https://github.com/stancld/rossum-agents/pull/127)
- Migrated knowledge base search from sync `requests` to async `httpx` with parallel webpage fetching via `asyncio.gather()` [#127](https://github.com/stancld/rossum-agents/pull/127)
- Refactored sub-agents (hook_debug, schema_patching, knowledge_base) to shared `SubAgent` base class with unified iteration loop [#107](https://github.com/stancld/rossum-agents/pull/107)
- Added token tracking to all sub-agents with counts propagated via `SubAgentResult` [#107](https://github.com/stancld/rossum-agents/pull/107)
- Migrated default model from Sonnet 4.5 to Opus 4.5 with significantly simplified prompts [#99](https://github.com/stancld/rossum-agents/pull/99)
- Separated model's chain-of-thought reasoning (thinking blocks) from response text (text blocks) in stream processing [#92](https://github.com/stancld/rossum-agents/pull/92)
- Updated Streamlit UI to display thinking blocks with "🧠 **Thinking:**" label [#92](https://github.com/stancld/rossum-agents/pull/92)
- Refactored `internal_tools.py` into modular `tools/` subpackage with separate modules for file tools, spawn MCP, knowledge base search, hook debugging, and skills [#78](https://github.com/stancld/rossum-agents/pull/78)
- Reorganized sub-agent tools into `tools/subagents/` module (hook_debug, knowledge_base, schema_patching) [#102](https://github.com/stancld/rossum-agents/pull/102)
- Improved multi-turn conversation by passing context properly [#73](https://github.com/stancld/rossum-agents/pull/73)
- Improved sub-agent knowledge base info panel [#73](https://github.com/stancl/rossum-mcp/pull/73)
- Made token owner selection stricter in deployment tools [#73](https://github.com/stancld/rossum-agents/pull/73)
- Display workspace diffs in a concise way [#73](https://github.com/stancld/rossum-agents/pull/73)
- Improved result analyzing UX for sub-agent responses [#85](https://github.com/stancld/rossum-agents/pull/85)

### Removed
- Removed test front-end from rossum-agent API as it doesn't fit the repo scope [#83](https://github.com/stancld/rossum-agents/pull/83)

### Fixed
- Fixed concurrent API request handling by isolating per-request state with contextvars [#148](https://github.com/stancld/rossum-agents/pull/148)
- Fixed `write_file` tool to accept dict/list content by auto-converting to JSON [#139](https://github.com/stancld/rossum-agents/pull/139)
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
