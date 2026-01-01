"""Tests for rossum_agent.streamlit_app.cli module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rossum_agent.streamlit_app.cli import main


class TestCli:
    """Test CLI entry point."""

    @patch("rossum_agent.streamlit_app.cli.subprocess.call")
    @patch("rossum_agent.streamlit_app.cli.shutil.which")
    def test_main_calls_streamlit_run(self, mock_which: MagicMock, mock_call: MagicMock):
        """Test that main() calls streamlit run with correct app path."""
        mock_which.return_value = "/usr/bin/streamlit"
        mock_call.return_value = 0

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        mock_call.assert_called_once()

        call_args = mock_call.call_args[0][0]
        assert call_args[0] == "/usr/bin/streamlit"
        assert call_args[1] == "run"
        assert "app.py" in call_args[2]

    @patch("rossum_agent.streamlit_app.cli.subprocess.call")
    @patch("rossum_agent.streamlit_app.cli.shutil.which")
    def test_main_passes_extra_args(self, mock_which: MagicMock, mock_call: MagicMock):
        """Test that main() passes extra CLI arguments to streamlit."""
        mock_which.return_value = "/usr/bin/streamlit"
        mock_call.return_value = 0

        with patch("rossum_agent.streamlit_app.cli.sys.argv", ["cli.py", "--server.port", "8501"]):
            with pytest.raises(SystemExit):
                main()

        call_args = mock_call.call_args[0][0]
        assert "--server.port" in call_args
        assert "8501" in call_args

    @patch("rossum_agent.streamlit_app.cli.subprocess.call")
    @patch("rossum_agent.streamlit_app.cli.shutil.which")
    def test_main_returns_subprocess_exit_code(self, mock_which: MagicMock, mock_call: MagicMock):
        """Test that main() returns the subprocess exit code."""
        mock_which.return_value = "/usr/bin/streamlit"
        mock_call.return_value = 1

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    @patch("rossum_agent.streamlit_app.cli.subprocess.call")
    @patch("rossum_agent.streamlit_app.cli.shutil.which")
    def test_main_uses_correct_app_path(self, mock_which: MagicMock, mock_call: MagicMock):
        """Test that main() uses the app.py path relative to cli.py."""
        mock_which.return_value = "/usr/bin/streamlit"
        mock_call.return_value = 0

        with pytest.raises(SystemExit):
            main()

        call_args = mock_call.call_args[0][0]
        app_path = Path(call_args[2])
        assert app_path.name == "app.py"
        assert "streamlit_app" in str(app_path)

    @patch("rossum_agent.streamlit_app.cli.subprocess.call")
    @patch("rossum_agent.streamlit_app.cli.shutil.which")
    def test_main_with_no_extra_args(self, mock_which: MagicMock, mock_call: MagicMock):
        """Test that main() works with no extra arguments."""
        mock_which.return_value = "/usr/bin/streamlit"
        mock_call.return_value = 0

        with patch("rossum_agent.streamlit_app.cli.sys.argv", ["cli.py"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0
        call_args = mock_call.call_args[0][0]
        assert len(call_args) == 3

    @patch("rossum_agent.streamlit_app.cli.shutil.which")
    def test_main_exits_when_streamlit_not_found(self, mock_which: MagicMock):
        """Test that main() exits with error when streamlit is not found."""
        mock_which.return_value = None

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
