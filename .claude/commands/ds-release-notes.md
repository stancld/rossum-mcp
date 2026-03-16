# Generate Release Notes

**Goal**: Generate GitHub release notes for $ARGUMENTS based on changelog and commit history.

## Valid Packages

| Package | Changelog | Tag Pattern | Title Format |
|---------|-----------|-------------|--------------|
| rossum-mcp | `rossum-mcp/CHANGELOG.md` | `rossum-mcp-vX.Y.Z` | Rossum MCP X.Y.Z |
| rossum-agent | `rossum-agent/CHANGELOG.md` | `rossum-agent-vX.Y.Z` | Rossum Agent X.Y.Z |
| rossum-deploy | `rossum-deploy/CHANGELOG.md` | `rossum-deploy-vX.Y.Z` | Rossum Deploy X.Y.Z |
| rossum-agent-client | `rossum-agent-client/CHANGELOG.md` | `rossum-agent-client-vX.Y.Z` | Rossum Agent Client X.Y.Z |
| rossum-agent-client-ts | no changelog — use git log | `rossum-agent-client-ts-vX.Y.Z` | Rossum Agent Client TS X.Y.Z |
| rossum-agent-tui | no changelog — use git log | `rossum-agent-tui-vX.Y.Z` | Fabry X.Y.Z |

## Approach

| Step | Action |
|------|--------|
| Parse input | Extract package name and version from `$ARGUMENTS` |
| Validate | Confirm tag exists on GitHub |
| Read changelog | Get release content from `CHANGELOG.md` (or git log for TUI) |
| Check existing | Verify release notes are empty or confirm overwrite |
| Generate notes | Create markdown following style guide below |
| Update release | Push notes and title to GitHub |

## Style Guide

| Release Type | Style |
|--------------|-------|
| Major (X.0.0) | Header with emoji (`# Rossum MCP X.0.0`), intro sentence, sections with emoji headers |
| Minor (X.Y.0) | Section headers with emoji (`## New Tools`, `## Improvements`, `## Bug Fixes`) |
| Patch (X.Y.Z) | Simple section (`## Bug Fix` or `## Changes`) |
| RC (X.Y.ZrcN) | `## Changes since rcN-1` with bullet points (or full changelog for rc0) |

### Section Headers

| Section | Header |
|---------|--------|
| New features | `## New Tools` or `## New Features` |
| Improvements | `## Improvements` or `## Changes` |
| Bug fixes | `## Bug Fixes` or `## Bug Fix` |
| Breaking | `## Breaking Changes` |

### rossum-agent-tui (Fabry)

No `CHANGELOG.md` — generate release notes from git history:

| Step | Action |
|------|--------|
| Find previous tag | `git tag --list 'rossum-agent-tui-v*' --sort=-v:refname` |
| Get commits | `git log --oneline prev-tag..current-tag -- rossum-agent-tui/` |
| Check `.agents/` | Look for `release-notes-*.md` files with draft content for the version |
| Write notes | Group changes into sections, use commit messages and PR context |

Title format: **Fabry X.Y.Z** (not "Rossum Agent TUI").

### RC Releases

- First RC (rc0): Show full diff from previous stable version
- Subsequent RCs: Show incremental changes from previous RC
- Use git log to identify changes: `git log --oneline prev-tag..current-tag -- package/`

## Output Format

After generating, provide:

```
## Release Updated

- Tag: <tag>
- Title: <title>
- URL: <release-url>

### Preview
<first 500 chars of release notes>
```

## Constraints

- Use proper title format (e.g., "Rossum MCP 1.1.0", not "rossum-mcp v1.1.0")
- Match existing release notes style in the repo
- Include PR links from changelog where available
- Use `AskUserQuestion` if changelog entry is missing or ambiguous

## Examples

```
/ds-release-notes rossum-mcp 1.1.0
/ds-release-notes rossum-agent 1.0.0rc5
/ds-release-notes rossum-agent-client 1.1.0
/ds-release-notes rossum-agent-client-ts 0.2.0
/ds-release-notes rossum-agent-tui 0.2.0
```
