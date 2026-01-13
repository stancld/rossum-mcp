"""Tests for rossum_agent.streamlit_app.render_modules module."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from rossum_agent.streamlit_app.render_modules import (
    MERMAID_BLOCK_PATTERN,
    render_chat_history,
    render_markdown_with_mermaid,
    render_mermaid_html,
)

FIXED_NOW = datetime(2023, 11, 14, 12, 0, 0)
FIXED_TIMESTAMP = FIXED_NOW.timestamp()
DAY_SECONDS = 24 * 60 * 60


class TestRenderChatHistory:
    """Test render_chat_history function."""

    @pytest.fixture
    def mock_redis_storage(self):
        """Create a mock RedisStorage instance."""
        storage = MagicMock()
        storage.is_connected.return_value = True
        return storage

    @pytest.fixture
    def mock_st(self):
        """Create a mock streamlit module with all required methods."""
        with (
            patch("rossum_agent.streamlit_app.render_modules.st") as mock,
            patch("rossum_agent.streamlit_app.render_modules.datetime") as mock_datetime,
        ):
            mock_datetime.now.return_value = FIXED_NOW
            mock_datetime.fromtimestamp = datetime.fromtimestamp
            mock.markdown = MagicMock()
            mock.subheader = MagicMock()
            mock.info = MagicMock()
            mock.warning = MagicMock()
            mock.button = MagicMock(return_value=False)
            mock.expander = MagicMock()
            mock.expander.return_value.__enter__ = MagicMock()
            mock.expander.return_value.__exit__ = MagicMock()
            mock.query_params = {}
            mock.rerun = MagicMock()
            yield mock

    def test_renders_header(self, mock_redis_storage, mock_st):
        """Test that chat history header is rendered."""
        mock_redis_storage.list_all_chats.return_value = []
        render_chat_history(mock_redis_storage, "chat-123")

        mock_st.markdown.assert_called_with("---")
        mock_st.subheader.assert_called_with("Chat History")

    def test_shows_no_history_message_when_empty(self, mock_redis_storage, mock_st):
        """Test that 'No chat history' message is shown when list is empty."""
        mock_redis_storage.list_all_chats.return_value = []
        render_chat_history(mock_redis_storage, "chat-123")

        mock_st.info.assert_called_with("No chat history yet")

    def test_shows_warning_when_redis_disconnected(self, mock_redis_storage, mock_st):
        """Test that warning is shown when Redis is not connected."""
        mock_redis_storage.is_connected.return_value = False
        render_chat_history(mock_redis_storage, "chat-123")

        mock_st.warning.assert_called_with("Redis not connected - chat history unavailable")

    def test_displays_today_chats(self, mock_redis_storage, mock_st):
        """Test that today's chats are displayed with correct header."""
        mock_redis_storage.list_all_chats.return_value = [
            {"chat_id": "chat-1", "first_message": "Hello world", "timestamp": FIXED_TIMESTAMP}
        ]
        render_chat_history(mock_redis_storage, "chat-123")

        mock_st.markdown.assert_any_call("**Today**")
        mock_st.button.assert_called()

    def test_truncates_long_messages(self, mock_redis_storage, mock_st):
        """Test that long messages are truncated to 40 characters."""
        long_message = "A" * 50
        mock_redis_storage.list_all_chats.return_value = [
            {"chat_id": "chat-1", "first_message": long_message, "timestamp": FIXED_TIMESTAMP}
        ]
        render_chat_history(mock_redis_storage, "chat-123")

        call_args = mock_st.button.call_args_list[0]
        button_label = call_args[0][0]
        assert "..." in button_label
        assert len(button_label) < len(long_message) + 10

    def test_shows_pin_icon_for_current_chat(self, mock_redis_storage, mock_st):
        """Test that current chat shows pin icon."""
        current_chat_id = "chat-123"
        mock_redis_storage.list_all_chats.return_value = [
            {"chat_id": current_chat_id, "first_message": "Current chat", "timestamp": FIXED_TIMESTAMP}
        ]
        render_chat_history(mock_redis_storage, current_chat_id)

        call_args = mock_st.button.call_args_list[0]
        button_label = call_args[0][0]
        assert "📌" in button_label

    def test_shows_chat_icon_for_other_chats(self, mock_redis_storage, mock_st):
        """Test that non-current chats show chat icon."""
        mock_redis_storage.list_all_chats.return_value = [
            {"chat_id": "chat-456", "first_message": "Other chat", "timestamp": FIXED_TIMESTAMP}
        ]
        render_chat_history(mock_redis_storage, "chat-123")

        call_args = mock_st.button.call_args_list[0]
        button_label = call_args[0][0]
        assert "💬" in button_label

    def test_disables_current_chat_button(self, mock_redis_storage, mock_st):
        """Test that current chat button is disabled."""
        current_chat_id = "chat-123"
        mock_redis_storage.list_all_chats.return_value = [
            {"chat_id": current_chat_id, "first_message": "Current", "timestamp": FIXED_TIMESTAMP}
        ]
        render_chat_history(mock_redis_storage, current_chat_id)

        call_kwargs = mock_st.button.call_args_list[0][1]
        assert call_kwargs.get("disabled") is True

    def test_groups_chats_by_time_period(self, mock_redis_storage, mock_st):
        """Test that chats are grouped into today and previous 30 days."""
        five_days_ago = FIXED_TIMESTAMP - (5 * DAY_SECONDS)

        mock_redis_storage.list_all_chats.return_value = [
            {"chat_id": "chat-1", "first_message": "Today chat", "timestamp": FIXED_TIMESTAMP},
            {"chat_id": "chat-2", "first_message": "Old chat", "timestamp": five_days_ago},
        ]
        render_chat_history(mock_redis_storage, "chat-123")

        mock_st.markdown.assert_any_call("**Today**")
        mock_st.expander.assert_called_with("**Previous 30 days**", expanded=False)

    def test_passes_user_id_to_list_all_chats(self, mock_redis_storage, mock_st):
        """Test that user_id is passed to list_all_chats."""
        mock_redis_storage.list_all_chats.return_value = []
        render_chat_history(mock_redis_storage, "chat-123", user_id="user-456")

        mock_redis_storage.list_all_chats.assert_called_once_with("user-456")

    def test_passes_none_user_id_when_not_provided(self, mock_redis_storage, mock_st):
        """Test that None is passed when user_id is not provided."""
        mock_redis_storage.list_all_chats.return_value = []
        render_chat_history(mock_redis_storage, "chat-123")

        mock_redis_storage.list_all_chats.assert_called_once_with(None)

    def test_handles_chat_at_30_day_boundary(self, mock_redis_storage, mock_st):
        """Test handling of chat exactly 30 days ago."""
        thirty_days_ago = FIXED_TIMESTAMP - (30 * DAY_SECONDS)

        mock_redis_storage.list_all_chats.return_value = [
            {"chat_id": "chat-1", "first_message": "Boundary chat", "timestamp": thirty_days_ago}
        ]
        render_chat_history(mock_redis_storage, "chat-123")

        mock_st.expander.assert_called_with("**Previous 30 days**", expanded=False)

    def test_handles_chat_older_than_30_days(self, mock_redis_storage, mock_st):
        """Test that chats older than 30 days are not displayed."""
        forty_days_ago = FIXED_TIMESTAMP - (40 * DAY_SECONDS)

        mock_redis_storage.list_all_chats.return_value = [
            {"chat_id": "chat-1", "first_message": "Old chat", "timestamp": forty_days_ago}
        ]
        render_chat_history(mock_redis_storage, "chat-123")

        mock_st.button.assert_not_called()

    def test_short_message_not_truncated(self, mock_redis_storage, mock_st):
        """Test that short messages are not truncated."""
        short_message = "Short"
        mock_redis_storage.list_all_chats.return_value = [
            {"chat_id": "chat-1", "first_message": short_message, "timestamp": FIXED_TIMESTAMP}
        ]
        render_chat_history(mock_redis_storage, "chat-123")

        call_args = mock_st.button.call_args_list[0]
        button_label = call_args[0][0]
        assert short_message in button_label
        assert "..." not in button_label


class TestMermaidBlockPattern:
    """Test MERMAID_BLOCK_PATTERN regex."""

    def test_matches_simple_mermaid_block(self):
        """Test that pattern matches a simple mermaid code block."""
        content = "```mermaid\ngraph TD\nA-->B\n```"
        match = MERMAID_BLOCK_PATTERN.search(content)
        assert match is not None
        assert "graph TD" in match.group(1)

    def test_matches_mermaid_block_with_surrounding_content(self):
        """Test pattern matches mermaid block in mixed content."""
        content = "Some text\n```mermaid\nflowchart LR\nA-->B\n```\nMore text"
        match = MERMAID_BLOCK_PATTERN.search(content)
        assert match is not None
        assert "flowchart LR" in match.group(1)

    def test_captures_multiline_diagram(self):
        """Test pattern captures multiline mermaid diagrams."""
        diagram = """graph TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Do something]
    B -->|No| D[Do something else]"""
        content = f"```mermaid\n{diagram}\n```"
        match = MERMAID_BLOCK_PATTERN.search(content)
        assert match is not None
        assert "Decision" in match.group(1)
        assert "Do something" in match.group(1)

    def test_does_not_match_non_mermaid_code_block(self):
        """Test pattern does not match other code blocks."""
        content = "```python\nprint('hello')\n```"
        match = MERMAID_BLOCK_PATTERN.search(content)
        assert match is None

    def test_finds_multiple_mermaid_blocks(self):
        """Test pattern finds all mermaid blocks using findall."""
        content = "```mermaid\ngraph A\n```\ntext\n```mermaid\ngraph B\n```"
        matches = MERMAID_BLOCK_PATTERN.findall(content)
        assert len(matches) == 2
        assert "graph A" in matches[0]
        assert "graph B" in matches[1]

    def test_split_content_with_mermaid(self):
        """Test split behavior used by render_markdown_with_mermaid."""
        content = "Before\n```mermaid\ndiagram\n```\nAfter"
        parts = MERMAID_BLOCK_PATTERN.split(content)
        assert len(parts) == 3
        assert "Before" in parts[0]
        assert "diagram" in parts[1]
        assert "After" in parts[2]


class TestRenderMermaidHtml:
    """Test render_mermaid_html function."""

    @pytest.fixture
    def mock_components(self):
        """Mock streamlit.components.v1."""
        with patch("rossum_agent.streamlit_app.render_modules.components") as mock:
            yield mock

    def test_calls_components_html(self, mock_components):
        """Test that components.html is called."""
        render_mermaid_html("graph TD\nA-->B")
        mock_components.html.assert_called_once()

    def test_uses_default_height(self, mock_components):
        """Test that default height of 400 is used."""
        render_mermaid_html("graph TD")
        call_kwargs = mock_components.html.call_args[1]
        assert call_kwargs["height"] == 400

    def test_uses_custom_height(self, mock_components):
        """Test that custom height can be specified."""
        render_mermaid_html("graph TD", height=600)
        call_kwargs = mock_components.html.call_args[1]
        assert call_kwargs["height"] == 600

    def test_enables_scrolling(self, mock_components):
        """Test that scrolling is enabled."""
        render_mermaid_html("graph TD")
        call_kwargs = mock_components.html.call_args[1]
        assert call_kwargs["scrolling"] is True

    def test_escapes_html_in_code(self, mock_components):
        """Test that HTML special characters are escaped."""
        render_mermaid_html("A[<script>alert('xss')</script>]-->B")
        html_content = mock_components.html.call_args[0][0]
        assert "<script>alert" not in html_content
        assert "&lt;script&gt;" in html_content

    def test_includes_mermaid_script(self, mock_components):
        """Test that mermaid.js script is included."""
        render_mermaid_html("graph TD")
        html_content = mock_components.html.call_args[0][0]
        assert "mermaid.min.js" in html_content

    def test_includes_mermaid_initialize(self, mock_components):
        """Test that mermaid.initialize is called."""
        render_mermaid_html("graph TD")
        html_content = mock_components.html.call_args[0][0]
        assert "mermaid.initialize" in html_content

    def test_strips_whitespace_from_code(self, mock_components):
        """Test that whitespace is stripped from code."""
        render_mermaid_html("  graph TD  \n  A-->B  \n  ")
        html_content = mock_components.html.call_args[0][0]
        assert "graph TD" in html_content


class TestRenderMarkdownWithMermaid:
    """Test render_markdown_with_mermaid function."""

    @pytest.fixture
    def mock_st_and_render(self):
        """Mock st.markdown and render_mermaid_html."""
        with (
            patch("rossum_agent.streamlit_app.render_modules.st") as mock_st,
            patch("rossum_agent.streamlit_app.render_modules.render_mermaid_html") as mock_render,
        ):
            yield mock_st, mock_render

    def test_renders_plain_markdown(self, mock_st_and_render):
        """Test that plain markdown is rendered with st.markdown."""
        mock_st, mock_render = mock_st_and_render
        render_markdown_with_mermaid("# Hello World")
        mock_st.markdown.assert_called_once_with("# Hello World")
        mock_render.assert_not_called()

    def test_renders_mermaid_block(self, mock_st_and_render):
        """Test that mermaid blocks are rendered with render_mermaid_html."""
        _mock_st, mock_render = mock_st_and_render
        render_markdown_with_mermaid("```mermaid\ngraph TD\nA-->B\n```")
        mock_render.assert_called_once()
        assert "graph TD" in mock_render.call_args[0][0]

    def test_renders_mixed_content_in_order(self, mock_st_and_render):
        """Test that mixed content renders markdown and mermaid in order."""
        mock_st, mock_render = mock_st_and_render
        content = "# Header\n```mermaid\ngraph TD\n```\n## Footer"
        render_markdown_with_mermaid(content)

        # Should have called st.markdown for both text sections
        assert mock_st.markdown.call_count == 2
        # Should have called render_mermaid_html once
        mock_render.assert_called_once()

    def test_skips_empty_parts(self, mock_st_and_render):
        """Test that empty parts are skipped."""
        mock_st, mock_render = mock_st_and_render
        content = "```mermaid\ngraph TD\n```"
        render_markdown_with_mermaid(content)
        # Only the mermaid part should be rendered, empty strings skipped
        mock_render.assert_called_once()
        mock_st.markdown.assert_not_called()

    def test_handles_multiple_mermaid_blocks(self, mock_st_and_render):
        """Test handling of multiple mermaid blocks."""
        mock_st, mock_render = mock_st_and_render
        content = "Text\n```mermaid\ngraph A\n```\nMiddle\n```mermaid\ngraph B\n```\nEnd"
        render_markdown_with_mermaid(content)

        # Should have called st.markdown for text sections
        assert mock_st.markdown.call_count == 3
        # Should have called render_mermaid_html for both diagrams
        assert mock_render.call_count == 2

    def test_preserves_markdown_content(self, mock_st_and_render):
        """Test that markdown content is passed correctly."""
        mock_st, _mock_render = mock_st_and_render
        markdown_text = "# Title\n\nSome **bold** text"
        render_markdown_with_mermaid(markdown_text)
        mock_st.markdown.assert_called_once_with(markdown_text)
