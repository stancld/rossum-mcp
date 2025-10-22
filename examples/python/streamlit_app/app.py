#!/usr/bin/env python3
"""Rossum Streamlit App

Web interface for the Rossum Document Processing Agent using Streamlit.

Usage:
    streamlit run examples/python/streamlit_app/app.py

Environment Variables:
    ROSSUM_API_TOKEN: Rossum API authentication token
    ROSSUM_API_BASE_URL: Rossum API base URL
    LLM_API_BASE_URL: LLM API endpoint URL
    LLM_MODEL_ID: (Optional) LLM model identifier
"""

import importlib.resources
import os
import sys
from pathlib import Path

import streamlit as st
import yaml
from smolagents import CodeAgent, LiteLLMModel

from rossum_mcp.tools import parse_annotation_content, rossum_mcp_tool

# Add parent directory to path to import tools BEFORE importing them
sys.path.insert(0, str(Path(__file__).parent.parent))

from file_system_tools import get_file_info, list_files, read_file
from instructions import SYSTEM_PROMPT
from internal_tools import copy_queue_knowledge, retrieve_queue_status
from plot_tools import plot_data

# Constants
DEFAULT_LLM_MODEL = "openai/Qwen/Qwen3-Next-80B-A3B-Instruct-FP8"

# Page config - must be first Streamlit command and at module level
st.set_page_config(
    page_title="Rossum AI Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_logo() -> str | None:
    """Load and display Rossum logo."""
    logo_path = Path(__file__).parent / "assets" / "Primary_light_logo.png"
    return str(logo_path) if logo_path.exists() else None


def check_env_vars() -> list[tuple[str, str]]:
    """Check if required environment variables are set."""
    required_vars = {
        "ROSSUM_API_TOKEN": "Rossum API authentication token",
        "ROSSUM_API_BASE_URL": "Rossum API base URL",
        "LLM_API_BASE_URL": "LLM API endpoint URL",
    }

    missing = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing.append((var, description))

    return missing


def create_agent(stream_outputs: bool = False) -> CodeAgent:
    """Create and configure the Rossum agent with custom tools and instructions."""
    llm = LiteLLMModel(
        model_id=os.environ.get("LLM_MODEL_ID", DEFAULT_LLM_MODEL),
        api_base=os.environ["LLM_API_BASE_URL"],
        api_key="not_needed",
    )

    prompt_templates = yaml.safe_load(
        importlib.resources.files("smolagents.prompts").joinpath("code_agent.yaml").read_text()
    )

    prompt_templates["system_prompt"] += "\n" + SYSTEM_PROMPT

    return CodeAgent(
        tools=[
            rossum_mcp_tool,
            parse_annotation_content,
            list_files,
            read_file,
            get_file_info,
            plot_data,
            # Rossum internal tools
            copy_queue_knowledge,
            retrieve_queue_status,
        ],
        model=llm,
        prompt_templates=prompt_templates,
        additional_authorized_imports=[
            "collections",
            "datetime",
            "itertools",
            "json",
            "math",
            "os",
            "pathlib",
            "queue",
            "random",
            "re",
            "rossum_api.models.annotation",
            "stat",
            "statistics",
            "time",
            "unicodedata",
        ],
        stream_outputs=stream_outputs,
    )


def main() -> None:  # noqa: C901
    # Sidebar
    with st.sidebar:
        logo_path = load_logo()
        st.image(logo_path, width=200)

        if missing_vars := check_env_vars():
            st.markdown("---")
            st.error("❌ Missing environment variables:")
            for var, desc in missing_vars:
                st.code(f"export {var}=<value>")
                st.caption(desc)
            st.stop()
            st.markdown("---")

        # Quick actions
        st.subheader("Quick Actions")
        if st.button("🔄 Reset Conversation"):
            st.session_state.messages = []
            if "agent" in st.session_state:
                del st.session_state.agent
            st.rerun()

    # Main content
    st.title("Rossum Agent")
    st.markdown("Agent for automating Rossum setup processes.")

    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "agent" not in st.session_state:
        with st.spinner("Initializing agent..."):
            try:
                st.session_state.agent = create_agent(stream_outputs=False)
            except Exception as e:
                st.error(f"Failed to initialize agent: {e}")
                st.stop()

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Process user input
    if prompt := st.chat_input("Enter your instruction..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response
        with st.chat_message("assistant"):
            try:
                # Create placeholder for streaming output
                output_placeholder = st.empty()

                # Stream the response
                result_generator = st.session_state.agent.run(prompt, return_full_result=True, stream=True)

                for chunk in result_generator:
                    if hasattr(chunk, "model_output") and chunk.model_output:
                        # Format the output with proper markdown/code handling
                        display_text = chunk.model_output

                        # Check if this is not the final chunk
                        is_final_answer = hasattr(chunk, "is_final_answer") and chunk.is_final_answer
                        if not is_final_answer:
                            display_text += "\n\n🤖 _Agent is running..._"

                        output_placeholder.markdown(display_text, unsafe_allow_html=True)

                    result = chunk  # Keep the last chunk as final result

                # Save final output to chat history
                if hasattr(result, "output") and result.output:
                    output_placeholder.markdown(result.output, unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": result.output})

            except Exception as e:
                error_msg = f"❌ Error: {e!s}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})


if __name__ == "__main__":
    main()
