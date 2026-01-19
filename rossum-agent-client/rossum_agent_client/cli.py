"""Command-line interface for Rossum Agent Client."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Literal

from rossum_agent_client import RossumAgentClient, __version__
from rossum_agent_client.exceptions import RossumAgentError
from rossum_agent_client.models import FileCreatedEvent, StepEvent, StreamDoneEvent


def get_env_or_arg(arg_value: str | None, env_var: str) -> str | None:
    """Get value from argument or environment variable."""
    return arg_value or os.environ.get(env_var)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="rossum-agent-client",
        description="CLI for Rossum Agent API - AI-powered document processing assistant",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    # Connection parameters
    parser.add_argument(
        "--agent-api-url",
        help="Agent API URL (env: ROSSUM_AGENT_API_URL)",
    )
    parser.add_argument(
        "--rossum-api-base-url",
        help="Rossum API base URL (env: ROSSUM_API_BASE_URL)",
    )
    parser.add_argument(
        "--rossum-api-token",
        help="Rossum API token (env: ROSSUM_API_TOKEN)",
    )

    # Execution modes (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "-x",
        "--execute",
        metavar="PROMPT",
        help="Execute a prompt directly",
    )
    mode_group.add_argument(
        "-r",
        "--read",
        metavar="FILE",
        help="Read prompt from a markdown file and execute",
    )

    # Optional parameters
    parser.add_argument(
        "--mcp-mode",
        choices=["read-only", "read-write"],
        help="MCP mode for the chat session (env: ROSSUM_MCP_MODE, default: read-only)",
    )
    parser.add_argument(
        "--show-thinking",
        action="store_true",
        help="Display thinking steps and tool arguments",
    )

    return parser


class _StreamState:
    """Mutable state for stream processing."""

    def __init__(self) -> None:
        self.last_content = ""
        self.last_thinking = ""
        self.last_tool_step: int | None = None
        self.created_files: list[str] = []


def _truncate(text: str, max_len: int = 100) -> str:
    """Truncate text with ellipsis if needed."""
    return text[:max_len] + ("..." if len(text) > max_len else "")


def _handle_thinking(event: StepEvent, state: _StreamState) -> None:
    """Handle thinking event - print incremental thinking content."""
    new_thinking = (event.content or "")[len(state.last_thinking) :]
    print(new_thinking, end="", flush=True, file=sys.stderr)
    state.last_thinking = event.content or ""


def _handle_tool_start(event: StepEvent, state: _StreamState, show_thinking: bool) -> None:
    """Handle tool_start event - print tool invocation."""
    state.last_thinking = ""  # Reset for next thinking block
    state.last_tool_step = event.step_number
    if show_thinking and event.tool_arguments:
        args_preview = _truncate(str(event.tool_arguments))
        print(f"\n[Tool] {event.tool_name} {args_preview}", file=sys.stderr)
    else:
        print(f"\n[Tool] {event.tool_name}", file=sys.stderr)


def _handle_tool_result(event: StepEvent) -> None:
    """Handle tool_result event - print result preview."""
    result_preview = _truncate(event.result or "")
    print(f"       → {result_preview}", file=sys.stderr)


def _handle_final_answer(event: StepEvent, state: _StreamState) -> None:
    """Handle final_answer event - print incremental answer content."""
    new_content = (event.content or "")[len(state.last_content) :]
    print(new_content, end="", flush=True)
    state.last_content = event.content or ""


def _handle_step_event(event: StepEvent, state: _StreamState, show_thinking: bool) -> None:
    """Dispatch step event to appropriate handler."""
    if event.type == "thinking" and event.content and show_thinking:
        _handle_thinking(event, state)
    elif event.type == "tool_start" and event.tool_name and event.step_number != state.last_tool_step:
        _handle_tool_start(event, state, show_thinking)
    elif event.type == "tool_result":
        _handle_tool_result(event)
    elif event.type == "final_answer" and event.content:
        _handle_final_answer(event, state)
    elif event.type == "error":
        print(f"\nError: {event.content}", file=sys.stderr)
        sys.exit(1)


def run_chat(
    client: RossumAgentClient,
    prompt: str,
    mcp_mode: Literal["read-only", "read-write"],
    show_thinking: bool = False,
) -> None:
    """Run a chat session with the given prompt."""
    chat = client.create_chat(mcp_mode=mcp_mode)
    print(f"Chat: {chat.chat_id}", file=sys.stderr)
    print(file=sys.stderr)

    state = _StreamState()

    for event in client.send_message_stream(chat.chat_id, prompt):
        if isinstance(event, StepEvent):
            _handle_step_event(event, state, show_thinking)
        elif isinstance(event, FileCreatedEvent):
            state.created_files.append(event.filename)
        elif isinstance(event, StreamDoneEvent):
            print()  # Final newline
            print(f"\n({event.input_tokens} in, {event.output_tokens} out)", file=sys.stderr)

    # Download and save created files
    for filename in state.created_files:
        content = client.download_file(chat.chat_id, filename)
        safe_filename = Path(filename).name  # Prevent path traversal
        Path(safe_filename).write_bytes(content)
        print(f"Saved: {safe_filename}", file=sys.stderr)


type McpMode = Literal["read-only", "read-write"]


def _require(value: str | None, name: str) -> str:
    """Return value if present, exit with error otherwise."""
    if value is not None:
        return value
    sys.exit(f"Error: Missing required configuration: {name}")


def _resolve_config(
    args: argparse.Namespace,
) -> tuple[str, str, str, McpMode]:
    """Resolve and validate CLI configuration. Exits on validation failure."""
    agent_api_url = _require(
        get_env_or_arg(args.agent_api_url, "ROSSUM_AGENT_API_URL"),
        "--agent-api-url or ROSSUM_AGENT_API_URL",
    )
    rossum_api_base_url = _require(
        get_env_or_arg(args.rossum_api_base_url, "ROSSUM_API_BASE_URL"),
        "--rossum-api-base-url or ROSSUM_API_BASE_URL",
    )
    token = _require(
        get_env_or_arg(args.rossum_api_token, "ROSSUM_API_TOKEN"),
        "--rossum-api-token or ROSSUM_API_TOKEN",
    )

    mcp_mode_raw = args.mcp_mode or os.environ.get("ROSSUM_MCP_MODE", "read-only")
    if mcp_mode_raw not in ("read-only", "read-write"):
        sys.exit(f"Error: Invalid MCP mode: {mcp_mode_raw}. Must be 'read-only' or 'read-write'.")

    mcp_mode: McpMode = "read-only" if mcp_mode_raw == "read-only" else "read-write"
    return agent_api_url, rossum_api_base_url, token, mcp_mode


def main(argv: list[str] | None = None) -> None:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args(argv)

    agent_api_url, rossum_api_base_url, token, mcp_mode = _resolve_config(args)

    # Determine the prompt
    if args.execute:
        prompt = args.execute
    else:
        file_path = Path(args.read)
        if not file_path.exists():
            sys.exit(f"Error: File not found: {file_path}")
        prompt = file_path.read_text()

    # Run the chat
    try:
        with RossumAgentClient(
            agent_api_url=agent_api_url,
            rossum_api_base_url=rossum_api_base_url,
            token=token,
        ) as client:
            run_chat(client, prompt, mcp_mode, show_thinking=args.show_thinking)
    except RossumAgentError as e:
        if e.response_body:
            sys.exit(f"Error: {e}\n{e.response_body}")
        sys.exit(f"Error: {e}")
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
