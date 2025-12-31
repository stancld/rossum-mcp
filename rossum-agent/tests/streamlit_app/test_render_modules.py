"""Tests for rossum_agent.streamlit_app.render_modules module."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from rossum_agent.streamlit_app.render_modules import render_chat_history

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
