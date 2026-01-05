"""Tests for rossum_agent.api.cli module."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from rossum_agent.api.cli import main


class TestApiCli:
    """Test API CLI entry point."""

    @patch("rossum_agent.api.cli.httpx.Client")
    @patch.dict("os.environ", {"ROSSUM_API_TOKEN": "test-token", "ROSSUM_API_BASE_URL": "https://api.rossum.ai"})
    def test_main_with_prompt_argument(self, mock_client_class: MagicMock):
        """Test main() with prompt provided as argument."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=None)

        mock_create_response = MagicMock()
        mock_create_response.json.return_value = {"id": "chat-123"}
        mock_client.post.return_value = mock_create_response

        mock_stream_response = MagicMock()
        mock_stream_response.iter_lines.return_value = ["data: event1", "data: event2"]
        mock_client.stream.return_value.__enter__ = MagicMock(return_value=mock_stream_response)
        mock_client.stream.return_value.__exit__ = MagicMock(return_value=None)

        with patch.object(sys, "argv", ["cli.py", "Hello agent"]):
            main()

        mock_client.post.assert_called_once()
        mock_client.stream.assert_called_once()

    @patch("rossum_agent.api.cli.httpx.Client")
    @patch.dict("os.environ", {"ROSSUM_API_TOKEN": "test-token", "ROSSUM_API_BASE_URL": "https://api.rossum.ai"})
    def test_main_with_custom_api_url(self, mock_client_class: MagicMock):
        """Test main() with custom API URL."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=None)

        mock_create_response = MagicMock()
        mock_create_response.json.return_value = {"chat_id": "chat-456"}
        mock_client.post.return_value = mock_create_response

        mock_stream_response = MagicMock()
        mock_stream_response.iter_lines.return_value = []
        mock_client.stream.return_value.__enter__ = MagicMock(return_value=mock_stream_response)
        mock_client.stream.return_value.__exit__ = MagicMock(return_value=None)

        with patch.object(sys, "argv", ["cli.py", "--api-url", "http://custom:9000", "Test prompt"]):
            main()

        call_args = mock_client.post.call_args
        assert "http://custom:9000" in call_args[0][0]

    @patch.dict("os.environ", {"ROSSUM_API_TOKEN": "", "ROSSUM_API_BASE_URL": ""}, clear=True)
    def test_main_exits_without_token(self):
        """Test main() exits with error when ROSSUM_API_TOKEN is missing."""
        with patch.object(sys, "argv", ["cli.py", "Hello"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    @patch.dict("os.environ", {"ROSSUM_API_TOKEN": "token", "ROSSUM_API_BASE_URL": ""}, clear=True)
    def test_main_exits_without_base_url(self):
        """Test main() exits with error when ROSSUM_API_BASE_URL is missing."""
        with patch.object(sys, "argv", ["cli.py", "Hello"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    @patch("rossum_agent.api.cli.httpx.Client")
    @patch("builtins.input", return_value="Interactive prompt")
    @patch.dict("os.environ", {"ROSSUM_API_TOKEN": "test-token", "ROSSUM_API_BASE_URL": "https://api.rossum.ai"})
    def test_main_prompts_for_input_when_no_prompt_given(self, mock_input: MagicMock, mock_client_class: MagicMock):
        """Test main() prompts for input when no prompt argument provided."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=None)

        mock_create_response = MagicMock()
        mock_create_response.json.return_value = {"id": "chat-789"}
        mock_client.post.return_value = mock_create_response

        mock_stream_response = MagicMock()
        mock_stream_response.iter_lines.return_value = ["data: test"]
        mock_client.stream.return_value.__enter__ = MagicMock(return_value=mock_stream_response)
        mock_client.stream.return_value.__exit__ = MagicMock(return_value=None)

        with patch.object(sys, "argv", ["cli.py"]):
            main()

        mock_input.assert_called_once_with("Prompt: ")

    @patch("rossum_agent.api.cli.httpx.Client")
    @patch.dict("os.environ", {"ROSSUM_API_TOKEN": "test-token", "ROSSUM_API_BASE_URL": "https://api.rossum.ai"})
    def test_main_sends_correct_headers(self, mock_client_class: MagicMock):
        """Test main() sends correct headers to API."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=None)

        mock_create_response = MagicMock()
        mock_create_response.json.return_value = {"id": "chat-123"}
        mock_client.post.return_value = mock_create_response

        mock_stream_response = MagicMock()
        mock_stream_response.iter_lines.return_value = []
        mock_client.stream.return_value.__enter__ = MagicMock(return_value=mock_stream_response)
        mock_client.stream.return_value.__exit__ = MagicMock(return_value=None)

        with patch.object(sys, "argv", ["cli.py", "Test"]):
            main()

        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["headers"]["X-Rossum-Token"] == "test-token"
        assert call_kwargs["headers"]["X-Rossum-Api-Url"] == "https://api.rossum.ai"

    @patch("rossum_agent.api.cli.httpx.Client")
    @patch.dict("os.environ", {"ROSSUM_API_TOKEN": "test-token", "ROSSUM_API_BASE_URL": "https://api.rossum.ai"})
    def test_main_prints_sse_events(self, mock_client_class: MagicMock, capsys):
        """Test main() prints SSE events."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=None)

        mock_create_response = MagicMock()
        mock_create_response.json.return_value = {"id": "chat-123"}
        mock_client.post.return_value = mock_create_response

        mock_stream_response = MagicMock()
        mock_stream_response.iter_lines.return_value = ["data: first_event", "data: second_event", ""]
        mock_client.stream.return_value.__enter__ = MagicMock(return_value=mock_stream_response)
        mock_client.stream.return_value.__exit__ = MagicMock(return_value=None)

        with patch.object(sys, "argv", ["cli.py", "Test"]):
            main()

        captured = capsys.readouterr()
        assert "first_event" in captured.out
        assert "second_event" in captured.out

    @patch("rossum_agent.api.cli.httpx.Client")
    @patch.dict("os.environ", {"ROSSUM_API_TOKEN": "test-token", "ROSSUM_API_BASE_URL": "https://api.rossum.ai"})
    def test_main_handles_chat_id_fallback(self, mock_client_class: MagicMock, capsys):
        """Test main() handles both 'id' and 'chat_id' response formats."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=None)

        mock_create_response = MagicMock()
        mock_create_response.json.return_value = {"chat_id": "fallback-chat-id"}
        mock_client.post.return_value = mock_create_response

        mock_stream_response = MagicMock()
        mock_stream_response.iter_lines.return_value = []
        mock_client.stream.return_value.__enter__ = MagicMock(return_value=mock_stream_response)
        mock_client.stream.return_value.__exit__ = MagicMock(return_value=None)

        with patch.object(sys, "argv", ["cli.py", "Test"]):
            main()

        captured = capsys.readouterr()
        assert "fallback-chat-id" in captured.out
