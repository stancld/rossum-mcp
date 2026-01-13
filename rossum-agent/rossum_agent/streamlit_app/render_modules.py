"""Streamlit UI rendering modules for the Rossum Agent app."""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import TYPE_CHECKING

import streamlit as st
import streamlit.components.v1 as components

if TYPE_CHECKING:
    from rossum_agent.redis_storage import RedisStorage

MERMAID_BLOCK_PATTERN = re.compile(r"```mermaid\s*(.*?)```", re.DOTALL)

MERMAID_HTML_TEMPLATE = """
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<script>mermaid.initialize({{startOnLoad: true, theme: 'default'}});</script>
<div class="mermaid" style="background: white; padding: 10px; border-radius: 5px;">
{code}
</div>
"""


def render_mermaid_html(code: str, height: int = 400) -> None:
    """Render mermaid diagram using HTML component."""
    escaped_code = html.escape(code.strip())
    html_content = MERMAID_HTML_TEMPLATE.format(code=escaped_code)
    components.html(html_content, height=height, scrolling=True)


def render_markdown_with_mermaid(content: str) -> None:
    """Render markdown content with mermaid diagram support.

    Parses markdown content for ```mermaid``` code blocks and renders them
    using HTML components. Other content is rendered with st.markdown.
    """
    parts = MERMAID_BLOCK_PATTERN.split(content)
    for i, part in enumerate(parts):
        if not part.strip():
            continue
        if i % 2 == 1:
            render_mermaid_html(part)
        else:
            st.markdown(part)


def render_chat_history(redis_storage: RedisStorage, current_chat_id: str, user_id: str | None = None) -> None:
    """Render the chat history section in the sidebar.

    Args:
        redis_storage: Redis storage instance for retrieving chat history
        current_chat_id: The currently active chat ID
        user_id: Optional user ID for filtering chat history
    """
    st.markdown("---")
    st.subheader("Chat History")

    if redis_storage.is_connected():
        all_chats = redis_storage.list_all_chats(user_id)

        if all_chats:
            # Group chats by time period
            now = datetime.now()
            today_chats = []
            last_30_days_chats = []

            for chat in all_chats:
                chat_date = datetime.fromtimestamp(chat["timestamp"])
                days_ago = (now - chat_date).days

                if days_ago == 0:
                    today_chats.append(chat)
                elif days_ago <= 30:
                    last_30_days_chats.append(chat)

            # Display Today section
            if today_chats:
                st.markdown("**Today**")
                for chat in today_chats:
                    is_current = chat["chat_id"] == current_chat_id
                    prefix = "📌 " if is_current else "💬 "
                    chat_title = (
                        chat["first_message"][:40] + "..."
                        if len(chat["first_message"]) > 40
                        else chat["first_message"]
                    )

                    if st.button(
                        f"{prefix}{chat_title}",
                        key=f"chat_{chat['chat_id']}",
                        use_container_width=True,
                        disabled=is_current,
                    ):
                        st.query_params["chat_id"] = chat["chat_id"]
                        st.rerun()

            # Display Previous 30 days section
            if last_30_days_chats:
                with st.expander("**Previous 30 days**", expanded=False):
                    for chat in last_30_days_chats:
                        is_current = chat["chat_id"] == current_chat_id
                        prefix = "📌 " if is_current else "💬 "
                        chat_title = (
                            chat["first_message"][:40] + "..."
                            if len(chat["first_message"]) > 40
                            else chat["first_message"]
                        )

                        if st.button(
                            f"{prefix}{chat_title}",
                            key=f"chat_{chat['chat_id']}",
                            use_container_width=True,
                            disabled=is_current,
                        ):
                            st.query_params["chat_id"] = chat["chat_id"]
                            st.rerun()
        else:
            st.info("No chat history yet")
    else:
        st.warning("Redis not connected - chat history unavailable")
