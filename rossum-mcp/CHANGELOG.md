# Changelog - Rossum MCP

All notable changes to this project will be documented in this file.

---

## [0.4.0] - 2026-01-18

### Added
- Added dynamic tool discovery system with `list_tool_categories` MCP tool [#113](https://github.com/stancld/rossum-mcp/pull/113)
- Added tool catalog (`catalog.py`) with categories, keywords, and tool metadata for on-demand loading [#113](https://github.com/stancld/rossum-mcp/pull/113)


## [0.3.5] - 2026-01-16
- Added `get_email_template` tool for retrieving a single email template by ID [#102](https://github.com/stancld/rossum-mcp/pull/102)
- Added `list_email_templates` tool for listing email templates with optional filtering by queue, type, or name [#102](https://github.com/stancld/rossum-mcp/pull/102)
- Added `create_email_template` tool for creating new email templates with recipient configuration [#102](https://github.com/stancld/rossum-mcp/pull/102)
- Added `get_schema_tree_structure` tool for lightweight schema tree view with only ids, labels, categories, and types [#102](https://github.com/stancld/rossum-mcp/pull/102)
- Added `prune_schema_fields` tool for efficiently removing multiple fields from schema at once (batch pruning) [#102](https://github.com/stancld/rossum-mcp/pull/102)
- Added `create_queue_from_template` tool for creating queues from predefined templates (EU/US/UK/CZ/CN demo templates) [#102](https://github.com/stancld/rossum-mcp/pull/102)
- Added `get_queue_template_names` tool for listing available queue template names [#102](https://github.com/stancld/rossum-mcp/pull/102)
- Added `list_queues` tool for listing queues with optional filtering by workspace or name [#101](https://github.com/stancld/rossum-mcp/pull/101)
- Added `list_schemas` tool for listing schemas with optional filtering by name or queue [#101](https://github.com/stancl/rossum-mcp/pull/101)
- Enhanced `list_annotations` tool with `ordering` and `first_n` parameters for sorting and limiting results [#101](https://github.com/stancld/rossum-mcp/pull/101)
- Added schema validation with clear error messages for datapoint, tuple, multivalue, and section nodes [#102](https://github.com/stancld/rossum-mcp/pull/102)
- Improved multivalue node handling in `patch_schema` with explicit error when attempting to add children to multivalue nodes [#102](https://github.com/stancl/rossum-mcp/pull/102)


## [0.3.4] - 2025-12-31
- Added `get_user` tool for retrieving a single user by ID [#75](https://github.com/stancld/rossum-mcp/pull/75)
- Added `list_users` tool for user management and finding users for hook token owner configuration [#75](https://github.com/stancld/rossum-mcp/pull/75)
- Added `list_user_roles` tool for listing all user roles (groups of permissions) in the organization [#75](https://github.com/stancld/rossum-mcp/pull/75)
- Added `list_hook_templates` tool for listing available hook templates from Rossum Store [#75](https://github.com/stancld/rossum-mcp/pull/75)
- Added `create_hook_from_template` tool for creating hooks from pre-built templates [#75](https://github.com/stancld/rossum-mcp/pull/75)
- Added `update_hook` tool for modifying existing hook properties [#75](https://github.com/stancld/rossum-mcp/pull/75)
- Added `patch_schema` tool for adding, updating, or removing individual schema nodes without replacing entire content [#75](https://github.com/stancld/rossum-mcp/pull/75)


## [0.3.3] - 2025-12-16
- Added `list_hook_logs` tool for listing hook execution logs with filters for debugging and monitoring [#72](https://github.com/stancld/rossum-mcp/pull/72)
- Added `job` as a valid hook type in `create_hook` tool [#72](https://github.com/stancld/rossum-mcp/pull/72)
- Improved `list_hooks` and `get_hook` tool descriptions [#72](https://github.com/stancld/rossum-mcp/pull/72)


## [0.3.2] - 2025-12-14
- Fixed allowed sideloads for `get_annotation` [#63](https://github.com/stancld/rossum-mcp/pull/63)
- Refactored tools to return class instances directly instead of `dataclasses.asdict()` conversions,
leveraging FastMCP's automatic serialization [#64](https://github.com/stancld/rossum-mcp/pull/64)


## [0.3.1] - 2025-12-09
- Upgrade minimal Rossum API version dependency to >= 3.7.0


## [0.3.0] - 2025-12-08
### Changed
- **Breaking**: Migrated from vanilla python-sdk MCP to FastMCP framework [#56](https://github.com/stancld/rossum-mcp/pull/56)
  - Replaced class-based `handlers/` architecture with modular `tools/` registration pattern
  - Each domain (annotations, queues, schemas, etc.) now has its own tool module with `register_*_tools()` function
  - Restructured tests into `tests/tools/` directory mirroring the new module structure
  - Simplified server.py from ~200 lines to ~70 lines
  - Reduced overall codebase by ~2,000 lines of code


## [0.2.0] - 2025-12-06
- Modified logging configuration for Redis backend [#44](https://github.com/stancld/rossum-mcp/pull/44)
- Unified `list_*` methods signature and usage [#49](https://github.com/stancld/rossum-mcp/pull/49)
- Added `get_engine` and `list_engines` methods for `rossum_api.models.engine.Engine` objects. [#49](https://github.com/stancld/rossum-mcp/pull/49)
- Added `get_hook` method for `rossum_api.models.hook.Hook` objects. [#49](https://github.com/stancld/rossum-mcp/pull/49)
- Added `get_rule` method for `rossum_api.models.rule.Rule` objects. [#49](https://github.com/stancld/rossum-mcp/pull/49)
- Added `get_engine_fields` method for `rossum_api.models.engine.EngineFields` objects. [#49](https://github.com/stancld/rossum-mcp/pull/49)
- Added `get_relation` and `list_relations` methods for `rossum_api.models.relation.Relation` objects. [#50](https://github.com/stancld/rossum-mcp/pull/50)
- Added `get_document_relation` and `list_document_relations` methods for `rossum_api.models.document_relation.DocumentRelation` objects. [#51](https://github.com/stancld/rossum-mcp/pull/51)
