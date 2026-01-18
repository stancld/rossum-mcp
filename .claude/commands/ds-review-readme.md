# Review & Improve README

**Goal**: Audit all README files from open-source maintainer perspective, ensure style consistency across them, then implement approved improvements.

## Review Dimensions

| Dimension | Focus Areas |
|-----------|-------------|
| First Impression | Hook in first 3 lines, clear value proposition, visual appeal |
| Structure | Logical flow, scannable sections, appropriate depth |
| Onboarding | Installation steps, quick start, copy-paste examples |
| Trust Signals | Badges, license, contribution info, maintenance activity |
| Discoverability | Keywords, project positioning, comparison to alternatives |

## Review Checklist

| Category | Check For |
|----------|-----------|
| Opening | One-line description, what problem it solves, who it's for |
| Visuals | Logo/banner, badges (build, coverage, version), screenshots/GIFs if applicable |
| Installation | All methods (pip, npm, etc.), prerequisites clearly stated |
| Quick Start | Working example within 30 seconds of reading |
| Usage | Common use cases with code examples, expected output shown |
| API Reference | Link to docs or inline reference for key functions |
| Configuration | Environment variables, config files, options tables |
| Contributing | Link to CONTRIBUTING.md or inline guidelines |
| License | Clearly stated, link to LICENSE file |
| Support | Where to get help, issue templates, discussions |
| Badges | Appropriate badges (CI status, version, downloads, license) |
| Links | No broken links, relative paths for repo files |

## Best Practices

| Practice | Implementation |
|----------|----------------|
| Inverted pyramid | Most important info first, details later |
| Scannable | Headers, bullet points, tables over prose |
| Code blocks | Syntax highlighting, copy-paste ready |
| Minimal jargon | Accessible to newcomers, define terms |
| Show don't tell | Examples over explanations |
| Keep current | No outdated version numbers or deprecated features |

## Approach

| Step | Action |
|------|--------|
| Discover | Find all README files in the project (root, subdirectories, packages) |
| Audit | Read each README, identify gaps across all dimensions |
| Consistency | Compare style, formatting, structure across all READMEs; flag inconsistencies |
| Compare | Check against top open-source READMEs in same domain |
| Prioritize | Rank findings by impact (Critical → High → Medium → Low) |
| Present | Show findings with specific recommendations |
| Confirm | Use `AskUserQuestion` to approve implementation scope |
| Implement | Apply approved changes |
| Verify | Ensure links work and examples are accurate |

## Output Format

Present findings as:

```
## [Dimension] Issues

| Priority | Issue | Current | Recommended |
|----------|-------|---------|-------------|
| Critical | ... | Line X | ... |

**Summary**: 1-2 sentence description of what changes will be made.
```

After all dimensions reviewed, provide:

```
## Implementation Summary

[Concise list of all improvements to be applied, grouped by type]
```

## Constraints

- Find and read all README files before making any suggestions
- Preserve existing accurate content
- Match project's tone and voice
- Ensure consistent style across all READMEs (headings, formatting, structure)
- Ask before implementing changes
- Verify all code examples are correct and runnable
