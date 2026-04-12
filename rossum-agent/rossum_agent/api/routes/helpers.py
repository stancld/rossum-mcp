"""Shared helpers for message route handlers."""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from anthropic.types import TextBlock

from rossum_agent.agent.memory import AgentMemory
from rossum_agent.api.dependencies import RossumCredentials
from rossum_agent.api.models.schemas import DocumentContent, ImageContent, MessageRequest, Persona, StreamDoneEvent
from rossum_agent.api.services.agent_service import AgentService
from rossum_agent.api.services.chat_service import ChatService
from rossum_agent.bedrock_client import create_async_bedrock_client, get_small_model_id
from rossum_agent.change_tracking.store import CommitStore
from rossum_agent.chat_models import ChatData
from rossum_agent.valkey_client import ValkeyConnection

if TYPE_CHECKING:
    from rossum_agent.api.services.agent_service import StreamEvent

logger = logging.getLogger(__name__)

SSE_KEEPALIVE_INTERVAL = 15
SSE_KEEPALIVE_COMMENT = ": keepalive\n\n"


async def generate_chat_summary(
    user_prompt: str, previous_summary: str | None = None, url_context: str | None = None
) -> str | None:
    try:
        context_prefix = f"Context: {url_context}\n" if url_context else ""
        if previous_summary:
            prompt = (
                f"{context_prefix}"
                f"Current summary: {previous_summary}\n"
                f"New user message: {user_prompt[:500]}\n\n"
                f"Update the summary to cover the full conversation. One sentence, max 10 words."
            )
        else:
            prompt = f"{context_prefix}Summarize this in one sentence (max 10 words): {user_prompt[:500]}"

        client = create_async_bedrock_client()
        response = await client.messages.create(
            model=get_small_model_id(),
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )
        text_block = next((b for b in response.content if isinstance(b, TextBlock)), None)
        return text_block.text.strip() if text_block else None
    except Exception as e:
        logger.warning(f"Failed to generate chat summary: {e}")
        return None


def save_chat_history(
    chat_service: ChatService,
    agent_service: AgentService,
    credentials: RossumCredentials,
    chat_id: str,
    chat_data: ChatData,
    history: list[dict],
    user_prompt: str,
    final_response: str | None,
    images: list[ImageContent] | None,
    documents: list[DocumentContent] | None,
    output_dir: Path | None,
    memory: AgentMemory | None,
    done_event: StreamDoneEvent | None = None,
    summary: str | None = None,
) -> None:
    if done_event:
        chat_data.metadata.total_input_tokens += done_event.input_tokens
        chat_data.metadata.total_output_tokens += done_event.output_tokens
        chat_data.metadata.total_steps += done_event.total_steps
        if done_event.config_commit_hash:
            chat_data.metadata.config_commits.append(done_event.config_commit_hash)
    if summary is not None:
        chat_data.metadata.summary = summary

    updated_history = agent_service.build_updated_history(
        existing_history=history,
        user_prompt=user_prompt,
        final_response=final_response,
        images=images,
        documents=documents,
        memory=memory,
    )
    chat_service.save_messages(
        user_id=credentials.user_id,
        chat_id=chat_id,
        messages=updated_history,
        output_dir=output_dir,
        metadata=chat_data.metadata,
    )


async def watch_disconnect(request, chat_id: str, agent_service: AgentService) -> None:
    try:
        while True:
            if await request.is_disconnected():
                logger.info(f"Client disconnected for chat {chat_id}, cancelling run")
                agent_service.cancel_run(chat_id)
                return
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        logger.debug(f"Disconnect watcher for chat {chat_id} cancelled")


def resolve_mcp_mode(message: MessageRequest, chat_data: ChatData) -> Literal["read-only", "read-write"]:
    if message.mcp_mode is not None:
        chat_data.metadata.mcp_mode = message.mcp_mode
        return message.mcp_mode
    return chat_data.metadata.mcp_mode


def resolve_persona(message: MessageRequest, chat_data: ChatData) -> Persona:
    if message.persona is not None:
        chat_data.metadata.persona = message.persona
    return chat_data.metadata.persona


async def with_sse_keepalive(
    events: AsyncIterator[StreamEvent],
    interval: float = SSE_KEEPALIVE_INTERVAL,
) -> AsyncIterator[tuple[StreamEvent | None, bool]]:
    """Wrap an async event stream with periodic SSE keepalive signals.

    Yields (event, False) for real events and (None, True) for keepalive ticks.

    Uses asyncio.wait() instead of asyncio.wait_for() to avoid cancelling the
    pending anext() task on timeout, which would corrupt the async generator state.

    Context is captured from each completed task and passed to the next one,
    so that context variables set by the async generator propagate across iterations.
    """
    ctx: contextvars.Context | None = None
    pending: asyncio.Task = asyncio.create_task(anext(events))
    try:
        while True:
            done, _ = await asyncio.wait({pending}, timeout=interval)
            if not done:
                yield None, True
                continue
            ctx = pending.get_context()
            try:
                event = pending.result()
            except StopAsyncIteration:
                break
            yield event, False
            pending = asyncio.create_task(anext(events), context=ctx)
    finally:
        if not pending.done():
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration):
                await pending


def get_commit_store() -> CommitStore | None:
    try:
        conn = ValkeyConnection()
        if conn.is_connected():
            return CommitStore(conn.client)
    except Exception as e:
        logger.warning(f"Commit store is unavailable: {e}")
    return None
