"""Tests for rossum_agent.streamlit_app.cli module."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from rossum_agent.streamlit_app.cli import main


class TestStreamlitCLI:
    """Test the CLI entry point for Streamlit app."""

    def test_main_calls_subprocess_with_correct_args(self):
        """Test that main calls subprocess.call with correct streamlit command."""
        with (
            patch("rossum_agent.streamlit_app.cli.subprocess.call") as mock_call,
            patch.object(sys, "argv", ["rossum-agent"]),
        ):
            mock_call.return_value = 0

            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 0
            mock_call.assert_called_once()
            call_args = mock_call.call_args[0][0]
            assert call_args[0] == sys.executable
            assert call_args[1:3] == ["-m", "streamlit"]
            assert call_args[3] == "run"
            assert "app.py" in call_args[4]

    def test_main_passes_additional_cli_args(self):
        """Test that additional CLI arguments are passed to streamlit."""
        with (
            patch("rossum_agent.streamlit_app.cli.subprocess.call") as mock_call,
            patch.object(sys, "argv", ["rossum-agent", "--server.port", "8080"]),
        ):
            mock_call.return_value = 0

            with pytest.raises(SystemExit):
                main()

            call_args = mock_call.call_args[0][0]
            assert "--server.port" in call_args
            assert "8080" in call_args

    def test_main_exits_with_subprocess_exit_code(self):
        """Test that main exits with the subprocess exit code."""
        with (
            patch("rossum_agent.streamlit_app.cli.subprocess.call") as mock_call,
            patch.object(sys, "argv", ["rossum-agent"]),
        ):
            mock_call.return_value = 1

            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1

    def test_main_uses_correct_app_path(self):
        """Test that main uses the correct app.py path."""
        with (
            patch("rossum_agent.streamlit_app.cli.subprocess.call") as mock_call,
            patch.object(sys, "argv", ["rossum-agent"]),
        ):
            mock_call.return_value = 0

            with pytest.raises(SystemExit):
                main()

            call_args = mock_call.call_args[0][0]
            app_path = Path(call_args[4])
            assert app_path.name == "app.py"
            assert "streamlit_app" in str(app_path)
