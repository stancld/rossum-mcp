"""Rossum Streamlit Test Bed App.

Web interface for testing the Rossum Document Processing Agent using Streamlit.

Usage:
    streamlit run rossum_agent/streamlit_app/app.py
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import pathlib
import time
from typing import TYPE_CHECKING, Literal

import streamlit as st
from rossum_mcp.logging_config import setup_logging

from rossum_agent.agent import AgentConfig, create_agent
from rossum_agent.agent_logging import log_agent_result
from rossum_agent.prompts.system_prompt import get_system_prompt
from rossum_agent.redis_storage import ChatMetadata, RedisStorage, get_commit_sha
from rossum_agent.rossum_mcp_integration import connect_mcp_server
from rossum_agent.streamlit_app.beep_sound import generate_beep_wav
from rossum_agent.streamlit_app.render_modules import (
    MERMAID_BLOCK_PATTERN,
    render_chat_history,
    render_markdown_with_mermaid,
)
from rossum_agent.streamlit_app.response_formatting import ChatResponse, parse_and_format_final_answer
from rossum_agent.tools import set_mcp_connection, set_output_dir
from rossum_agent.url_context import RossumUrlContext, extract_url_context, format_context_for_prompt
from rossum_agent.user_detection import detect_user_id, normalize_user_id
from rossum_agent.utils import (
    cleanup_session_output_dir,
    create_session_output_dir,
    generate_chat_id,
    get_generated_files,
    get_generated_files_with_metadata,
    is_valid_chat_id,
    set_session_output_dir,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from anthropic.types import ImageBlockParam, TextBlockParam

    from rossum_agent.agent import AgentStep
    from rossum_agent.agent.types import UserContent

# Generate beep and encode as base64 data URL
_beep_wav = generate_beep_wav(frequency=440, duration=0.33)
_beep_b64 = base64.b64encode(_beep_wav).decode("ascii")
BEEP_HTML = f'<audio src="data:audio/wav;base64,{_beep_b64}" autoplay></audio>'

LOGO_PATH = pathlib.Path(__file__).parent.parent / "assets" / "Primary_light_logo.png"

# Configure logging with Redis integration
setup_logging(app_name="rossum-agent", log_level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


# Page config - must be first Streamlit command and at module level
st.set_page_config(page_title="Rossum Agent", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")


async def run_agent_turn(
    rossum_api_token: str,
    rossum_api_base_url: str,
    mcp_mode: Literal["read-only", "read-write"],
    prompt: UserContent,
    conversation_history: list[dict[str, str]],
    on_step: Callable[[AgentStep], None],
    rossum_url: str | None = None,
) -> None:
    """Run a single agent turn with proper MCP connection lifecycle.

    Creates MCP connection, runs the agent, and cleans up within a single event loop.

    Args:
        rossum_api_token: Rossum API token.
        rossum_api_base_url: Rossum API base URL.
        mcp_mode: MCP mode ('read-only' or 'read-write').
        prompt: User's input prompt (text or multimodal content).
        conversation_history: Previous messages for context.
        on_step: Callback function called for each step as it completes.
        rossum_url: Optional Rossum app URL for context extraction.
    """
    system_prompt = get_system_prompt()

    url_context = extract_url_context(rossum_url)
    if not url_context.is_empty():
        context_section = format_context_for_prompt(url_context)
        system_prompt = system_prompt + "\n\n---\n" + context_section

    async with connect_mcp_server(
        rossum_api_token=rossum_api_token, rossum_api_base_url=rossum_api_base_url, mcp_mode=mcp_mode
    ) as mcp_connection:
        set_mcp_connection(mcp_connection, asyncio.get_event_loop())

        agent = await create_agent(mcp_connection=mcp_connection, system_prompt=system_prompt, config=AgentConfig())

        for msg in conversation_history:
            if msg["role"] == "user":
                agent.add_user_message(msg["content"])
            elif msg["role"] == "assistant":
                agent.add_assistant_message(msg["content"])

        async for step in agent.run(prompt):
            on_step(step)


def _initialize_user_and_storage() -> None:
    """Initialize user ID and Redis storage in session state."""
    jwt_enabled = bool(os.getenv("TELEPORT_JWT_JWKS_URL"))
    st.session_state.user_isolation_enabled = jwt_enabled

    if "user_id" not in st.session_state:
        headers = dict(st.context.headers) if hasattr(st.context, "headers") else None
        jwt_token = headers.get("Teleport-Jwt-Assertion") if headers else None
        user_id = detect_user_id(jwt_token=jwt_token)
        st.session_state.user_id = normalize_user_id(user_id)

    if "redis_storage" not in st.session_state:
        st.session_state.redis_storage = RedisStorage()


def _initialize_chat_id() -> None:
    """Initialize chat ID from URL or generate a new one."""
    url_chat_id = st.query_params.get("chat_id")
    url_shared_user_id = st.query_params.get("user_id")

    if url_chat_id and is_valid_chat_id(url_chat_id):
        if "chat_id" not in st.session_state or st.session_state.chat_id != url_chat_id:
            st.session_state.chat_id = url_chat_id
            st.session_state.shared_user_id = url_shared_user_id
            for key in ["messages", "output_dir"]:
                if key in st.session_state:
                    del st.session_state[key]
            if "uploaded_images" in st.session_state:
                st.session_state.uploaded_images = []
            if "uploader_key_counter" in st.session_state:
                st.session_state.uploader_key_counter += 1
            logger.info(f"Loaded chat ID from URL: {url_chat_id}, shared_user_id: {url_shared_user_id}")
    elif "chat_id" not in st.session_state:
        st.session_state.chat_id = generate_chat_id()
        st.query_params["chat_id"] = st.session_state.chat_id
        logger.info(f"Generated new chat ID: {st.session_state.chat_id}")


def _initialize_session_defaults() -> None:
    """Initialize default session state values."""
    if "output_dir" not in st.session_state:
        st.session_state.output_dir = create_session_output_dir()
    set_session_output_dir(st.session_state.output_dir)
    set_output_dir(st.session_state.output_dir)

    if "rossum_api_token" not in st.session_state:
        st.session_state.rossum_api_token = os.getenv("ROSSUM_API_TOKEN", "") if os.getenv("DEBUG") else ""
    if "rossum_api_base_url" not in st.session_state:
        st.session_state.rossum_api_base_url = os.getenv("ROSSUM_API_BASE_URL", "") if os.getenv("DEBUG") else ""
    if "credentials_saved" not in st.session_state:
        st.session_state.credentials_saved = bool(
            st.session_state.rossum_api_token and st.session_state.rossum_api_base_url
        )

    if "read_write_disabled" not in st.session_state:
        st.session_state.read_write_disabled = os.getenv("ROSSUM_DISABLE_READ_WRITE", "").lower() in [
            "true",
            "1",
            "yes",
        ]
    if "mcp_mode" not in st.session_state:
        st.session_state.mcp_mode = "read-write"

    if "rossum_url_context" not in st.session_state:
        st.session_state.rossum_url_context = RossumUrlContext()

    if "uploaded_images" not in st.session_state:
        st.session_state.uploaded_images = []

    if "uploader_key_counter" not in st.session_state:
        st.session_state.uploader_key_counter = 0


def _load_messages_from_redis() -> None:
    """Load messages from Redis or initialize empty list."""
    if "messages" in st.session_state:
        return

    if not st.session_state.redis_storage.is_connected():
        st.session_state.messages = []
        return

    shared_user_id = st.session_state.get("shared_user_id")
    if shared_user_id:
        user_id = shared_user_id if st.session_state.user_isolation_enabled else None
        logger.info(f"Loading shared conversation from user: {shared_user_id}")
    else:
        user_id = st.session_state.user_id if st.session_state.user_isolation_enabled else None

    chat_data = st.session_state.redis_storage.load_chat(
        user_id, st.session_state.chat_id, st.session_state.output_dir
    )
    if chat_data:
        st.session_state.messages = chat_data.messages
        logger.info(f"Loaded {len(chat_data.messages)} messages from Redis for chat {st.session_state.chat_id}")
    else:
        st.session_state.messages = []
        logger.info(f"No messages found in Redis for chat {st.session_state.chat_id}, starting fresh")


def _render_credentials_section() -> None:
    """Render the credentials section in sidebar."""
    st.markdown("---")
    st.subheader("Rossum API Credentials")

    if not st.session_state.credentials_saved:
        st.warning("⚠️ Please enter your Rossum API credentials")
        api_base_url = st.text_input(
            "API Base URL",
            value=st.session_state.rossum_api_base_url,
            placeholder="https://your-instance.rossum.app",
            type="default",
        )
        api_token = st.text_input(
            "API Token",
            value=st.session_state.rossum_api_token,
            placeholder="Your Rossum API token",
            type="password",
        )
        if st.button("Save Credentials", type="primary"):
            if api_base_url and api_token:
                st.session_state.rossum_api_token = api_token
                st.session_state.rossum_api_base_url = api_base_url
                st.session_state.credentials_saved = True
                st.rerun()
            else:
                st.error("Both fields are required")
    else:
        st.success("✅ Credentials configured")
        with st.expander("View Credentials"):
            st.text_input("API Base URL", value=st.session_state.rossum_api_base_url, disabled=True)
            token_display = (
                st.session_state.rossum_api_token[:8] + "..."
                if len(st.session_state.rossum_api_token) > 8
                else st.session_state.rossum_api_token
            )
            st.text_input("API Token", value=token_display, disabled=True)
        if st.button("Update Credentials"):
            st.session_state.credentials_saved = False
            st.rerun()

    if os.getenv("DEBUG"):
        st.markdown("---")
        st.subheader("MCP Mode")
        mode_options = ["read-only", "read-write"]
        current_index = (
            mode_options.index(st.session_state.mcp_mode) if st.session_state.mcp_mode in mode_options else 0
        )
        selected_mode = st.radio(
            "Select mode:",
            options=mode_options,
            index=current_index,
            horizontal=True,
            disabled=st.session_state.read_write_disabled,
        )
        if selected_mode != st.session_state.mcp_mode:
            st.session_state.mcp_mode = selected_mode


def _render_url_context_section() -> None:
    """Render the URL context section in sidebar."""
    st.markdown("---")
    st.subheader("Current Context")

    current_url = st.text_input(
        "Rossum URL",
        value=st.session_state.rossum_url_context.raw_url or "",
        placeholder="Paste Rossum app URL here",
        help="Paste a Rossum application URL to provide context (queue, annotation, etc.)",
    )

    if current_url != (st.session_state.rossum_url_context.raw_url or ""):
        st.session_state.rossum_url_context = extract_url_context(current_url)

    if not st.session_state.rossum_url_context.is_empty():
        context_str = st.session_state.rossum_url_context.to_context_string()
        st.success(f"✅ {context_str}")
    elif current_url:
        st.warning("⚠️ No context extracted from URL")


def _render_quick_actions() -> None:
    """Render quick actions section in sidebar."""
    st.subheader("Quick Actions")

    if not st.session_state.get("shared_user_id") and st.button("🔗 Get Shareable Link"):
        public_url = os.getenv("PUBLIC_URL")
        if public_url:
            base_url = public_url.rstrip("/")
        else:
            host = st.context.headers.get("host", "localhost:8501")
            protocol = "https" if "localhost" not in host else "http"
            base_url = f"{protocol}://{host}"

        share_url = f"{base_url}/?chat_id={st.session_state.chat_id}&user_id={st.session_state.user_id}"
        st.code(share_url, language=None)

    if st.button("🔄 Reset Conversation"):
        st.session_state.messages = []
        st.session_state.uploaded_images = []
        st.session_state.uploader_key_counter += 1
        if "output_dir" in st.session_state:
            cleanup_session_output_dir(st.session_state.output_dir)
        st.session_state.output_dir = create_session_output_dir()
        set_session_output_dir(st.session_state.output_dir)
        st.session_state.chat_id = generate_chat_id()
        st.query_params["chat_id"] = st.session_state.chat_id
        logger.info(f"Reset conversation with new chat ID: {st.session_state.chat_id}")
        st.rerun()


def _render_generated_files() -> dict[str, float]:
    """Render generated files section and return file metadata."""
    st.markdown("---")
    st.subheader("Generated Files")
    generated_files = get_generated_files(st.session_state.output_dir)
    generated_files_metadata = get_generated_files_with_metadata(st.session_state.output_dir)

    if generated_files:
        st.write(f"📁 {len(generated_files)} file(s) generated:")
        for file_path in generated_files:
            file_name = pathlib.Path(file_path).name
            try:
                with open(file_path, "rb") as f:
                    file_content = f.read()
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(file_name)
                with col2:
                    st.download_button(label="⬇️", data=file_content, file_name=file_name, key=f"download_{file_path}")
            except Exception as e:
                st.error(f"Error loading {file_name}: {e}")
    else:
        st.info("No files generated yet")

    return generated_files_metadata


def _render_sidebar() -> dict[str, float]:
    """Render the sidebar and return generated files metadata."""
    with st.sidebar:
        st.image(str(LOGO_PATH), width=200)
        _render_credentials_section()
        _render_url_context_section()
        _render_quick_actions()
        generated_files_metadata = _render_generated_files()

        user_id = st.session_state.user_id if st.session_state.user_isolation_enabled else None
        render_chat_history(st.session_state.redis_storage, st.session_state.chat_id, user_id)

        st.sidebar.divider()
        st.sidebar.caption(f"User ID: {st.session_state.user_id}")

    return generated_files_metadata


def _build_agent_prompt(prompt: str, uploaded_images: list[dict]) -> tuple[UserContent, int]:
    """Build agent prompt from text and optional images.

    Returns:
        Tuple of (agent_prompt, num_images)
    """
    if uploaded_images:
        content_blocks: list[ImageBlockParam | TextBlockParam] = []
        for img_data in uploaded_images:
            content_blocks.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": img_data["media_type"], "data": img_data["data"]},
                }
            )
        content_blocks.append({"type": "text", "text": prompt})
        st.session_state.uploaded_images = []
        return content_blocks, len(uploaded_images)
    return prompt, 0


def _render_image_upload() -> None:
    """Render image upload section."""
    col1, col2 = st.columns([1, 15])
    with col1:
        with st.popover("+", help="Attach images"):
            uploaded_files = st.file_uploader(
                "Upload images",
                type=["png", "jpg", "jpeg", "gif", "webp"],
                accept_multiple_files=True,
                key=f"image_uploader_{st.session_state.uploader_key_counter}",
                label_visibility="collapsed",
            )
            if uploaded_files:
                st.session_state.uploaded_images = []
                for uploaded_file in uploaded_files[:5]:
                    file_bytes = uploaded_file.read()
                    b64_data = base64.b64encode(file_bytes).decode("utf-8")
                    mime_type = uploaded_file.type or "image/png"
                    st.session_state.uploaded_images.append(
                        {"name": uploaded_file.name, "media_type": mime_type, "data": b64_data}
                    )
                    uploaded_file.seek(0)
                if len(uploaded_files) > 5:
                    st.warning("Max 5 images allowed. Only first 5 will be used.")

    with col2:
        if st.session_state.uploaded_images:
            thumb_cols = st.columns(len(st.session_state.uploaded_images) + 1)
            for idx, img_data in enumerate(st.session_state.uploaded_images):
                with thumb_cols[idx]:
                    st.image(f"data:{img_data['media_type']};base64,{img_data['data']}", width=50)
            with thumb_cols[-1]:
                if st.button("✕", key="clear_images", help="Clear images"):
                    st.session_state.uploaded_images = []
                    st.rerun()


def _process_user_input(generated_files_metadata: dict[str, float]) -> None:
    """Process user input and run the agent."""
    prompt = st.chat_input("Enter your instruction...")
    if not prompt:
        return

    logger.info(f"User prompt received: {prompt[:100]}...")

    uploaded_images = st.session_state.uploaded_images
    agent_prompt, num_images = _build_agent_prompt(prompt, uploaded_images)

    display_content = f"[{num_images} image(s) attached]\n\n{prompt}" if num_images > 0 else prompt
    st.session_state.messages.append({"role": "user", "content": display_content})

    if st.session_state.redis_storage.is_connected():
        user_id = st.session_state.user_id if st.session_state.user_isolation_enabled else None
        st.session_state.redis_storage.save_chat(
            user_id, st.session_state.chat_id, st.session_state.messages, str(st.session_state.output_dir)
        )

    with st.chat_message("user"):
        st.markdown(display_content)

    with st.chat_message("assistant"):
        _run_agent_and_display(prompt, agent_prompt, num_images, generated_files_metadata)


def _run_agent_and_display(
    prompt: str, agent_prompt: UserContent, num_images: int, generated_files_metadata: dict[str, float]
) -> None:
    """Run the agent and display results."""
    final_answer_text = None
    final_error_text = None

    try:
        start_time = time.time()
        chat_response = ChatResponse(prompt, output_placeholder=st.empty())
        conversation_history = st.session_state.messages[:-1]

        mcp_mode: Literal["read-only", "read-write"] = (
            "read-write" if st.session_state.mcp_mode == "read-write" else "read-only"
        )

        def process_step(step: AgentStep) -> None:
            nonlocal final_answer_text, final_error_text
            chat_response.process_step(step)
            if step.is_final:
                if step.final_answer:
                    final_answer_text = parse_and_format_final_answer(step.final_answer)
                elif step.error:
                    final_error_text = f"❌ Error: {step.error}"

        logger.info(
            f"Agent input context:\n"
            f"  - Prompt: {prompt[:500]}{'...' if len(prompt) > 500 else ''}\n"
            f"  - Num images: {num_images}\n"
            f"  - Conversation history length: {len(conversation_history)}\n"
            f"  - MCP mode: {mcp_mode}\n"
            f"  - Rossum URL context: {st.session_state.rossum_url_context.raw_url}"
        )

        asyncio.run(
            run_agent_turn(
                rossum_api_token=st.session_state.rossum_api_token,
                rossum_api_base_url=st.session_state.rossum_api_base_url,
                mcp_mode=mcp_mode,
                prompt=agent_prompt,
                conversation_history=conversation_history,
                on_step=process_step,
                rossum_url=st.session_state.rossum_url_context.raw_url,
            )
        )

        final_content = final_answer_text or final_error_text
        if final_content:
            st.session_state.messages.append({"role": "assistant", "content": final_content})
            _save_response_to_redis(chat_response)

        duration = time.time() - start_time
        if chat_response.result:
            log_agent_result(
                chat_response.result,
                prompt,
                duration,
                total_input_tokens=chat_response.total_input_tokens,
                total_output_tokens=chat_response.total_output_tokens,
            )
        logger.info("Agent response generated successfully")

        if final_answer_text:
            st.components.v1.html(BEEP_HTML, height=0)

        current_files_metadata = get_generated_files_with_metadata(st.session_state.output_dir)
        has_mermaid = final_answer_text and MERMAID_BLOCK_PATTERN.search(final_answer_text)
        if current_files_metadata != generated_files_metadata or has_mermaid:
            st.rerun()

    except Exception as e:
        logger.error(f"Error processing user request: {e}", exc_info=True)
        error_msg = f"❌ Error: {e!s}"
        st.error(error_msg)
        st.session_state.messages.append({"role": "assistant", "content": error_msg})


def _save_response_to_redis(chat_response: ChatResponse) -> None:
    """Save agent response to Redis with metadata."""
    if not st.session_state.redis_storage.is_connected():
        return

    user_id = st.session_state.get("user_id") if st.session_state.get("user_isolation_enabled", False) else None
    metadata = ChatMetadata(
        commit_sha=get_commit_sha(),
        total_input_tokens=chat_response.total_input_tokens,
        total_output_tokens=chat_response.total_output_tokens,
        total_tool_calls=chat_response.total_tool_calls,
        total_steps=chat_response.total_steps,
    )
    st.session_state.redis_storage.save_chat(
        user_id,
        st.session_state.chat_id,
        st.session_state.messages,
        str(st.session_state.output_dir),
        metadata=metadata,
    )


def main() -> None:
    """Main entry point for the Streamlit app."""
    _initialize_user_and_storage()
    _initialize_chat_id()
    _initialize_session_defaults()
    _load_messages_from_redis()

    generated_files_metadata = _render_sidebar()

    st.title("Rossum Agent")
    st.markdown("Test-bed agent for automating Rossum setup processes.")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            render_markdown_with_mermaid(message["content"])

    if not st.session_state.credentials_saved:
        st.chat_input("👈 Please enter your Rossum API credentials in the sidebar", disabled=True)
        return

    _render_image_upload()
    _process_user_input(generated_files_metadata)


if __name__ == "__main__":
    main()
