"""Rossum Streamlit App

Web interface for the Rossum Document Processing Agent using Streamlit.

Usage:
    streamlit run rossum_agent/app.py
"""

from __future__ import annotations

import base64
import logging
import os
import pathlib
import time
from typing import TYPE_CHECKING

import streamlit as st
from rossum_mcp.logging_config import setup_logging
from smolagents.memory import ActionStep, FinalAnswerStep, PlanningStep

from rossum_agent.agent import create_agent
from rossum_agent.agent_logging import log_agent_result
from rossum_agent.app_llm_response_formatting import ChatResponse, parse_and_format_final_answer
from rossum_agent.beep_sound import generate_beep_wav
from rossum_agent.redis_storage import RedisStorage
from rossum_agent.render_modules import render_chat_history
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
    from collections.abc import Iterator

# Generate beep and encode as base64 data URL
_beep_wav = generate_beep_wav(frequency=440, duration=0.33)
_beep_b64 = base64.b64encode(_beep_wav).decode("ascii")
BEEP_HTML = f'<audio src="data:audio/wav;base64,{_beep_b64}" autoplay></audio>'

LOGO_PATH = pathlib.Path(__file__).parent / "assets" / "Primary_light_logo.png"

# Configure logging with Redis integration
setup_logging(app_name="rossum-agent", log_level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


# Page config - must be first Streamlit command and at module level
st.set_page_config(page_title="Rossum Agent", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")


def main() -> None:  # noqa: C901
    # Auto-enable user isolation if Teleport JWT config is present
    jwt_enabled = bool(os.getenv("TELEPORT_JWT_JWKS_URL"))
    st.session_state.user_isolation_enabled = jwt_enabled

    # Initialize user ID (with automatic fallback to "default")
    if "user_id" not in st.session_state:
        headers = dict(st.context.headers) if hasattr(st.context, "headers") else None
        jwt_token = headers.get("Teleport-Jwt-Assertion") if headers else None

        # Detect user from JWT token
        user_id = detect_user_id(jwt_token=jwt_token)
        st.session_state.user_id = normalize_user_id(user_id)

    # Initialize Redis storage
    if "redis_storage" not in st.session_state:
        st.session_state.redis_storage = RedisStorage()

    # Initialize chat ID from URL or generate new one
    url_chat_id = st.query_params.get("chat_id")
    url_shared_user_id = st.query_params.get("user_id")  # For shared permalinks

    # Check if URL chat_id changed (permalink navigation)
    if url_chat_id and is_valid_chat_id(url_chat_id):
        if "chat_id" not in st.session_state or st.session_state.chat_id != url_chat_id:
            # Chat ID changed via permalink - reset session
            st.session_state.chat_id = url_chat_id
            st.session_state.shared_user_id = url_shared_user_id  # Store shared user_id if present
            if "messages" in st.session_state:
                del st.session_state.messages  # Force reload from Redis
            if "output_dir" in st.session_state:
                del st.session_state.output_dir  # Clear old files
            logger.info(f"Loaded chat ID from URL: {url_chat_id}, shared_user_id: {url_shared_user_id}")
    elif "chat_id" not in st.session_state:
        st.session_state.chat_id = generate_chat_id()
        st.query_params["chat_id"] = st.session_state.chat_id
        logger.info(f"Generated new chat ID: {st.session_state.chat_id}")

    # Initialize session-specific output directory
    if "output_dir" not in st.session_state:
        st.session_state.output_dir = create_session_output_dir()
    # Set the context variable for the current session
    set_session_output_dir(st.session_state.output_dir)

    # Initialize credentials in session state
    # Read from env variables for debugging if suitable
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
        st.session_state.mcp_mode = os.getenv("ROSSUM_MCP_MODE", "read-only")

    # Load messages from Redis or initialize empty list (BEFORE sidebar renders)
    if "messages" not in st.session_state:
        if st.session_state.redis_storage.is_connected():
            # Use shared_user_id if present (for shared permalinks), otherwise use current user_id
            shared_user_id = st.session_state.get("shared_user_id")
            if shared_user_id:
                # Loading shared conversation - use the original owner's user_id
                user_id = shared_user_id if st.session_state.user_isolation_enabled else None
                logger.info(f"Loading shared conversation from user: {shared_user_id}")
            else:
                # Loading own conversation
                user_id = st.session_state.user_id if st.session_state.user_isolation_enabled else None

            result = st.session_state.redis_storage.load_chat(
                user_id, st.session_state.chat_id, st.session_state.output_dir
            )
            if result:
                messages, _ = result
                st.session_state.messages = messages
                logger.info(f"Loaded {len(messages)} messages from Redis for chat {st.session_state.chat_id}")
            else:
                st.session_state.messages = []
                logger.info(f"No messages found in Redis for chat {st.session_state.chat_id}, starting fresh")
        else:
            st.session_state.messages = []

    # Sidebar
    with st.sidebar:
        st.image(str(LOGO_PATH), width=200)

        # Credentials section
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
                    if "agent" in st.session_state:
                        del st.session_state.agent
                    st.rerun()
                else:
                    st.error("Both fields are required")
        else:
            st.success("✅ Credentials configured")

            with st.expander("View Credentials"):
                st.text_input("API Base URL", value=st.session_state.rossum_api_base_url, disabled=True)
                st.text_input(
                    "API Token",
                    value=st.session_state.rossum_api_token[:8] + "..."
                    if len(st.session_state.rossum_api_token) > 8
                    else st.session_state.rossum_api_token,
                    disabled=True,
                )

            if st.button("Update Credentials"):
                st.session_state.credentials_saved = False
                if "agent" in st.session_state:
                    del st.session_state.agent
                st.rerun()

        # MCP Mode selection
        st.markdown("---")
        st.subheader("Agent Mode")

        if st.session_state.read_write_disabled:
            st.info("ℹ️ Read-write mode is disabled for current release.")  # noqa: RUF001
            new_mode = "read-only"
            st.radio(
                "Select mode:",
                options=["read-only"],
                index=0,
                help="Read-only mode prevents the agent from making changes to Rossum.",
                disabled=False,
            )
        else:
            new_mode = st.radio(
                "Select mode:",
                options=["read-write", "read-only"],
                index=0 if st.session_state.mcp_mode == "read-write" else 1,
                help="Read-only mode prevents the agent from making changes to Rossum. "
                "Read-write mode allows full operations including creating/updating resources.",
            )

        if new_mode != st.session_state.mcp_mode:
            st.session_state.mcp_mode = new_mode
            os.environ["ROSSUM_MCP_MODE"] = new_mode
            if "agent" in st.session_state:
                del st.session_state.agent
            st.rerun()

        mode_indicator = "🔒 Read-Only" if new_mode == "read-only" else "✏️ Read-Write"
        st.info(f"Current mode: **{mode_indicator}**")

        # Quick actions
        st.subheader("Quick Actions")

        # Share conversation button (only for own conversations)
        if not st.session_state.get("shared_user_id") and st.button("🔗 Get Shareable Link"):
            # Use PUBLIC_URL from environment if set, otherwise construct from headers
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
            if "agent" in st.session_state:
                del st.session_state.agent
            # Cleanup old session directory and create a new one
            if "output_dir" in st.session_state:
                cleanup_session_output_dir(st.session_state.output_dir)
            st.session_state.output_dir = create_session_output_dir()
            set_session_output_dir(st.session_state.output_dir)
            # Generate new chat ID for new conversation
            st.session_state.chat_id = generate_chat_id()
            st.query_params["chat_id"] = st.session_state.chat_id
            logger.info(f"Reset conversation with new chat ID: {st.session_state.chat_id}")
            st.rerun()

        # Generated files section
        st.markdown("---")
        st.subheader("Generated Files")
        generated_files = get_generated_files()
        generated_files_metadata = get_generated_files_with_metadata()

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
                        st.download_button(
                            label="⬇️",
                            data=file_content,
                            file_name=file_name,
                            key=f"download_{file_path}",
                        )
                except Exception as e:
                    st.error(f"Error loading {file_name}: {e}")
        else:
            st.info("No files generated yet")

        # Chat History section
        user_id = st.session_state.user_id if st.session_state.user_isolation_enabled else None
        is_shared_view = bool(st.session_state.get("shared_user_id"))
        render_chat_history(st.session_state.redis_storage, st.session_state.chat_id, user_id, is_shared_view)

        # Debug: Display normalized user_id
        st.sidebar.divider()
        st.sidebar.caption(f"User ID: {st.session_state.user_id}")

    # Main content
    st.title("Rossum Agent")
    st.markdown("Agent for automating Rossum setup processes.")

    # Initialize agent only if credentials are saved
    if "agent" not in st.session_state and st.session_state.credentials_saved:
        with st.spinner("Initializing agent..."):
            try:
                logger.info("Initializing Rossum agent")
                st.session_state.agent = create_agent(
                    rossum_api_token=st.session_state.rossum_api_token,
                    rossum_api_base_url=st.session_state.rossum_api_base_url,
                    mcp_mode=st.session_state.mcp_mode,
                    stream_outputs=False,
                )
                logger.info("Agent initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize agent: {e}", exc_info=True)
                st.error(f"Failed to initialize agent: {e}")
                st.stop()

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Disable chat input if credentials not saved
    if not st.session_state.credentials_saved:
        st.chat_input("👈 Please enter your Rossum API credentials in the sidebar", disabled=True)
        return

    # Process user input
    if prompt := st.chat_input("Enter your instruction..."):
        logger.info(f"User prompt received: {prompt[:100]}...")  # Log first 100 chars
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Persist user message to Redis
        if st.session_state.redis_storage.is_connected():
            user_id = st.session_state.user_id if st.session_state.user_isolation_enabled else None
            st.session_state.redis_storage.save_chat(
                user_id,
                st.session_state.chat_id,
                st.session_state.messages,
                str(st.session_state.output_dir),
            )

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            final_answer_text = None

            try:
                start_time = time.time()

                result_generator: Iterator[ActionStep | PlanningStep] = st.session_state.agent.run(
                    prompt, return_full_result=True, stream=True, reset=False
                )

                chat_response = ChatResponse(prompt, output_placeholder=st.empty(), start_time=start_time)

                for step in result_generator:
                    chat_response.process_step(step)

                    if isinstance(chat_response.result, FinalAnswerStep) and chat_response.result.output:
                        raw_answer = str(chat_response.result.output)
                        final_answer_text = parse_and_format_final_answer(raw_answer)

                    # Save final answer to chat history
                if final_answer_text:
                    st.session_state.messages.append({"role": "assistant", "content": final_answer_text})

                    # Persist to Redis
                    if st.session_state.redis_storage.is_connected():
                        user_id = (
                            st.session_state.get("user_id")
                            if st.session_state.get("user_isolation_enabled", False)
                            else None
                        )
                        st.session_state.redis_storage.save_chat(
                            user_id,
                            st.session_state.chat_id,
                            st.session_state.messages,
                            str(st.session_state.output_dir),
                        )

                    # Log final result
                    duration = time.time() - start_time
                    log_agent_result(chat_response.result, prompt, duration)
                    logger.info("Agent response generated successfully")

                    # Play beep sound when answer generation completes
                    st.components.v1.html(BEEP_HTML, height=0)

                    # Check if files were generated/modified and rerun to update sidebar
                    current_files_metadata = get_generated_files_with_metadata()
                    if current_files_metadata != generated_files_metadata:
                        st.rerun()

            except Exception as e:
                logger.error(f"Error processing user request: {e}", exc_info=True)
                error_msg = f"❌ Error: {e!s}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})


if __name__ == "__main__":
    main()
