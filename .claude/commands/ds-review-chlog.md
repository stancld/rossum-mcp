# Review Changelog Completeness

Review a changelog for completeness, ensuring major changes are documented while avoiding excessive detail on minor items.

## Instructions

1. First, ask the user which changelog file to review. Use AskUserQuestion if the changelog path wasn't provided as an argument.

2. Read the changelog file.

3. Analyze the git history to identify changes since the last changelog entry. If the timeframe is unclear, default to changes since the last git tag or the last 30 days.

4. Compare the changelog against the actual changes and evaluate:
   - **Major changes that should be documented:**
     - New features or capabilities
     - Breaking changes or API modifications
     - Significant bug fixes affecting user experience
     - Security updates
     - Dependency upgrades with notable impact
     - Performance improvements
     - Configuration changes

   - **Minor changes that can be omitted:**
     - Code refactoring without behavior changes
     - Internal tooling updates
     - Minor typo fixes
     - Test additions/modifications
     - Documentation formatting
     - Dependency version bumps (patch level)

5. Check version alignment: verify the changelog's latest version matches the package version (e.g., in `pyproject.toml`).

6. Provide a summary:
   - List any major changes that appear to be missing from the changelog
   - Note if the changelog includes too much minor detail
   - Suggest improvements to changelog entries if wording is unclear
   - Flag any version mismatches

## Arguments

$ARGUMENTS - Optional: Path to the changelog file to review

## Output

Provide a structured markdown summary:

- **Missing entries**: Major changes not in the changelog
- **Excessive detail**: Minor items that could be removed
- **Wording improvements**: Unclear or inconsistent entries
- **Version check**: Whether changelog version matches package version
