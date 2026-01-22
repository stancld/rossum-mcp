# Review Changelog Completeness

**Goal**: Review a changelog for completeness, ensuring major changes are documented while avoiding excessive detail on minor items.

## Scope

| Context | What to Review |
|---------|----------------|
| No argument | Ask user which changelog to review |
| Path provided | Review specified changelog file |

## Valid Packages

| Package | Changelog Path |
|---------|---------------|
| rossum-mcp | `rossum-mcp/CHANGELOG.md` |
| rossum-agent | `rossum-agent/CHANGELOG.md` |
| rossum-deploy | `rossum-deploy/CHANGELOG.md` |
| rossum-agent-client | `rossum-agent-client/CHANGELOG.md` |

## Change Categories

| Should Document | Can Omit |
|-----------------|----------|
| New features or capabilities | Code refactoring without behavior changes |
| Breaking changes or API modifications | Internal tooling updates |
| Significant bug fixes affecting users | Minor typo fixes |
| Security updates | Test additions/modifications |
| Dependency upgrades with notable impact | Documentation formatting |
| Performance improvements | Dependency version bumps (patch level) |
| Configuration changes | |

## Approach

| Step | Action |
|------|--------|
| Identify | Ask user for changelog path if not provided |
| Read | Load changelog and pyproject.toml |
| Analyze | Check git history since last changelog entry (or last tag, or 30 days) |
| Compare | Match commits against documented changes |
| Version check | Verify changelog version matches pyproject.toml |
| Report | List gaps and suggestions |

## Output

Provide a structured summary:

```
## Changelog Review

### Missing entries
- [ ] Major change X not documented

### Excessive detail
- [ ] Minor item Y could be removed

### Wording improvements
- [ ] Entry Z is unclear

### Version check
- [x] Changelog version matches pyproject.toml
```

## Constraints

- No automatic file modifications
- Use `AskUserQuestion` if changelog path not provided
- Focus on user-facing changes, not internal refactors
