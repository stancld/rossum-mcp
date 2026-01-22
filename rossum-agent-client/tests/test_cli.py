"""Tests for CLI module."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from rossum_agent_client.cli import (
    _handle_final_answer,
    _handle_step_event,
    _handle_thinking,
    _handle_tool_result,
    _handle_tool_start,
    _print_token_summary,
    _require,
    _resolve_config,
    _StreamState,
    _truncate,
    create_parser,
    get_env_or_arg,
    main,
    run_chat,
)
from rossum_agent_client.models import (
    StepEvent,
    StreamDoneEvent,
    SubAgentTokenUsageDetail,
    TokenUsageBreakdown,
    TokenUsageBySource,
)


class TestGetEnvOrArg:
    def test_returns_arg_value_when_provided(self) -> None:
        result = get_env_or_arg("from_arg", "SOME_VAR")
        assert result == "from_arg"

    def test_returns_env_var_when_arg_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SOME_VAR", "from_env")
        result = get_env_or_arg(None, "SOME_VAR")
        assert result == "from_env"

    def test_returns_none_when_both_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MISSING_VAR", raising=False)
        result = get_env_or_arg(None, "MISSING_VAR")
        assert result is None

    def test_arg_takes_precedence_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SOME_VAR", "from_env")
        result = get_env_or_arg("from_arg", "SOME_VAR")
        assert result == "from_arg"


class TestCreateParser:
    def test_parser_has_required_arguments(self) -> None:
        parser = create_parser()
        assert parser.prog == "rossum-agent-client"

    def test_execute_mode(self) -> None:
        parser = create_parser()
        args = parser.parse_args(["-x", "test prompt"])
        assert args.execute == "test prompt"

    def test_read_mode(self) -> None:
        parser = create_parser()
        args = parser.parse_args(["-r", "prompt.md"])
        assert args.read == "prompt.md"

    def test_mutually_exclusive_modes(self) -> None:
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["-x", "prompt", "-r", "file.md"])

    def test_mcp_mode_choices(self) -> None:
        parser = create_parser()
        args = parser.parse_args(["-x", "test", "--mcp-mode", "read-write"])
        assert args.mcp_mode == "read-write"

    def test_show_thinking_flag(self) -> None:
        parser = create_parser()
        args = parser.parse_args(["-x", "test", "--show-thinking"])
        assert args.show_thinking is True

    def test_connection_parameters(self) -> None:
        parser = create_parser()
        args = parser.parse_args(
            [
                "-x",
                "test",
                "--agent-api-url",
                "https://agent.example.com",
                "--rossum-api-base-url",
                "https://api.rossum.ai",
                "--rossum-api-token",
                "token123",
            ]
        )
        assert args.agent_api_url == "https://agent.example.com"
        assert args.rossum_api_base_url == "https://api.rossum.ai"
        assert args.rossum_api_token == "token123"


class TestTruncate:
    def test_short_text_unchanged(self) -> None:
        result = _truncate("short", max_len=100)
        assert result == "short"

    def test_long_text_truncated_with_ellipsis(self) -> None:
        result = _truncate("a" * 150, max_len=100)
        assert result == "a" * 100 + "..."

    def test_exact_length_no_ellipsis(self) -> None:
        result = _truncate("a" * 100, max_len=100)
        assert result == "a" * 100


class TestStreamState:
    def test_initial_state(self) -> None:
        state = _StreamState()
        assert state.last_content == ""
        assert state.last_thinking == ""
        assert state.last_tool_step is None
        assert state.created_files == []


class TestHandleThinking:
    def test_prints_incremental_thinking(self, capsys: pytest.CaptureFixture[str]) -> None:
        state = _StreamState()
        state.last_thinking = "Hello"

        event = StepEvent(type="thinking", step_number=1, content="Hello World")
        _handle_thinking(event, state)

        captured = capsys.readouterr()
        assert captured.err == " World"
        assert state.last_thinking == "Hello World"

    def test_handles_none_content(self, capsys: pytest.CaptureFixture[str]) -> None:
        state = _StreamState()
        event = StepEvent(type="thinking", step_number=1, content=None)
        _handle_thinking(event, state)

        captured = capsys.readouterr()
        assert captured.err == ""
        assert state.last_thinking == ""


class TestHandleToolStart:
    def test_prints_tool_name(self, capsys: pytest.CaptureFixture[str]) -> None:
        state = _StreamState()
        event = StepEvent(type="tool_start", step_number=1, tool_name="list_queues")
        _handle_tool_start(event, state, show_thinking=False)

        captured = capsys.readouterr()
        assert "[Tool] list_queues" in captured.err
        assert state.last_tool_step == 1

    def test_prints_args_when_show_thinking(self, capsys: pytest.CaptureFixture[str]) -> None:
        state = _StreamState()
        event = StepEvent(type="tool_start", step_number=1, tool_name="list_queues", tool_arguments={"limit": 10})
        _handle_tool_start(event, state, show_thinking=True)

        captured = capsys.readouterr()
        assert "[Tool] list_queues" in captured.err
        assert "limit" in captured.err

    def test_resets_thinking_state(self) -> None:
        state = _StreamState()
        state.last_thinking = "some thinking"
        event = StepEvent(type="tool_start", step_number=1, tool_name="test")
        _handle_tool_start(event, state, show_thinking=False)

        assert state.last_thinking == ""


class TestHandleToolResult:
    def test_prints_result_preview(self, capsys: pytest.CaptureFixture[str]) -> None:
        event = StepEvent(type="tool_result", step_number=1, result="success")
        _handle_tool_result(event)

        captured = capsys.readouterr()
        assert "→ success" in captured.err

    def test_truncates_long_result(self, capsys: pytest.CaptureFixture[str]) -> None:
        event = StepEvent(type="tool_result", step_number=1, result="x" * 200)
        _handle_tool_result(event)

        captured = capsys.readouterr()
        assert "..." in captured.err


class TestHandleFinalAnswer:
    def test_prints_incremental_content(self, capsys: pytest.CaptureFixture[str]) -> None:
        state = _StreamState()
        state.last_content = "Hello"

        event = StepEvent(type="final_answer", step_number=1, content="Hello World", is_final=True)
        _handle_final_answer(event, state)

        captured = capsys.readouterr()
        assert captured.out == " World"
        assert state.last_content == "Hello World"


class TestHandleStepEvent:
    def test_dispatches_thinking_event(self, capsys: pytest.CaptureFixture[str]) -> None:
        state = _StreamState()
        event = StepEvent(type="thinking", step_number=1, content="Analyzing...")
        _handle_step_event(event, state, show_thinking=True)

        captured = capsys.readouterr()
        assert "Analyzing..." in captured.err

    def test_skips_thinking_when_not_showing(self, capsys: pytest.CaptureFixture[str]) -> None:
        state = _StreamState()
        event = StepEvent(type="thinking", step_number=1, content="Analyzing...")
        _handle_step_event(event, state, show_thinking=False)

        captured = capsys.readouterr()
        assert captured.err == ""

    def test_dispatches_tool_start_event(self, capsys: pytest.CaptureFixture[str]) -> None:
        state = _StreamState()
        event = StepEvent(type="tool_start", step_number=1, tool_name="test_tool")
        _handle_step_event(event, state, show_thinking=False)

        captured = capsys.readouterr()
        assert "[Tool] test_tool" in captured.err

    def test_skips_duplicate_tool_start(self, capsys: pytest.CaptureFixture[str]) -> None:
        state = _StreamState()
        state.last_tool_step = 1
        event = StepEvent(type="tool_start", step_number=1, tool_name="test_tool")
        _handle_step_event(event, state, show_thinking=False)

        captured = capsys.readouterr()
        assert captured.err == ""

    def test_dispatches_tool_result_event(self, capsys: pytest.CaptureFixture[str]) -> None:
        state = _StreamState()
        event = StepEvent(type="tool_result", step_number=1, result="done")
        _handle_step_event(event, state, show_thinking=False)

        captured = capsys.readouterr()
        assert "→ done" in captured.err

    def test_dispatches_final_answer_event(self, capsys: pytest.CaptureFixture[str]) -> None:
        state = _StreamState()
        event = StepEvent(type="final_answer", step_number=1, content="Result", is_final=True)
        _handle_step_event(event, state, show_thinking=False)

        captured = capsys.readouterr()
        assert captured.out == "Result"

    def test_handles_error_event(self, capsys: pytest.CaptureFixture[str]) -> None:
        state = _StreamState()
        event = StepEvent(type="error", step_number=1, content="Something failed", is_error=True)

        with pytest.raises(SystemExit) as exc_info:
            _handle_step_event(event, state, show_thinking=False)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error: Something failed" in captured.err


class TestRequire:
    def test_returns_value_when_present(self) -> None:
        result = _require("value", "test_param")
        assert result == "value"

    def test_exits_when_none(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            _require(None, "test_param")
        assert "Missing required configuration: test_param" in str(exc_info.value)


class TestResolveConfig:
    def test_resolves_from_args(self) -> None:
        args = argparse.Namespace(
            agent_api_url="https://agent.example.com",
            rossum_api_base_url="https://api.rossum.ai",
            rossum_api_token="token123",
            mcp_mode="read-write",
        )

        agent_url, rossum_url, token, mcp_mode = _resolve_config(args)

        assert agent_url == "https://agent.example.com"
        assert rossum_url == "https://api.rossum.ai"
        assert token == "token123"
        assert mcp_mode == "read-write"

    def test_resolves_from_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ROSSUM_AGENT_API_URL", "https://env-agent.example.com")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://env-api.rossum.ai")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "env-token")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")

        args = argparse.Namespace(agent_api_url=None, rossum_api_base_url=None, rossum_api_token=None, mcp_mode=None)

        agent_url, rossum_url, token, mcp_mode = _resolve_config(args)

        assert agent_url == "https://env-agent.example.com"
        assert rossum_url == "https://env-api.rossum.ai"
        assert token == "env-token"
        assert mcp_mode == "read-only"

    def test_defaults_mcp_mode_to_read_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ROSSUM_AGENT_API_URL", "https://agent.example.com")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.rossum.ai")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "token")
        monkeypatch.delenv("ROSSUM_MCP_MODE", raising=False)

        args = argparse.Namespace(agent_api_url=None, rossum_api_base_url=None, rossum_api_token=None, mcp_mode=None)

        _, _, _, mcp_mode = _resolve_config(args)
        assert mcp_mode == "read-only"

    def test_exits_on_invalid_mcp_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ROSSUM_AGENT_API_URL", "https://agent.example.com")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.rossum.ai")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "token")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "invalid-mode")

        args = argparse.Namespace(agent_api_url=None, rossum_api_base_url=None, rossum_api_token=None, mcp_mode=None)

        with pytest.raises(SystemExit) as exc_info:
            _resolve_config(args)
        assert "Invalid MCP mode" in str(exc_info.value)

    def test_exits_on_missing_agent_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ROSSUM_AGENT_API_URL", raising=False)
        args = argparse.Namespace(
            agent_api_url=None, rossum_api_base_url="https://api.rossum.ai", rossum_api_token="token", mcp_mode=None
        )

        with pytest.raises(SystemExit) as exc_info:
            _resolve_config(args)
        assert "ROSSUM_AGENT_API_URL" in str(exc_info.value)


class TestRunChat:
    def test_run_chat_processes_events(
        self,
        httpx_mock: HTTPXMock,
        agent_api_url: str,
        rossum_api_base_url: str,
        token: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from rossum_agent_client import RossumAgentClient

        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats",
            status_code=201,
            json={"chat_id": "chat-test", "created_at": "2024-01-15T10:00:00Z"},
        )

        sse_response = (
            'event: step\ndata: {"type": "final_answer", "step_number": 1, "content": "Done", "is_final": true}\n\n'
            'event: done\ndata: {"total_steps": 1, "input_tokens": 10, "output_tokens": 5}\n\n'
        )
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-test/messages",
            method="POST",
            content=sse_response.encode(),
        )

        with RossumAgentClient(agent_api_url, rossum_api_base_url, token) as client:
            run_chat(client, "Test prompt", "read-only", show_thinking=False)

        captured = capsys.readouterr()
        assert "Chat: chat-test" in captured.err
        assert "Done" in captured.out
        assert "10 in, 5 out" in captured.err

    def test_run_chat_downloads_created_files(
        self,
        httpx_mock: HTTPXMock,
        agent_api_url: str,
        rossum_api_base_url: str,
        token: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from rossum_agent_client import RossumAgentClient

        monkeypatch.chdir(tmp_path)

        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats",
            status_code=201,
            json={"chat_id": "chat-files", "created_at": "2024-01-15T10:00:00Z"},
        )

        sse_response = (
            "event: file_created\n"
            'data: {"type": "file_created", "filename": "output.csv", "url": "/files/output.csv"}\n\n'
            'event: done\ndata: {"total_steps": 1, "input_tokens": 10, "output_tokens": 5}\n\n'
        )
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-files/messages",
            method="POST",
            content=sse_response.encode(),
        )

        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-files/files/output.csv",
            content=b"col1,col2\nval1,val2",
        )

        with RossumAgentClient(agent_api_url, rossum_api_base_url, token) as client:
            run_chat(client, "Create file", "read-only")

        assert (tmp_path / "output.csv").exists()
        assert (tmp_path / "output.csv").read_text() == "col1,col2\nval1,val2"

        captured = capsys.readouterr()
        assert "Saved: output.csv" in captured.err

    def test_run_chat_prevents_path_traversal(
        self,
        httpx_mock: HTTPXMock,
        agent_api_url: str,
        rossum_api_base_url: str,
        token: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from rossum_agent_client import RossumAgentClient

        monkeypatch.chdir(tmp_path)

        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats",
            status_code=201,
            json={"chat_id": "chat-traverse", "created_at": "2024-01-15T10:00:00Z"},
        )

        sse_response = (
            "event: file_created\n"
            'data: {"type": "file_created", "filename": "../../../etc/passwd", "url": "/files/bad"}\n\n'
            'event: done\ndata: {"total_steps": 1, "input_tokens": 10, "output_tokens": 5}\n\n'
        )
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-traverse/messages",
            method="POST",
            content=sse_response.encode(),
        )

        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-traverse/files/../../../etc/passwd",
            content=b"safe content",
        )

        with RossumAgentClient(agent_api_url, rossum_api_base_url, token) as client:
            run_chat(client, "Create file", "read-only")

        # File should be saved with just the filename, not the traversal path
        assert (tmp_path / "passwd").exists()
        assert not (tmp_path / ".." / ".." / ".." / "etc" / "passwd").exists()


class TestMain:
    def test_main_execute_mode(
        self, httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("ROSSUM_AGENT_API_URL", "https://agent.example.com")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.rossum.ai")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "token123")

        httpx_mock.add_response(
            url="https://agent.example.com/api/v1/chats",
            status_code=201,
            json={"chat_id": "chat-main", "created_at": "2024-01-15T10:00:00Z"},
        )

        sse_response = (
            'event: step\ndata: {"type": "final_answer", "step_number": 1, "content": "Hello", "is_final": true}\n\n'
            'event: done\ndata: {"total_steps": 1, "input_tokens": 10, "output_tokens": 5}\n\n'
        )
        httpx_mock.add_response(
            url="https://agent.example.com/api/v1/chats/chat-main/messages",
            method="POST",
            content=sse_response.encode(),
        )

        main(["-x", "Test prompt"])

        captured = capsys.readouterr()
        assert "Hello" in captured.out

    def test_main_read_mode(
        self, httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("ROSSUM_AGENT_API_URL", "https://agent.example.com")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.rossum.ai")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "token123")

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Prompt from file")

        httpx_mock.add_response(
            url="https://agent.example.com/api/v1/chats",
            status_code=201,
            json={"chat_id": "chat-read", "created_at": "2024-01-15T10:00:00Z"},
        )

        sse_response = 'event: done\ndata: {"total_steps": 0, "input_tokens": 5, "output_tokens": 2}\n\n'
        httpx_mock.add_response(
            url="https://agent.example.com/api/v1/chats/chat-read/messages",
            method="POST",
            content=sse_response.encode(),
        )

        main(["-r", str(prompt_file)])

    def test_main_file_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ROSSUM_AGENT_API_URL", "https://agent.example.com")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.rossum.ai")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "token123")

        with pytest.raises(SystemExit) as exc_info:
            main(["-r", "/nonexistent/file.md"])

        assert "File not found" in str(exc_info.value)

    def test_main_api_error(self, httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ROSSUM_AGENT_API_URL", "https://agent.example.com")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.rossum.ai")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "token123")

        httpx_mock.add_response(
            url="https://agent.example.com/api/v1/chats",
            status_code=401,
            text="Unauthorized",
        )

        with pytest.raises(SystemExit) as exc_info:
            main(["-x", "Test"])

        assert "Error:" in str(exc_info.value)

    def test_main_api_error_with_body(self, httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ROSSUM_AGENT_API_URL", "https://agent.example.com")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.rossum.ai")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "token123")

        httpx_mock.add_response(
            url="https://agent.example.com/api/v1/chats",
            status_code=500,
            text="Detailed error message",
        )

        with pytest.raises(SystemExit) as exc_info:
            main(["-x", "Test"])

        error_msg = str(exc_info.value)
        assert "Error:" in error_msg

    def test_main_keyboard_interrupt(self, httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ROSSUM_AGENT_API_URL", "https://agent.example.com")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.rossum.ai")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "token123")

        def raise_keyboard_interrupt(*args: object, **kwargs: object) -> None:
            raise KeyboardInterrupt

        with patch("rossum_agent_client.cli.RossumAgentClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = raise_keyboard_interrupt

            with pytest.raises(SystemExit) as exc_info:
                main(["-x", "Test"])

            assert exc_info.value.code == 130

    def test_main_with_show_thinking(
        self, httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("ROSSUM_AGENT_API_URL", "https://agent.example.com")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.rossum.ai")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "token123")

        httpx_mock.add_response(
            url="https://agent.example.com/api/v1/chats",
            status_code=201,
            json={"chat_id": "chat-think", "created_at": "2024-01-15T10:00:00Z"},
        )

        sse_response = (
            'event: step\ndata: {"type": "thinking", "step_number": 1, "content": "Let me analyze..."}\n\n'
            'event: step\ndata: {"type": "final_answer", "step_number": 2, "content": "Done", "is_final": true}\n\n'
            'event: done\ndata: {"total_steps": 2, "input_tokens": 10, "output_tokens": 5}\n\n'
        )
        httpx_mock.add_response(
            url="https://agent.example.com/api/v1/chats/chat-think/messages",
            method="POST",
            content=sse_response.encode(),
        )

        main(["-x", "Test", "--show-thinking"])

        captured = capsys.readouterr()
        assert "Let me analyze..." in captured.err


class TestPrintTokenSummary:
    def test_prints_simple_summary_when_no_breakdown(self, capsys: pytest.CaptureFixture[str]) -> None:
        event = StreamDoneEvent(total_steps=5, input_tokens=100, output_tokens=50)
        _print_token_summary(event)

        captured = capsys.readouterr()
        assert "(100 in, 50 out)" in captured.err

    def test_prints_detailed_breakdown_when_available(self, capsys: pytest.CaptureFixture[str]) -> None:
        breakdown = TokenUsageBreakdown(
            total=TokenUsageBySource(input_tokens=3000, output_tokens=1500, total_tokens=4500),
            main_agent=TokenUsageBySource(input_tokens=1000, output_tokens=500, total_tokens=1500),
            sub_agents=SubAgentTokenUsageDetail(
                input_tokens=2000,
                output_tokens=1000,
                total_tokens=3000,
                by_tool={"debug_hook": TokenUsageBySource(input_tokens=2000, output_tokens=1000, total_tokens=3000)},
            ),
        )
        event = StreamDoneEvent(total_steps=5, input_tokens=3000, output_tokens=1500, token_usage_breakdown=breakdown)
        _print_token_summary(event)

        captured = capsys.readouterr()
        assert "TOKEN USAGE SUMMARY" in captured.err
        assert "Main Agent" in captured.err
        assert "Sub-agents (total)" in captured.err
        assert "debug_hook" in captured.err
        assert "TOTAL" in captured.err

    def test_prints_breakdown_without_sub_agents(self, capsys: pytest.CaptureFixture[str]) -> None:
        breakdown = TokenUsageBreakdown(
            total=TokenUsageBySource(input_tokens=1000, output_tokens=500, total_tokens=1500),
            main_agent=TokenUsageBySource(input_tokens=1000, output_tokens=500, total_tokens=1500),
            sub_agents=SubAgentTokenUsageDetail(input_tokens=0, output_tokens=0, total_tokens=0, by_tool={}),
        )
        event = StreamDoneEvent(total_steps=3, input_tokens=1000, output_tokens=500, token_usage_breakdown=breakdown)
        _print_token_summary(event)

        captured = capsys.readouterr()
        assert "TOKEN USAGE SUMMARY" in captured.err
        assert "Main Agent" in captured.err
        assert "1,000" in captured.err
