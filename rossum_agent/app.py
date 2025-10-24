"""Rossum Streamlit App

Web interface for the Rossum Document Processing Agent using Streamlit.

Usage:
    streamlit run rossum_agent/app.py
"""

import pathlib

import streamlit as st

from rossum_agent.agent import create_agent
from rossum_agent.utils import check_env_vars


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
