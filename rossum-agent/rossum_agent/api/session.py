"""Session management for rossum-agent API."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from smolagents import CodeAgent

from rossum_agent.agent import create_agent
from rossum_agent.utils import create_session_output_dir, generate_chat_id

if TYPE_CHECKING:
    from rossum_agent.redis_storage import RedisStorage


logger = logging.getLogger(__name__)


@dataclass
class ChatSession:
    """Represents an active chat session."""

    chat_id: str
    agent: CodeAgent
    output_dir: Path
    messages: list[dict[str, str]]
    api_token: str
    api_base_url: str
    mcp_mode: Literal["read-only", "read-write"]


class SessionManager:
    """Manages active chat sessions."""

    def __init__(self, storage: RedisStorage) -> None:
        self.storage = storage
        self._sessions: dict[str, ChatSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        api_token: str,
        api_base_url: str,
        mcp_mode: Literal["read-only", "read-write"] = "read-only",
        chat_id: str | None = None,
    ) -> ChatSession:
        """Create a new chat session with an agent."""
        async with self._lock:
            if chat_id is None:
                chat_id = generate_chat_id()

            output_dir = create_session_output_dir()

            # Create agent in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            agent = await loop.run_in_executor(
                None,
                lambda: create_agent(
                    rossum_api_token=api_token,
                    rossum_api_base_url=api_base_url,
                    mcp_mode=mcp_mode,
                    stream_outputs=False,
                ),
            )

            # Load existing messages from Redis if available
            messages: list[dict[str, str]] = []
            if self.storage.is_connected():
                result = self.storage.load_chat(None, chat_id, output_dir)
                if result:
                    messages, _ = result

            session = ChatSession(
                chat_id=chat_id,
                agent=agent,
                output_dir=output_dir,
                messages=messages,
                api_token=api_token,
                api_base_url=api_base_url,
                mcp_mode=mcp_mode,
            )
            self._sessions[chat_id] = session
            logger.info(f"Created session {chat_id}")
            return session

    async def get_session(self, chat_id: str) -> ChatSession | None:
        """Get an existing session by chat_id."""
        return self._sessions.get(chat_id)

    async def remove_session(self, chat_id: str) -> None:
        """Remove a session."""
        async with self._lock:
            if chat_id in self._sessions:
                del self._sessions[chat_id]
                logger.info(f"Removed session {chat_id}")

    def save_messages(self, session: ChatSession) -> None:
        """Persist messages to Redis."""
        if self.storage.is_connected():
            self.storage.save_chat(None, session.chat_id, session.messages, str(session.output_dir))
