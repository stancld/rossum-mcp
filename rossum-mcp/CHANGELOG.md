# Changelog - Rossum MCP

All notable changes to this project will be documented in this file.

---

## [Unreleased] - YYYY-MM-DD
- Added `list_hook_templates` tool for listing available hook templates from Rossum Store
- Added `create_hook_from_template` tool for creating hooks from pre-built templates


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
