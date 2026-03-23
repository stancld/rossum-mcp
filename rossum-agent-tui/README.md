# Rossum Agent TUI

<div align="center">

**Terminal UI for interacting with the Rossum Agent API. Development test-bed for the [Rossum Agent](../rossum-agent/).**

[![Node.js](https://img.shields.io/badge/Node.js-22+-339933?logo=node.js&logoColor=white)](https://nodejs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7+-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-agents/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

> [!NOTE]
> This is not an official Rossum project. It is a community-developed integration built on top of the Rossum API, not a product (yet).

> [!NOTE]
> This is a development tool, not a production application. Tests are not required for this package.

## Prerequisites

- **Node.js 22+**
- **[rossum-agent](../rossum-agent/)** — the API backend the TUI connects to:
  ```bash
  pip install "rossum-agent[api]"
  # or
  uv pip install "rossum-agent[api]"
  ```
  This provides the `rossum-agent-api` command used by `--start-api`.

## Installation

Download the latest release from [GitHub Releases](https://github.com/stancld/rossum-agents/releases) and install it with npm:

```bash
npm install -g https://github.com/stancld/rossum-agents/releases/download/rossum-agent-tui-vX.Y.Z/rossum-agent-tui-X.Y.Z.tgz
```

Replace `X.Y.Z` with the version you want to install. After installation, the `fabry` command is available globally.

## Development Setup

```bash
npm install
npm run build
```

## Configuration

| Option              | Flag           | Environment Variable   | Required                  |
| ------------------- | -------------- | ---------------------- | ------------------------- |
| Agent API URL       | `--api-url`    | `ROSSUM_AGENT_API_URL` | Yes                       |
| Rossum API token    | `--token`      | `ROSSUM_API_TOKEN`     | Yes                       |
| Rossum API base URL | `--rossum-url` | `ROSSUM_API_BASE_URL`  | Yes                       |
| MCP mode            | `--mcp-mode`   | `ROSSUM_MCP_MODE`      | No (default: `read-only`) |
| Persona             | `--persona`    | `ROSSUM_AGENT_PERSONA` | No (default: `default`)   |

## Usage

```bash
# Using environment variables
export ROSSUM_AGENT_API_URL=http://localhost:8000
export ROSSUM_API_TOKEN=your-token
export ROSSUM_API_BASE_URL=https://api.elis.rossum.ai
fabry

# Using flags
fabry --api-url http://localhost:8000 --token your-token --rossum-url https://api.elis.rossum.ai

# Read-write mode
fabry --mcp-mode read-write

# Cautious persona
fabry --persona cautious
```

## Keyboard Controls

| Mode   | Key                 | Action                                 |
| ------ | ------------------- | -------------------------------------- |
| Input  | `Esc`               | Switch to browse mode                  |
| Browse | `i` / `Tab`         | Switch to input mode                   |
| Browse | `j` / `↓`           | Move selection down                    |
| Browse | `k` / `↑`           | Move selection up                      |
| Browse | `Ctrl+D` / `Ctrl+U` | Scroll chat viewport down/up           |
| Browse | `Enter` / `Space`   | Expand/collapse selected item          |
| Browse | `G`                 | Jump to bottom (re-enable auto-scroll) |
| Input  | `Meta+1`            | Quick reply: Approve                   |
| Input  | `Meta+2`            | Quick reply: Reject                    |
| Input  | `Meta+3`            | Quick reply: Let's chat about it.      |
| Any    | `Ctrl+X`            | Stop current response stream           |
| Any    | `Ctrl+N`            | Start a new chat                       |

Expandable items: thinking steps, tool calls, intermediate content, and final answers.

## Task Tracking

When the agent uses task tracking for multi-step operations, a task list appears inline showing progress:

| Badge        | Status      |
| ------------ | ----------- |
| `✓` (green)  | Completed   |
| Spinner      | In progress |
| `○` (dimmed) | Pending     |

Tasks update in real-time as the agent works through each step.

## Session Persistence

Chat state is persisted to `~/.rossum-agent-tui/history.json`. On restart, the TUI restores the previous session (chat history, completed steps, tasks).

### Clear state / start fresh

```bash
rm ~/.rossum-agent-tui/history.json
```

Or remove the entire directory:

```bash
rm -rf ~/.rossum-agent-tui
```

## Development

```bash
npm run dev    # watch mode (recompiles on changes)
npm run build  # one-off build
npm start      # run from dist/
```

## License

MIT License - see [LICENSE](../LICENSE) for details.

## Resources

- [Rossum Agent README](../rossum-agent/README.md)
- [Full Documentation](https://stancld.github.io/rossum-agents/)
- [Main Repository](https://github.com/stancld/rossum-agents)
