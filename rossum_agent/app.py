"""Rossum Streamlit App

Web interface for the Rossum Document Processing Agent using Streamlit.

Usage:
    streamlit run rossum_agent/app.py
"""

import logging
import os
import pathlib
import time

import streamlit as st

from rossum_agent.agent import create_agent
from rossum_agent.agent_logging import log_agent_result
from rossum_agent.utils import check_env_vars
from rossum_mcp.logging_config import setup_logging

# Configure logging with Elasticsearch integration
setup_logging(
    app_name="rossum-agent",
    log_level=os.getenv("LOG_LEVEL", "INFO"),
)
logger = logging.getLogger(__name__)


def load_logo() -> str | None:
    """Load and display Rossum logo."""
    logo_path = pathlib.Path(__file__).parent / "assets" / "Primary_light_logo.png"
    return str(logo_path) if logo_path.exists() else None


# Page config - must be first Streamlit command and at module level
st.set_page_config(
    page_title="Rossum AI Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:  # noqa: C901
    # Initialize credentials in session state
    if "rossum_api_token" not in st.session_state:
        st.session_state.rossum_api_token = os.getenv("ROSSUM_API_TOKEN", "")
    if "rossum_api_base_url" not in st.session_state:
        st.session_state.rossum_api_base_url = os.getenv("ROSSUM_API_BASE_URL", "")
    if "mcp_mode" not in st.session_state:
        st.session_state.mcp_mode = os.getenv("ROSSUM_MCP_MODE", "read-only")
    if "credentials_saved" not in st.session_state:
        st.session_state.credentials_saved = bool(
            st.session_state.rossum_api_token and st.session_state.rossum_api_base_url
        )

    # Sidebar
    with st.sidebar:
        logo_path = load_logo()
        st.image(logo_path, width=200)

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
                    os.environ["ROSSUM_API_TOKEN"] = api_token
                    os.environ["ROSSUM_API_BASE_URL"] = api_base_url
                    if "agent" in st.session_state:
                        del st.session_state.agent
                    st.rerun()
                else:
                    st.error("Both fields are required")
        else:
            st.success("✅ Credentials configured")

            with st.expander("View Credentials"):
                st.text_input(
                    "API Base URL",
                    value=st.session_state.rossum_api_base_url,
                    disabled=True,
                )
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
            st.rerun()

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

        # Generate response
        with st.chat_message("assistant"):
            try:
                # Create placeholder for streaming output
                output_placeholder = st.empty()
                start_time = time.time()

                # Stream the response
                result_generator = st.session_state.agent.run(
                    prompt, return_full_result=True, stream=True, reset=False
                )

                for chunk in result_generator:
                    if hasattr(chunk, "model_output") and chunk.model_output:
                        # Format the output with proper markdown/code handling
                        display_text = chunk.model_output

                        # Check if this is not the final chunk
                        is_final_answer = hasattr(chunk, "is_final_answer") and chunk.is_final_answer
                        if not is_final_answer:
                            display_text += "\n\n🤖 _Agent is running..._"

                        output_placeholder.markdown(display_text, unsafe_allow_html=True)

                        # Log individual step to Elasticsearch
                        duration = time.time() - start_time
                        log_agent_result(chunk, prompt, duration)

                    result = chunk  # Keep the last chunk as final result

                # Save final output to chat history
                if hasattr(result, "output") and result.output:
                    duration = time.time() - start_time
                    output_placeholder.markdown(result.output, unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": result.output})

                    # Log complete result to Elasticsearch
                    log_agent_result(result, prompt, duration)
                    logger.info("Agent response generated successfully")

            except Exception as e:
                logger.error(f"Error processing user request: {e}", exc_info=True)
                error_msg = f"❌ Error: {e!s}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})


if __name__ == "__main__":
    main()
