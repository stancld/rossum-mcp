"""Rossum Streamlit App

Web interface for the Rossum Document Processing Agent using Streamlit.

Usage:
    streamlit run rossum_agent/app.py
"""

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
from rossum_agent.utils import (
    check_env_vars,
    clear_generated_files,
    get_generated_files,
    get_generated_files_with_metadata,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

# Generate beep and encode as base64 data URL
_beep_wav = generate_beep_wav(frequency=440, duration=0.33)
_beep_b64 = base64.b64encode(_beep_wav).decode("ascii")
BEEP_HTML = f'<audio src="data:audio/wav;base64,{_beep_b64}" autoplay></audio>'

LOGO_PATH = pathlib.Path(__file__).parent / "assets" / "Primary_light_logo.png"

# Configure logging with Elasticsearch integration
setup_logging(app_name="rossum-agent", log_level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


# Page config - must be first Streamlit command and at module level
st.set_page_config(page_title="Rossum Agent", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")


def main() -> None:  # noqa: C901
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

        if missing_vars := check_env_vars():
            st.markdown("---")
            st.error("❌ Missing environment variables:")
            for var, desc in missing_vars:
                if var not in ["ROSSUM_API_TOKEN", "ROSSUM_API_BASE_URL"]:
                    st.code(f"export {var}=<value>")
                    st.caption(desc)
            if any(var not in ["ROSSUM_API_TOKEN", "ROSSUM_API_BASE_URL"] for var, _ in missing_vars):
                st.stop()
            st.markdown("---")

        # Quick actions
        st.subheader("Quick Actions")
        if st.button("🔄 Reset Conversation"):
            st.session_state.messages = []
            if "agent" in st.session_state:
                del st.session_state.agent
            clear_generated_files()
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

    # Stop if credentials not saved
    if not st.session_state.credentials_saved:
        st.info("👈 Please enter your Rossum API credentials in the sidebar to continue")
        st.stop()

    # Main content
    st.title("Rossum Agent")
    st.markdown("Agent for automating Rossum setup processes.")

    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "agent" not in st.session_state:
        with st.spinner("Initializing agent..."):
            try:
                logger.info("Initializing Rossum agent")
                st.session_state.agent = create_agent(stream_outputs=False)
                logger.info("Agent initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize agent: {e}", exc_info=True)
                st.error(f"Failed to initialize agent: {e}")
                st.stop()

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Process user input
    if prompt := st.chat_input("Enter your instruction..."):
        logger.info(f"User prompt received: {prompt[:100]}...")  # Log first 100 chars
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
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
