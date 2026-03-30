# Changelog - Rossum Deploy

All notable changes to this project will be documented in this file.

---

## [Unreleased] - YYYY-MM-DD

### Changed
- Bump `rossum-api` dependency from `>=3.11.2` to `>=3.12.0` [#276](https://github.com/stancld/rossum-agents/pull/276), from `>=3.12.1` to `>=3.13.1` — adds support for rule → queues many-to-many relation [#329](https://github.com/stancld/rossum-agents/pull/329)

## [0.1.0] - 2025-12-31

### Added
- Initial release of `rossum-deploy` package
- `Workspace` class for managing local workspace state
- Pull Rossum objects: workspaces, queues, schemas, hooks, engines, connectors, email templates, rules
- `diff` method for comparing local state with remote instance
- `push` method for pushing local changes to remote with dry-run support
- `copy_workspace` and `copy_org` methods for copying configurations between organizations
- `deploy` method for deploying local workspace to target organization with ID remapping
- `compare_workspaces` method for comparing source and target workspace states
