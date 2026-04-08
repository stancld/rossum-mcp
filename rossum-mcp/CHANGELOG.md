# Changelog - Rossum MCP

All notable changes to this project will be documented in this file.

---

## [2.1.3] - 2026-04-08

### Added
- Schema models now expose additional fields: `description`, `can_collapse`, `aggregations` on datapoints; `disable_prediction`, `rir_field_names` on tuples; `disable_prediction`, `grid`, `show_grid_by_default` on multivalues — all settable via `patch_schema` [#347](https://github.com/stancld/rossum-agents/pull/347)

### Changed
- Bump `fastmcp` dependency from `>=2.-.0` to `>=3.2.0`


## [2.1.2] - 2026-03-31

### Fixed
- Switch `graceful_list` to cursor-based pagination (`cursor_fetch_all`) to avoid silently returning empty results on large collections [#341](https://github.com/stancld/rossum-agents/pull/341)


## [2.1.1] - 2026-03-31

### Fixed
- Batch `get` (list of IDs) now silently skips failed items instead of raising on the first error [#339](https://github.com/stancld/rossum-agents/pull/339)


## [2.1.0] - 2026-03-30

### Added
- Schema responses from `get` and `search` now include resolved `workspaces` URLs (derived from linked queues); schema `search` also accepts a `workspace_id` filter to scope results to a specific workspace [#324](https://github.com/stancld/rossum-agents/pull/324)
- Hook responses from `get` and `search` now include resolved `workspaces` URLs (derived from linked queues); hook `search` also accepts a `workspace_id` filter to scope results to a specific workspace [#325](https://github.com/stancld/rossum-agents/pull/325)
- Rule responses from `get` and `search` now include resolved `workspaces` URLs (derived from linked queues); rule `search` also accepts a `workspace_id` filter to scope results to a specific workspace [#330](https://github.com/stancld/rossum-agents/pull/330)
- Email template responses from `get` and `search` now include resolved `workspaces` URLs — workspace association is derived from the linked queue; email template `search` also accepts a `workspace_id` filter to scope results to a specific workspace [#331](https://github.com/stancld/rossum-agents/pull/331)
- Annotation responses from `get` and `search` now include resolved `workspaces` URLs — workspace association is derived from the linked queue; annotation `search` also accepts a `workspace_id` filter to scope results to a specific workspace [#333](https://github.com/stancld/rossum-agents/pull/333)

### Changed
- Lifted `first_n` from per-entity search models to a universal `first_n` parameter on the `search` tool — result limiting now works for all entity types, not just hooks, email templates, and annotations [#326](https://github.com/stancld/rossum-agents/pull/326)
- Bump `rossum-api` dependency from `>=3.12.1` to `>=3.13.1` — adds support for rule → queues many-to-many relation [#329](https://github.com/stancld/rossum-agents/pull/329)

### Removed
- Dropped `id` filter from `queue`, `engine`, `relation`, and `document_relation` search queries — use the `get` tool to fetch a resource by ID instead [#327](https://github.com/stancld/rossum-agents/pull/327)

## [2.0.6] - 2026-03-25

### Added
- Added `after_field` and `before_field` parameters to `patch_schema` — fields can now be inserted relative to an existing sibling instead of only by numeric `position` or appending to the end; at most one positioning parameter (`position`, `after_field`, `before_field`) may be specified per call [#308](https://github.com/stancld/rossum-agents/pull/308)

## [2.0.5] - 2026-03-25

### Changed
- Moved `get_mcp_mode` tool from `server.py` into `tools/discovery.py` alongside other discovery tools — no functional change, aligns with the existing tool registration pattern [#304](https://github.com/stancld/rossum-agents/pull/304)

## [2.0.4] - 2026-03-23

### Fixed
- Added missing `format` field to `SchemaDatapoint` and `SchemaNodeUpdate` — date fields with custom formats (e.g. `M/D/YYYY`) can now be created and updated via `patch_schema` without losing their format configuration [#299](https://github.com/stancld/rossum-agents/pull/299)

## [2.0.3] - 2026-03-18

### Fixed
- Fixed `create_engine_field` sending `multiline` as Python bool (`True`/`False`) instead of API-expected lowercase string (`"true"`/`"false"`) [#280](https://github.com/stancld/rossum-agents/pull/280)

### Changed
- `get_schema_tree_structure` now includes boolean `required` and `hidden` flags on every node; datapoints map `required` from `constraints.required` and default to `false` when unset [#279](https://github.com/stancld/rossum-agents/pull/279)

## [2.0.2] - 2026-03-17

### Changed
- Bump `rossum-api` dependency from `>=3.11.2` to `>=3.12.0` [#276](https://github.com/stancld/rossum-agents/pull/276)
- Replaced `Literal` type aliases with `StrEnum` classes for all tool parameters — `AutomationLevel`, `QueueLocale`, `DatapointType`, `QueueTemplateName`, `EmailTemplateType`, `HookSideload`, `EngineType`, `DeleteEntityType`, `EntityType`, `PatchOperation`, and search-model types (`LogLevel`). Enums provide named members, iteration support, and consistent JSON schema representation [#269](https://github.com/stancld/rossum-agents/pull/269)
- Removed duplicate `DatapointType` Literal from `update/models.py` — now imported from `tools/models.py` [#269](https://github.com/stancld/rossum-agents/pull/269)

## [2.0.1] - 2026-03-16

### Fixed
- Added `matching` and `enum_value_type` fields to `SchemaDatapoint` and `SchemaNodeUpdate` — lookup fields can now be created and updated via `patch_schema` without losing their matching configuration

### Removed
- Removed `update_rule` tool (PUT) — use `patch_rule` (PATCH) instead, which handles both partial and full updates [#259](https://github.com/stancld/rossum-agents/pull/259)

## [2.0.0] - 2026-03-09

### Added
- Added `get` tool: fetch any entity by ID with a single unified tool — supports `queue`, `schema`, `hook`, `engine`, `rule`, `user`, `workspace`, `email_template`, `organization_group`, `organization_limit`, `annotation`, `relation`, `document_relation`, `hook_secrets_keys`; `include_related=True` enriches with linked data (queue→schema_tree+engine+hooks, schema→queues+rules, hook→queues+events) [#221](https://github.com/stancld/rossum-agents/pull/221)
- Added `search` tool: list/filter any entity with typed, entity-specific query objects — covers all `get`-supported types except `organization_limit` and `hook_secrets_keys` (get-only), plus search-only entities `hook_log`, `hook_template`, `user_role`, `queue_template_name` [#221](https://github.com/stancld/rossum-agents/pull/221)
- Added `hook_secrets_keys` entity to the `get` tool — returns stored secret key names for a hook (values are write-only, never returned) [#247](https://github.com/stancld/rossum-agents/pull/247)

### Changed
- Error handling in MCP tools now uses `raise ToolError(...)` instead of `return {"error": ...}` dicts — FastMCP surfaces these as proper MCP error responses, and return types are tightened by removing `| dict` unions [#236](https://github.com/stancld/rossum-agents/pull/236)
- `create_queue` and `update_queue` parameters `locale` and `automation_level` are now `Literal` types instead of plain strings — LLMs see valid values directly in the JSON schema [#237](https://github.com/stancld/rossum-agents/pull/237)
- `create_email_template` parameters `to`, `cc`, `bcc` are now typed `EmailRecipient` dicts instead of untyped `dict[str, Any]` [#237](https://github.com/stancld/rossum-agents/pull/237)
- `update_queue` parameter `queue_data` is now a typed `QueueUpdateData` schema instead of an untyped dict — LLMs see valid field names and types directly in the JSON schema [#221](https://github.com/stancld/rossum-agents/pull/221)
- `update_engine` parameter `engine_data` is now a typed `EngineUpdateData` schema instead of an untyped dict [#221](https://github.com/stancld/rossum-agents/pull/221)
- `create_engine_field` parameter `multiline` changed from `str` to `bool` [#221](https://github.com/stancld/rossum-agents/pull/221)
- **Breaking**: `create_hook` now maps `config.source` to `config.code` (previously mapped to `config.function`) to match the current API field name [#221](https://github.com/stancld/rossum-agents/pull/221)

### Removed
- Removed `are_lookup_fields_enabled` and `are_reasoning_fields_enabled` tools — feature availability is inferred by the agent from organization group data via the `get` / `search` tools
- Removed `update_schema` tool — use `patch_schema` for individual field changes or `prune_schema_fields` for bulk removal [#245](https://github.com/stancld/rossum-agents/pull/245)
- Removed `create_queue` tool — use `create_queue_from_template` instead [#245](https://github.com/stancld/rossum-agents/pull/245)
- Removed `create_schema` tool — use `patch_schema` to build schemas incrementally [#244](https://github.com/stancld/rossum-agents/pull/244)
- Removed `set_mcp_mode` tool — mode is now set exclusively via the `ROSSUM_MCP_MODE` environment variable at server startup [#249](https://github.com/stancld/rossum-agents/pull/249)
- Removed generic `"template"` keyword from `email_templates` category to reduce false-positive tool pre-loads (e.g., queue template queries no longer trigger email template tools)
- **Breaking**: Replaced 25+ individual read tools with the unified `get` and `search` tools. Removed standalone tools: `get_annotation`, `list_annotations`, `get_queue`, `list_queues`, `get_queue_schema`, `get_queue_engine`, `get_schema`, `list_schemas`, `get_hook`, `list_hooks`, `list_hook_logs`, `list_hook_templates`, `get_engine`, `list_engines`, `get_email_template`, `list_email_templates`, `get_user`, `list_users`, `list_user_roles`, `get_organization_group`, `list_organization_groups`, `get_rule`, `list_rules`, `get_workspace`, `list_workspaces`, `get_relation`, `list_relations`, `get_document_relation`, `list_document_relations`, `get_organization_limit` [#221](https://github.com/stancld/rossum-agents/pull/221)
- **Breaking**: Replaced 6 individual delete tools with the unified `delete` tool. Removed standalone tools: `delete_queue`, `delete_schema`, `delete_hook`, `delete_rule`, `delete_workspace`, `delete_annotation` [#229](https://github.com/stancld/rossum-agents/pull/229)
- Removed `get_queue_template_names` — use `search(query={"entity": "queue_template_name"})` instead [#231](https://github.com/stancld/rossum-agents/pull/231)
- Removed dead validation code (`_validate_node`, `_validate_id`, `_validate_datapoint`, `_validate_tuple`, `_validate_multivalue`, `_validate_section`, `SchemaValidationError`) superseded by the sanitization approach in `sanitize_schema_content`

### Fixed
- `create_hook` and `update_hook` now expose `token_owner`, `run_after`, `secrets`, and `sideload` parameters — previously these fields were missing from the tool signatures [#247](https://github.com/stancld/rossum-agents/pull/247)

## [1.4.1] - 2026-02-26

### Added
- `get_annotation_content` tool: fetches annotation extracted content and saves it to `/tmp/rossum_annotation_{id}_content.json`; returns the local path for `jq`/`grep` processing

### Changed
- `get_annotation` no longer accepts a `sideloads` parameter; use `get_annotation_content` to retrieve extracted fields

## [1.4.0] - 2026-02-24

### Changed
- `create_queue_from_template` now fetches the schema and engine created as side effects and embeds them in the return value as `_tracked_resources` for rossum-agent's change tracking and point-in-time restore [#200](https://github.com/stancld/rossum-agents/pull/200)
- Upgraded FastMCP dependency to `>=3.0.0` — changes transitive dependencies and may affect MCP client compatibility [#201](https://github.com/stancld/rossum-agents/pull/201)
- Read-only mode enforcement rewritten: `mcp.disable(tags={"write"})` replaces per-tool `is_read_write_mode()` checks, making read-only enforcement more reliable [#201](https://github.com/stancld/rossum-agents/pull/201)
- All 70 tools now declare `readOnlyHint` and `destructiveHint` MCP annotations; MCP clients can use these for UI hints and safety checks [#201](https://github.com/stancld/rossum-agents/pull/201)
- `list_tool_categories` and `list_tools_by_category` now use dynamic tag-based discovery via FastMCP instead of the static `TOOL_CATALOG` dict [#201](https://github.com/stancld/rossum-agents/pull/201)
- `list_queues` now returns `QueueListItem` summary objects instead of truncated `Queue` objects — `settings` is omitted entirely (`"<omitted>"`) rather than field-truncated [#206](https://github.com/stancld/rossum-agents/pull/206)
- `list_queues`, `list_workspaces`, `list_schemas`, `list_email_templates`, and `list_organization_groups` now accept regex patterns in the `name` filter parameter [#206](https://github.com/stancld/rossum-agents/pull/206)

## [1.3.0] - 2026-02-18

### Added
- Added `copy_annotations` tool for bulk copying annotations to another queue via `POST /v1/annotations/{id}/copy` with optional `reimport` and `target_status` parameters [#195](https://github.com/stancld/rossum-agents/pull/195)
- Added `are_lookup_fields_enabled` tool to check whether lookup fields are available — returns `{"enabled": bool}` based on whether both `datasets` and `lookup_fields` features are enabled in any organization group
- Added `are_reasoning_fields_enabled` tool to check whether reasoning fields are available — returns `{"enabled": bool}` based on whether the `reasoning_fields` feature is enabled in any organization group

## [1.2.3] - 2026-02-17

### Changed
- `patch_schema` now returns a concise confirmation dict (`status`, `schema_id`, `operation`, `node_id`, `node`) instead of the full schema object to reduce context bloat [#192](https://github.com/stancld/rossum-agents/pull/192)
- `update_schema`, `patch_schema`, and `prune_schema_fields` now allow empty content — previously these operations rejected empty schema content, preventing intentional clearing of all fields

### Fixed
- Fixed `prune_schema_fields` treating `fields_to_keep=[]` and `fields_to_remove=[]` as unset — empty lists were evaluated as falsy, causing "Must specify fields_to_keep or fields_to_remove" errors instead of pruning all/no fields ([#188](https://github.com/stancld/rossum-agents/pull/188))

## [1.2.2] - 2026-02-12

### Added
- Added `test_hook` tool for testing hooks — auto-generates a realistic payload via `/generate_payload` and executes it via `POST /v1/hooks/{hook_id}/test`

## [1.2.1] - 2026-02-12

### Fixed
- Fixed `list_hook_templates` returning only ~3 templates due to excessive context — after `rossum-api` upgrade, `HookTemplate` became a dataclass with many verbose fields (guide, config, settings, schemas, etc.) that filled the context window. Now uses `dataclasses.replace()` to truncate these fields, returning all templates. [#182](https://github.com/stancld/rossum-agents/pull/182)

## [1.2.0] - 2026-02-09

### Added
- Added `create_user` tool for creating new users with full field support (queues, groups, metadata, auth_type, OIDC) [#163](https://github.com/stancld/rossum-agents/pull/163)
- Added `update_user` tool for partial update (PATCH) of existing users [#163](https://github.com/stancld/rossum-agents/pull/163)
- Added `get_organization_group` and `list_organization_groups` tools for viewing organization group (license) details [#170](https://github.com/stancld/rossum-agents/pull/170)
- Added `get_organization_limit` tool for retrieving email sending limits and usage counters for an organization [#170](https://github.com/stancld/rossum-agents/pull/170)

### Changed
- `create_hook` and `update_hook` now use `HookEventAndAction` enum for the `events` parameter, exposing valid event values directly in the JSON schema so the LLM picks from enumerated options instead of guessing [#173](https://github.com/stancld/rossum-agents/pull/173)
- `get_schema_tree_structure` now accepts `queue_id` as an alternative to `schema_id` — resolves the queue's schema automatically [#151](https://github.com/stancld/rossum-agents/pull/151)
- Optimized all MCP tool descriptions for Opus 4.5/4.6 — replaced procedural/warning preambles (`IMPORTANT`, `CRITICAL`, `ALWAYS`) with concise constraint-based descriptions, removed redundancy with type hints, compressed multi-paragraph descriptions [#166](https://github.com/stancld/rossum-agents/pull/166)

### Removed
- Removed `RedisHandler` from `logging_config` — Redis log storage is no longer part of rossum-mcp. Agent chat history (via `RedisStorage` in rossum-agent) is unaffected.

### Fixed
- `create_schema`, `update_schema`, and `prune_schema_fields` now reject empty schema content instead of sending it to the API and wiping all fields [#172](https://github.com/stancld/rossum-agents/pull/172)
- `update_queue` now validates `annotation_list_table` column `meta_name` values against the set of valid meta names, preventing silent API 400 errors [#172](https://github.com/stancld/rossum-agents/pull/172)
- `create_hook`, `update_hook`, and `create_hook_from_template` now validate hook event strings against the `event.action` format before API call, with clear error listing valid values [#172](https://github.com/stancld/rossum-agents/pull/172)
- `patch_schema` and `prune_schema_fields` now retry up to 3 times on HTTP 412 Precondition Failed (concurrent schema modification), with linear backoff
- Fixed `create_rule` and `update_rule` requiring `schema_id` — now optional to match the API. Rules can be scoped by `queue_ids` alone; at least one of `schema_id` or `queue_ids` is required [#156](https://github.com/stancld/rossum-agents/pull/156)
- List tools now gracefully skip items that fail to deserialize instead of aborting the entire listing. A single broken item in a customer organization (API errors, unexpected data) no longer causes the agent to fail mid-run. Affected tools: `list_annotations`, `list_document_relations`, `list_email_templates`, `list_engines`, `list_hooks`, `list_hook_logs`, `list_queues`, `list_relations`, `list_rules`, `list_schemas`, `list_users`, `list_user_roles`, `list_workspaces`. [#158](https://github.com/stancld/rossum-agents/pull/158)
- Fixed `patch_schema`, `update_schema`, and `prune_schema_fields` failing with HTTP 400 when schema contains `stretch`, `width`, `can_collapse`, or `width_chars` attributes on fields outside multivalue-tuples. These attributes are now automatically stripped from non-tuple fields. [#151](https://github.com/stancld/rossum-agents/pull/151)


## [1.1.1] - 2026-02-05

### Fixed
- Fixed `create_schema` and `patch_schema` failing with HTTP 400 when schema contains invalid `ui_configuration.type` values (e.g., 'area', 'textarea'). Invalid values are now automatically sanitized before API calls.


## [1.1.0] - 2026-02-04

### Added
- Added `get_mcp_mode` tool to query current MCP operation mode (read-only or read-write)
- Added `set_mcp_mode` tool to dynamically switch MCP mode at runtime without server restart
- Added `create_rule` tool for creating business rules with trigger conditions and actions
- Added `update_rule` tool for full update (PUT) of business rules
- Added `patch_rule` tool for partial update (PATCH) of business rules


## [1.0.1] - 2026-01-31

### Changed
- Renamed `destructive` field to `read_only` in tool catalog for clearer semantics (tools with `read_only=false` are write operations)


## [1.0.0] - 2026-01-28

### Added
- Added `delete_queue` tool for queue deletion (24h delayed start) [#141](https://github.com/stancld/rossum-agents/pull/141)
- Added `delete_workspace` tool for workspace deletion [#141](https://github.com/stancld/rossum-agents/pull/141)
- Added `delete_schema` tool for schema deletion [#141](https://github.com/stancld/rossum-agents/pull/141)
- Added `delete_hook` tool for hook deletion [#141](https://github.com/stancld/rossum-agents/pull/141)
- Added `delete_annotation` tool for annotation deletion (soft delete) [#141](https://github.com/stancld/rossum-agents/pull/141)
- Added `delete_rule` tool for rule deletion [#141](https://github.com/stancld/rossum-agents/pull/141)

### Changed
- Added `id` parameter to `list_queues` tool for filtering by queue ID [#136](https://github.com/stancld/rossum-agents/pull/136)
- Documented `create_hook` config transformations: `source`→`function` rename, `runtime` default, `timeout_s` cap [#134](https://github.com/stancld/rossum-agents/pull/134)

### Fixed
- Fixed `StopAsyncIteration` crash in `list_hooks` and `list_email_templates` when `first_n` exceeds available items [#134](https://github.com/stancld/rossum-agents/pull/134)
- Fixed `get_schema` and `get_schema_tree_structure` tools crashing with unhandled exception when schema not found (404); now returns error dict


## [0.4.0] - 2026-01-18

### Added
- Added dynamic tool discovery system with `list_tool_categories` MCP tool [#113](https://github.com/stancld/rossum-agents/pull/113)
- Added tool catalog (`catalog.py`) with categories, keywords, and tool metadata for on-demand loading [#113](https://github.com/stancld/rossum-agents/pull/113)


## [0.3.5] - 2026-01-16
- Added `get_email_template` tool for retrieving a single email template by ID [#102](https://github.com/stancld/rossum-agents/pull/102)
- Added `list_email_templates` tool for listing email templates with optional filtering by queue, type, or name [#102](https://github.com/stancld/rossum-agents/pull/102)
- Added `create_email_template` tool for creating new email templates with recipient configuration [#102](https://github.com/stancld/rossum-agents/pull/102)
- Added `get_schema_tree_structure` tool for lightweight schema tree view with only ids, labels, categories, and types [#102](https://github.com/stancld/rossum-agents/pull/102)
- Added `prune_schema_fields` tool for efficiently removing multiple fields from schema at once (batch pruning) [#102](https://github.com/stancld/rossum-agents/pull/102)
- Added `create_queue_from_template` tool for creating queues from predefined templates (EU/US/UK/CZ/CN demo templates) [#102](https://github.com/stancld/rossum-agents/pull/102)
- Added `get_queue_template_names` tool for listing available queue template names [#102](https://github.com/stancld/rossum-agents/pull/102)
- Added `list_queues` tool for listing queues with optional filtering by workspace or name [#101](https://github.com/stancld/rossum-agents/pull/101)
- Added `list_schemas` tool for listing schemas with optional filtering by name or queue [#101](https://github.com/stancld/rossum-agents/pull/101)
- Enhanced `list_annotations` tool with `ordering` and `first_n` parameters for sorting and limiting results [#101](https://github.com/stancld/rossum-agents/pull/101)
- Added schema validation with clear error messages for datapoint, tuple, multivalue, and section nodes [#102](https://github.com/stancld/rossum-agents/pull/102)
- Improved multivalue node handling in `patch_schema` with explicit error when attempting to add children to multivalue nodes [#102](https://github.com/stancld/rossum-agents/pull/102)


## [0.3.4] - 2025-12-31
- Added `get_user` tool for retrieving a single user by ID [#75](https://github.com/stancld/rossum-agents/pull/75)
- Added `list_users` tool for user management and finding users for hook token owner configuration [#75](https://github.com/stancld/rossum-agents/pull/75)
- Added `list_user_roles` tool for listing all user roles (groups of permissions) in the organization [#75](https://github.com/stancld/rossum-agents/pull/75)
- Added `list_hook_templates` tool for listing available hook templates from Rossum Store [#75](https://github.com/stancld/rossum-agents/pull/75)
- Added `create_hook_from_template` tool for creating hooks from pre-built templates [#75](https://github.com/stancld/rossum-agents/pull/75)
- Added `update_hook` tool for modifying existing hook properties [#75](https://github.com/stancld/rossum-agents/pull/75)
- Added `patch_schema` tool for adding, updating, or removing individual schema nodes without replacing entire content [#75](https://github.com/stancld/rossum-agents/pull/75)


## [0.3.3] - 2025-12-16
- Added `list_hook_logs` tool for listing hook execution logs with filters for debugging and monitoring [#72](https://github.com/stancld/rossum-agents/pull/72)
- Added `job` as a valid hook type in `create_hook` tool [#72](https://github.com/stancld/rossum-agents/pull/72)
- Improved `list_hooks` and `get_hook` tool descriptions [#72](https://github.com/stancld/rossum-agents/pull/72)


## [0.3.2] - 2025-12-14
- Fixed allowed sideloads for `get_annotation` [#63](https://github.com/stancld/rossum-agents/pull/63)
- Refactored tools to return class instances directly instead of `dataclasses.asdict()` conversions,
leveraging FastMCP's automatic serialization [#64](https://github.com/stancld/rossum-agents/pull/64)


## [0.3.1] - 2025-12-09
- Upgrade minimal Rossum API version dependency to >= 3.7.0


## [0.3.0] - 2025-12-08
### Changed
- **Breaking**: Migrated from vanilla python-sdk MCP to FastMCP framework [#56](https://github.com/stancld/rossum-agents/pull/56)
  - Replaced class-based `handlers/` architecture with modular `tools/` registration pattern
  - Each domain (annotations, queues, schemas, etc.) now has its own tool module with `register_*_tools()` function
  - Restructured tests into `tests/tools/` directory mirroring the new module structure
  - Simplified server.py from ~200 lines to ~70 lines
  - Reduced overall codebase by ~2,000 lines of code


## [0.2.0] - 2025-12-06
- Modified logging configuration for Redis backend [#44](https://github.com/stancld/rossum-agents/pull/44)
- Unified `list_*` methods signature and usage [#49](https://github.com/stancld/rossum-agents/pull/49)
- Added `get_engine` and `list_engines` methods for `rossum_api.models.engine.Engine` objects. [#49](https://github.com/stancld/rossum-agents/pull/49)
- Added `get_hook` method for `rossum_api.models.hook.Hook` objects. [#49](https://github.com/stancld/rossum-agents/pull/49)
- Added `get_rule` method for `rossum_api.models.rule.Rule` objects. [#49](https://github.com/stancld/rossum-agents/pull/49)
- Added `get_engine_fields` method for `rossum_api.models.engine.EngineFields` objects. [#49](https://github.com/stancld/rossum-agents/pull/49)
- Added `get_relation` and `list_relations` methods for `rossum_api.models.relation.Relation` objects. [#50](https://github.com/stancld/rossum-agents/pull/50)
- Added `get_document_relation` and `list_document_relations` methods for `rossum_api.models.document_relation.DocumentRelation` objects. [#51](https://github.com/stancld/rossum-agents/pull/51)
