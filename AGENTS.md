# Development Guidelines

## Commands
- **Python setup**: `pip install -e .`
- **Run server**: `python server.py`
- **Lint & type check**: `pre-commit run --all-files`
- **Individual tools**: `ruff check --fix`, `ruff format`, `mypy --config-file=examples/python/mypy.ini`

## Architecture
- Single-file MCP server (`server.py`) for Rossum API integration
- Main class: `RossumMCPServer` with async tool handlers
- Three tools: `upload_document`, `get_annotation`, `list_annotations`
- Sync API client wrapped in async executors for MCP compatibility
- Examples in `examples/` directory

## Code Style
- **Python version**: 3.12+ syntax required
- **Typing**: Use modern union syntax (`str | None`, not `Optional[str]`) and built-ins (`list[str]`, `dict[str, int]`). Avoid using `Any` type annotation as much as possible - use specific types instead
- **Imports**: Use `from pathlib import Path`, standard library first. Do NOT add try/except blocks for missing imports - assume all dependencies are installed
- **Async**: Wrap sync operations with `ThreadPoolExecutor` for MCP
- **Logging**: File-based logging to `/tmp/` since stdout is MCP protocol
- **Error handling**: Return JSON error objects, include tracebacks for debugging
- **Comments**: Brief, explain why not what
- **Quality**: Use pre-commit hooks (ruff, mypy, codespell) before committing
- **Development workflow**: After making code changes, iteratively run `pre-commit run --all-files` and fix all mypy type errors until the checks pass cleanly

## Environment
- Required: `ROSSUM_API_TOKEN`, `ROSSUM_API_BASE_URL`
- MCP client configuration in Claude Desktop or smolagents
