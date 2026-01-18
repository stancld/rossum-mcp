# Improve Test Coverage

**Goal**: Add tests for code changed in the current branch to achieve 95%+ coverage.

## Scope

| Context | What to Cover |
|---------|---------------|
| Staged changes | `git diff --cached` |
| Branch changes | `git diff master...HEAD` if no staged changes |

## Coverage Priorities

| Priority | Target |
|----------|--------|
| High | New functions and methods |
| High | Modified logic branches |
| Medium | Error handling paths |
| Low | Simple property accessors |

## Approach

| Step | Action |
|------|--------|
| Identify | List new/modified functions from diff |
| Analyze | Check existing test coverage for each |
| Plan | Propose tests for uncovered code using `AskUserQuestion` |
| Write | Add tests following existing test patterns |
| Verify | Run `pytest` to confirm tests pass |

## Test Standards

| Rule | Implementation |
|------|----------------|
| Location | Mirror source structure in `tests/` |
| Naming | `test_<function_name>` or `Test<ClassName>` |
| Fixtures | Reuse from `conftest.py` where available |
| Assertions | One logical assertion per test |
| Mocking | Mock external dependencies, not internal logic |

## Constraints

- Ask before writing tests (use `AskUserQuestion` to confirm plan)
- Follow existing test patterns in the codebase
- No tests for trivial code (simple getters, pass-through calls)
- Run `pytest` after adding tests to verify they pass
