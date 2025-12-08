"""WebSocket endpoint for rossum-agent API."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from smolagents.memory import ActionStep, FinalAnswerStep

from rossum_agent.api.models import ErrorResponse
from rossum_agent.api.serialization import serialize_step
from rossum_agent.api.session import ChatSession, SessionManager  # noqa: TC001
from rossum_agent.redis_storage import RedisStorage  # noqa: TC001
from rossum_agent.utils import (
    get_generated_files_with_metadata,
    is_valid_chat_id,
    set_session_output_dir,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/chat/{chat_id}")
async def websocket_chat(websocket: WebSocket, chat_id: str) -> None:
    """WebSocket endpoint for real-time chat with the agent.

    Protocol:
    1. Client connects with chat_id in URL
    2. Client sends config message with credentials
    3. Client sends prompt messages
    4. Server streams back step responses
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for chat {chat_id}")

    session_manager: SessionManager = websocket.app.state.session_manager
    session: ChatSession | None = None

    try:
        # Wait for config message first
        config_data = await websocket.receive_json()

        if config_data.get("type") != "config":
            await websocket.send_json(ErrorResponse(message="First message must be config").model_dump())
            await websocket.close()
            return

        # Create or resume session
        session = await session_manager.get_session(chat_id)
        if session is None:
            session = await session_manager.create_session(
                api_token=config_data["api_token"],
                api_base_url=config_data["api_base_url"],
                mcp_mode=config_data.get("mcp_mode", "read-only"),
                chat_id=chat_id if is_valid_chat_id(chat_id) else None,
            )
            # Update chat_id if it was generated
            if session.chat_id != chat_id:
                await websocket.send_json({"type": "chat_id_assigned", "chat_id": session.chat_id})

        # Set output directory context
        set_session_output_dir(session.output_dir)

        # Main message loop
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "prompt":
                prompt = data.get("content", "")
                if not prompt:
                    await websocket.send_json(ErrorResponse(message="Empty prompt").model_dump())
                    continue

                # Add user message
                session.messages.append({"role": "user", "content": prompt})
                session_manager.save_messages(session)

                # Run agent and stream results
                try:
                    await run_agent_streaming(websocket, session)
                except Exception as e:
                    logger.error(f"Agent error: {e}", exc_info=True)
                    await websocket.send_json(ErrorResponse(message=f"Agent error: {e!s}").model_dump())

            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for chat {chat_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        with contextlib.suppress(Exception):
            await websocket.send_json(ErrorResponse(message=str(e)).model_dump())
    finally:
        if session:
            # Keep session alive for reconnection
            logger.info(f"WebSocket closed for chat {session.chat_id}")


async def run_agent_streaming(websocket: WebSocket, session: ChatSession) -> None:
    """Run the agent and stream steps via WebSocket."""
    loop = asyncio.get_event_loop()

    # Track files before execution
    files_before = get_generated_files_with_metadata(session.output_dir)

    # Get the last user message as the prompt
    prompt = session.messages[-1]["content"]

    # Run agent in thread pool (blocking operation)
    def run_agent():
        set_session_output_dir(session.output_dir)
        return list(session.agent.run(prompt, stream=True, return_full_result=True, reset=False))

    steps = await loop.run_in_executor(None, run_agent)

    # Send each step
    final_answer = None
    for step in steps:
        step_data = serialize_step(step)
        await websocket.send_json(step_data)

        # Track final answer
        if isinstance(step, ActionStep) and step.is_final_answer and step.action_output:
            final_answer = str(step.action_output)
        elif isinstance(step, FinalAnswerStep) and step.output:
            final_answer = str(step.output)

    # Save assistant response
    if final_answer:
        session.messages.append({"role": "assistant", "content": final_answer})

    # Save files to Redis
    storage: RedisStorage = websocket.app.state.storage
    if storage.is_connected():
        storage.save_all_files(session.chat_id, session.output_dir)
        storage.save_chat(None, session.chat_id, session.messages, str(session.output_dir))

    # Check for new files
    files_after = get_generated_files_with_metadata(session.output_dir)
    new_files = [f for f in files_after if f not in files_before]

    # Send completion message
    await websocket.send_json(
        {
            "type": "complete",
            "chat_id": session.chat_id,
            "new_files": [Path(f).name for f in new_files],
        }
    )
