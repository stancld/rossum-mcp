"""Tests for rossum_agent.streamlit_app.app module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestRunAgentTurn:
    """Test run_agent_turn function."""

    @pytest.fixture
    def mock_dependencies(self):
        """Set up all mock dependencies for run_agent_turn."""
        with (
            patch("rossum_agent.streamlit_app.app.connect_mcp_server") as mock_connect,
            patch("rossum_agent.streamlit_app.app.create_agent") as mock_create_agent,
            patch("rossum_agent.streamlit_app.app.set_mcp_connection") as mock_set_mcp,
            patch("rossum_agent.streamlit_app.app.get_system_prompt") as mock_get_prompt,
            patch("rossum_agent.streamlit_app.app.extract_url_context") as mock_extract_url,
            patch("rossum_agent.streamlit_app.app.format_context_for_prompt") as mock_format_context,
        ):
            mock_context = MagicMock()
            mock_context.is_empty.return_value = True

            mock_extract_url.return_value = mock_context
            mock_get_prompt.return_value = "System prompt"
            mock_format_context.return_value = "Context section"

            mock_mcp_connection = AsyncMock()
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)

            mock_agent = MagicMock()
            mock_agent.add_user_message = MagicMock()
            mock_agent.add_assistant_message = MagicMock()

            async def mock_run(prompt):
                step = MagicMock()
                step.is_final = True
                step.final_answer = "Done"
                yield step

            mock_agent.run = mock_run
            mock_create_agent.return_value = mock_agent

            yield {
                "connect": mock_connect,
                "create_agent": mock_create_agent,
                "set_mcp_connection": mock_set_mcp,
                "get_system_prompt": mock_get_prompt,
                "extract_url_context": mock_extract_url,
                "format_context_for_prompt": mock_format_context,
                "mcp_connection": mock_mcp_connection,
                "agent": mock_agent,
                "url_context": mock_context,
            }

    @pytest.mark.asyncio
    async def test_run_agent_turn_basic(self, mock_dependencies):
        """Test basic run_agent_turn execution."""
        from rossum_agent.streamlit_app.app import run_agent_turn

        on_step = MagicMock()

        await run_agent_turn(
            rossum_api_token="token123",
            rossum_api_base_url="https://api.rossum.ai",
            mcp_mode="read-only",
            prompt="Hello",
            conversation_history=[],
            on_step=on_step,
        )

        on_step.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_agent_turn_connects_mcp_server(self, mock_dependencies):
        """Test that MCP server is connected with correct parameters."""
        from rossum_agent.streamlit_app.app import run_agent_turn

        await run_agent_turn(
            rossum_api_token="token123",
            rossum_api_base_url="https://api.rossum.ai",
            mcp_mode="read-write",
            prompt="Hello",
            conversation_history=[],
            on_step=MagicMock(),
        )

        mock_dependencies["connect"].assert_called_once_with(
            rossum_api_token="token123",
            rossum_api_base_url="https://api.rossum.ai",
            mcp_mode="read-write",
        )

    @pytest.mark.asyncio
    async def test_run_agent_turn_adds_conversation_history(self, mock_dependencies):
        """Test that conversation history is added to agent."""
        from rossum_agent.streamlit_app.app import run_agent_turn

        conversation_history = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First response"},
            {"role": "user", "content": "Second message"},
        ]

        await run_agent_turn(
            rossum_api_token="token123",
            rossum_api_base_url="https://api.rossum.ai",
            mcp_mode="read-only",
            prompt="Current message",
            conversation_history=conversation_history,
            on_step=MagicMock(),
        )

        agent = mock_dependencies["agent"]
        assert agent.add_user_message.call_count == 2
        assert agent.add_assistant_message.call_count == 1

    @pytest.mark.asyncio
    async def test_run_agent_turn_with_url_context(self, mock_dependencies):
        """Test that URL context is added to system prompt."""
        from rossum_agent.streamlit_app.app import run_agent_turn

        mock_dependencies["url_context"].is_empty.return_value = False
        mock_dependencies["format_context_for_prompt"].return_value = "URL context info"

        await run_agent_turn(
            rossum_api_token="token123",
            rossum_api_base_url="https://api.rossum.ai",
            mcp_mode="read-only",
            prompt="Hello",
            conversation_history=[],
            on_step=MagicMock(),
            rossum_url="https://app.rossum.ai/queue/123",
        )

        mock_dependencies["extract_url_context"].assert_called_once_with("https://app.rossum.ai/queue/123")
        mock_dependencies["format_context_for_prompt"].assert_called_once()

    @pytest.mark.asyncio
    async def test_run_agent_turn_without_url_context(self, mock_dependencies):
        """Test that format_context_for_prompt is not called when URL context is empty."""
        from rossum_agent.streamlit_app.app import run_agent_turn

        mock_dependencies["url_context"].is_empty.return_value = True

        await run_agent_turn(
            rossum_api_token="token123",
            rossum_api_base_url="https://api.rossum.ai",
            mcp_mode="read-only",
            prompt="Hello",
            conversation_history=[],
            on_step=MagicMock(),
        )

        mock_dependencies["format_context_for_prompt"].assert_not_called()

    @pytest.mark.asyncio
    async def test_run_agent_turn_calls_on_step_for_each_step(self, mock_dependencies):
        """Test that on_step callback is called for each agent step."""
        from rossum_agent.streamlit_app.app import run_agent_turn

        step1 = MagicMock()
        step1.is_final = False
        step2 = MagicMock()
        step2.is_final = True

        async def mock_run(prompt):
            yield step1
            yield step2

        mock_dependencies["agent"].run = mock_run

        on_step = MagicMock()

        await run_agent_turn(
            rossum_api_token="token123",
            rossum_api_base_url="https://api.rossum.ai",
            mcp_mode="read-only",
            prompt="Hello",
            conversation_history=[],
            on_step=on_step,
        )

        assert on_step.call_count == 2
        on_step.assert_any_call(step1)
        on_step.assert_any_call(step2)


class TestAppHelpers:
    """Test helper functions and constants in app module."""

    def test_beep_html_contains_audio_tag(self):
        """Test that BEEP_HTML constant contains audio element."""
        from rossum_agent.streamlit_app.app import BEEP_HTML

        assert "<audio" in BEEP_HTML
        assert "autoplay" in BEEP_HTML
        assert "data:audio/wav;base64," in BEEP_HTML

    def test_logo_path_exists(self):
        """Test that LOGO_PATH points to existing file."""
        from rossum_agent.streamlit_app.app import LOGO_PATH

        assert LOGO_PATH.exists()
        assert LOGO_PATH.suffix == ".png"


class MockSessionState:
    """Mock class for Streamlit session_state that supports both dict and attribute access."""

    def __init__(self):
        self._data = {}

    def __contains__(self, key):
        return key in self._data

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __getattr__(self, key):
        if key.startswith("_"):
            return object.__getattribute__(self, key)
        try:
            return self._data[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        if key.startswith("_"):
            object.__setattr__(self, key, value)
        else:
            self._data[key] = value

    def __delitem__(self, key):
        del self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)


class TestMainFunction:
    """Test main function initialization logic."""

    @pytest.fixture
    def mock_streamlit(self):
        """Create comprehensive streamlit mock."""
        with patch("rossum_agent.streamlit_app.app.st") as mock_st:
            mock_st.session_state = MockSessionState()
            mock_st.query_params = {}
            mock_st.context = MagicMock()
            mock_st.context.headers = {}
            mock_st.sidebar = MagicMock()
            mock_st.sidebar.__enter__ = MagicMock(return_value=mock_st.sidebar)
            mock_st.sidebar.__exit__ = MagicMock(return_value=None)
            mock_st.sidebar.divider = MagicMock()
            mock_st.sidebar.caption = MagicMock()
            mock_st.chat_message = MagicMock()
            mock_st.chat_message.return_value.__enter__ = MagicMock()
            mock_st.chat_message.return_value.__exit__ = MagicMock()
            mock_st.chat_input = MagicMock(return_value=None)
            mock_st.title = MagicMock()
            mock_st.markdown = MagicMock()
            mock_st.image = MagicMock()
            mock_st.subheader = MagicMock()
            mock_st.warning = MagicMock()
            mock_st.info = MagicMock()
            mock_st.error = MagicMock()
            mock_st.text_input = MagicMock(return_value="")
            mock_st.button = MagicMock(return_value=False)
            mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock()])
            mock_st.popover = MagicMock()
            mock_st.popover.return_value.__enter__ = MagicMock()
            mock_st.popover.return_value.__exit__ = MagicMock()
            mock_st.file_uploader = MagicMock(return_value=None)
            mock_st.download_button = MagicMock()
            mock_st.radio = MagicMock(return_value="read-only")
            mock_st.toggle = MagicMock(return_value=False)
            mock_st.rerun = MagicMock()
            mock_st.expander = MagicMock()
            mock_st.expander.return_value.__enter__ = MagicMock()
            mock_st.expander.return_value.__exit__ = MagicMock()
            mock_st.write = MagicMock()
            mock_st.text = MagicMock()
            yield mock_st

    @pytest.fixture
    def mock_dependencies(self, mock_streamlit):
        """Set up mock dependencies for main function."""
        with (
            patch("rossum_agent.streamlit_app.app.RedisStorage") as mock_redis,
            patch("rossum_agent.streamlit_app.app.generate_chat_id") as mock_gen_chat,
            patch("rossum_agent.streamlit_app.app.create_session_output_dir") as mock_create_dir,
            patch("rossum_agent.streamlit_app.app.set_session_output_dir"),
            patch("rossum_agent.streamlit_app.app.set_output_dir"),
            patch("rossum_agent.streamlit_app.app.get_generated_files") as mock_get_files,
            patch("rossum_agent.streamlit_app.app.get_generated_files_with_metadata") as mock_get_meta,
            patch("rossum_agent.streamlit_app.app.render_chat_history"),
            patch("rossum_agent.streamlit_app.app.detect_user_id") as mock_detect_user,
            patch("rossum_agent.streamlit_app.app.normalize_user_id") as mock_norm_user,
            patch.dict("os.environ", {}, clear=True),
        ):
            mock_redis_instance = MagicMock()
            mock_redis_instance.is_connected.return_value = False
            mock_redis_instance.load_chat.return_value = None
            mock_redis.return_value = mock_redis_instance

            mock_gen_chat.return_value = "chat-test-123"
            mock_create_dir.return_value = "/tmp/test_output"
            mock_get_files.return_value = []
            mock_get_meta.return_value = {}
            mock_detect_user.return_value = "test-user"
            mock_norm_user.return_value = "test-user"

            yield {
                "redis": mock_redis,
                "redis_instance": mock_redis_instance,
                "generate_chat_id": mock_gen_chat,
                "create_session_output_dir": mock_create_dir,
                "st": mock_streamlit,
                "detect_user_id": mock_detect_user,
                "normalize_user_id": mock_norm_user,
            }

    def test_main_initializes_session_state(self, mock_dependencies):
        """Test that main initializes required session state variables."""
        from rossum_agent.streamlit_app.app import main

        st = mock_dependencies["st"]
        main()

        assert "user_id" in st.session_state
        assert "redis_storage" in st.session_state
        assert "chat_id" in st.session_state
        assert "output_dir" in st.session_state
        assert "messages" in st.session_state
        assert "mcp_mode" in st.session_state
        assert "uploaded_images" in st.session_state
        assert "uploader_key_counter" in st.session_state

    def test_main_generates_new_chat_id(self, mock_dependencies):
        """Test that main generates new chat ID when none exists."""
        from rossum_agent.streamlit_app.app import main

        st = mock_dependencies["st"]
        main()

        assert st.session_state["chat_id"] == "chat-test-123"
        assert st.query_params["chat_id"] == "chat-test-123"

    def test_main_detects_user_from_jwt(self, mock_dependencies):
        """Test that main detects user ID from JWT headers."""
        from rossum_agent.streamlit_app.app import main

        st = mock_dependencies["st"]
        st.context.headers = {"Teleport-Jwt-Assertion": "jwt-token-here"}

        main()

        mock_dependencies["detect_user_id"].assert_called_once_with(jwt_token="jwt-token-here")

    def test_main_enables_user_isolation_with_jwt_config(self, mock_dependencies):
        """Test that user isolation is enabled when JWT config is present."""
        from rossum_agent.streamlit_app.app import main

        with patch.dict("os.environ", {"TELEPORT_JWT_JWKS_URL": "https://example.com/jwks"}):
            st = mock_dependencies["st"]
            main()

            assert st.session_state["user_isolation_enabled"] is True

    def test_main_disables_user_isolation_without_jwt_config(self, mock_dependencies):
        """Test that user isolation is disabled when JWT config is absent."""
        from rossum_agent.streamlit_app.app import main

        st = mock_dependencies["st"]
        main()

        assert st.session_state["user_isolation_enabled"] is False

    def test_main_shows_credentials_warning_when_not_saved(self, mock_dependencies):
        """Test that credentials warning is shown when not saved."""
        from rossum_agent.streamlit_app.app import main

        st = mock_dependencies["st"]
        main()

        st.warning.assert_called()

    def test_main_disables_chat_input_without_credentials(self, mock_dependencies):
        """Test that chat input is disabled without credentials."""
        from rossum_agent.streamlit_app.app import main

        st = mock_dependencies["st"]
        main()

        st.chat_input.assert_called_with(
            "👈 Please enter your Rossum API credentials in the sidebar",
            disabled=True,
        )

    def test_main_loads_messages_from_redis(self, mock_dependencies):
        """Test that messages are loaded from Redis when connected."""
        from rossum_agent.streamlit_app.app import main

        redis_instance = mock_dependencies["redis_instance"]
        redis_instance.is_connected.return_value = True
        chat_data = MagicMock()
        chat_data.messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        redis_instance.load_chat.return_value = chat_data

        st = mock_dependencies["st"]
        main()

        assert st.session_state["messages"] == chat_data.messages

    def test_main_initializes_empty_messages_when_redis_empty(self, mock_dependencies):
        """Test that empty messages are initialized when Redis has no data."""
        from rossum_agent.streamlit_app.app import main

        redis_instance = mock_dependencies["redis_instance"]
        redis_instance.is_connected.return_value = True
        redis_instance.load_chat.return_value = None

        st = mock_dependencies["st"]
        main()

        assert st.session_state["messages"] == []

    def test_main_renders_title_and_description(self, mock_dependencies):
        """Test that title and description are rendered."""
        from rossum_agent.streamlit_app.app import main

        st = mock_dependencies["st"]
        main()

        st.title.assert_called_with("Rossum Agent")
        st.markdown.assert_any_call("Test-bed agent for automating Rossum setup processes.")

    def test_main_renders_logo(self, mock_dependencies):
        """Test that logo is rendered in sidebar."""
        from rossum_agent.streamlit_app.app import main

        st = mock_dependencies["st"]
        main()

        st.image.assert_called()

    def test_main_reads_debug_credentials_from_env(self, mock_dependencies):
        """Test that credentials are read from env in debug mode."""
        from rossum_agent.streamlit_app.app import main

        with patch.dict(
            "os.environ",
            {
                "DEBUG": "true",
                "ROSSUM_API_TOKEN": "debug-token",
                "ROSSUM_API_BASE_URL": "https://debug.rossum.ai",
            },
        ):
            st = mock_dependencies["st"]
            main()

            assert st.session_state["rossum_api_token"] == "debug-token"
            assert st.session_state["rossum_api_base_url"] == "https://debug.rossum.ai"
            assert st.session_state["credentials_saved"] is True

    def test_main_disables_read_write_mode_from_env(self, mock_dependencies):
        """Test that read-write mode can be disabled via env var."""
        from rossum_agent.streamlit_app.app import main

        with patch.dict("os.environ", {"ROSSUM_DISABLE_READ_WRITE": "true"}):
            st = mock_dependencies["st"]
            main()

            assert st.session_state["read_write_disabled"] is True
