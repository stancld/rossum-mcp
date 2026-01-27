"""Tests for rossum_agent.streamlit_app.app module."""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rossum_agent.streamlit_app.app import (
    BEEP_HTML,
    LOGO_PATH,
    _build_agent_prompt,
    _initialize_chat_id,
    _initialize_session_defaults,
    _initialize_user_and_storage,
    _load_messages_from_redis,
    _save_documents_to_output_dir,
    _save_response_to_redis,
    main,
    run_agent_turn,
)


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
        assert "<audio" in BEEP_HTML
        assert "autoplay" in BEEP_HTML
        assert "data:audio/wav;base64," in BEEP_HTML

    def test_logo_path_exists(self):
        """Test that LOGO_PATH points to existing file."""
        assert LOGO_PATH.exists()
        assert LOGO_PATH.suffix == ".png"


class TestInitializeUserAndStorage:
    """Test _initialize_user_and_storage function."""

    @pytest.fixture
    def mock_streamlit(self):
        """Create streamlit mock."""
        with patch("rossum_agent.streamlit_app.app.st") as mock_st:
            mock_st.session_state = MockSessionState()
            mock_st.context = MagicMock()
            mock_st.context.headers = {}
            yield mock_st

    @pytest.fixture
    def mock_deps(self, mock_streamlit):
        """Set up mock dependencies."""
        with (
            patch("rossum_agent.streamlit_app.app.RedisStorage") as mock_redis,
            patch("rossum_agent.streamlit_app.app.get_user_from_jwt") as mock_detect,
            patch("rossum_agent.streamlit_app.app.normalize_user_id") as mock_norm,
            patch.dict("os.environ", {}, clear=True),
        ):
            mock_redis_instance = MagicMock()
            mock_redis.return_value = mock_redis_instance
            mock_detect.return_value = "test-user"
            mock_norm.return_value = "test-user"
            yield {"st": mock_streamlit, "redis": mock_redis, "detect": mock_detect, "norm": mock_norm}

    def test_initializes_user_id(self, mock_deps):
        """Test user ID is initialized."""
        _initialize_user_and_storage()

        assert mock_deps["st"].session_state["user_id"] == "test-user"

    def test_initializes_redis_storage(self, mock_deps):
        """Test Redis storage is initialized."""
        _initialize_user_and_storage()

        assert "redis_storage" in mock_deps["st"].session_state

    def test_enables_user_isolation_with_jwt_url(self, mock_deps):
        """Test user isolation is enabled when JWT URL is set."""
        with patch.dict("os.environ", {"TELEPORT_JWT_JWKS_URL": "https://example.com"}):
            _initialize_user_and_storage()

        assert mock_deps["st"].session_state["user_isolation_enabled"] is True


class TestInitializeChatId:
    """Test _initialize_chat_id function."""

    @pytest.fixture
    def mock_streamlit(self):
        """Create streamlit mock."""
        with patch("rossum_agent.streamlit_app.app.st") as mock_st:
            mock_st.session_state = MockSessionState()
            mock_st.query_params = {}
            yield mock_st

    @pytest.fixture
    def mock_deps(self, mock_streamlit):
        """Set up mock dependencies."""
        with (
            patch("rossum_agent.streamlit_app.app.generate_chat_id") as mock_gen,
            patch("rossum_agent.streamlit_app.app.is_valid_chat_id") as mock_valid,
        ):
            mock_gen.return_value = "chat_20231201120000_abc123def456"
            mock_valid.return_value = False
            yield {"st": mock_streamlit, "gen": mock_gen, "valid": mock_valid}

    def test_generates_new_chat_id_when_none_exists(self, mock_deps):
        """Test new chat ID is generated when none exists."""
        _initialize_chat_id()

        assert mock_deps["st"].session_state["chat_id"] == "chat_20231201120000_abc123def456"
        assert mock_deps["st"].query_params["chat_id"] == "chat_20231201120000_abc123def456"

    def test_loads_chat_id_from_url(self, mock_deps):
        """Test chat ID is loaded from URL when valid."""
        mock_deps["st"].query_params["chat_id"] = "chat_20231201120000_validchatid1"
        mock_deps["valid"].return_value = True

        _initialize_chat_id()

        assert mock_deps["st"].session_state["chat_id"] == "chat_20231201120000_validchatid1"


class TestInitializeSessionDefaults:
    """Test _initialize_session_defaults function."""

    @pytest.fixture
    def mock_streamlit(self):
        """Create streamlit mock."""
        with patch("rossum_agent.streamlit_app.app.st") as mock_st:
            mock_st.session_state = MockSessionState()
            yield mock_st

    @pytest.fixture
    def mock_deps(self, mock_streamlit):
        """Set up mock dependencies."""
        with (
            patch("rossum_agent.streamlit_app.app.create_session_output_dir") as mock_create,
            patch("rossum_agent.streamlit_app.app.set_session_output_dir"),
            patch("rossum_agent.streamlit_app.app.set_output_dir"),
            patch("rossum_agent.streamlit_app.app.RossumUrlContext") as mock_ctx,
            patch.dict("os.environ", {}, clear=True),
        ):
            mock_create.return_value = Path(tempfile.mkdtemp())
            mock_ctx.return_value = MagicMock()
            yield {"st": mock_streamlit, "create": mock_create, "ctx": mock_ctx}

    def test_initializes_output_dir(self, mock_deps):
        """Test output directory is initialized."""
        _initialize_session_defaults()

        assert "output_dir" in mock_deps["st"].session_state

    def test_initializes_mcp_mode(self, mock_deps):
        """Test MCP mode defaults to read-write."""
        _initialize_session_defaults()

        assert mock_deps["st"].session_state["mcp_mode"] == "read-write"

    def test_initializes_uploaded_images(self, mock_deps):
        """Test uploaded images list is initialized."""
        _initialize_session_defaults()

        assert mock_deps["st"].session_state["uploaded_images"] == []

    def test_initializes_uploader_key_counter(self, mock_deps):
        """Test uploader key counter is initialized."""
        _initialize_session_defaults()

        assert mock_deps["st"].session_state["uploader_key_counter"] == 0


class TestLoadMessagesFromRedis:
    """Test _load_messages_from_redis function."""

    @pytest.fixture
    def mock_streamlit(self):
        """Create streamlit mock."""
        with patch("rossum_agent.streamlit_app.app.st") as mock_st:
            mock_st.session_state = MockSessionState()
            yield mock_st

    def test_skips_when_messages_already_exist(self, mock_streamlit):
        """Test loading is skipped when messages already exist."""
        mock_streamlit.session_state["messages"] = [{"role": "user", "content": "Hello"}]

        _load_messages_from_redis()

        assert mock_streamlit.session_state["messages"] == [{"role": "user", "content": "Hello"}]

    def test_initializes_empty_list_when_redis_not_connected(self, mock_streamlit):
        """Test empty list is initialized when Redis is not connected."""
        mock_redis = MagicMock()
        mock_redis.is_connected.return_value = False
        mock_streamlit.session_state["redis_storage"] = mock_redis

        _load_messages_from_redis()

        assert mock_streamlit.session_state["messages"] == []


class TestBuildAgentPrompt:
    """Test _build_agent_prompt function."""

    @pytest.fixture
    def mock_streamlit(self):
        """Create streamlit mock."""
        with patch("rossum_agent.streamlit_app.app.st") as mock_st:
            mock_st.session_state = MockSessionState()
            mock_st.session_state["uploaded_images"] = []
            yield mock_st

    def test_returns_string_when_no_images(self, mock_streamlit):
        """Test string prompt is returned when no images or documents."""
        result, num_images, num_documents = _build_agent_prompt("Hello agent", [], [])

        assert result == "Hello agent"
        assert num_images == 0
        assert num_documents == 0

    def test_returns_content_blocks_with_images(self, mock_streamlit):
        """Test content blocks are returned when images are present."""
        images = [{"media_type": "image/png", "data": "base64data", "name": "test.png"}]

        result, num_images, num_documents = _build_agent_prompt("Describe this", images, [])

        assert isinstance(result, list)
        assert num_images == 1
        assert num_documents == 0
        assert len(result) == 2
        assert result[0]["type"] == "image"
        assert result[1]["type"] == "text"

    def test_clears_uploaded_images_after_build(self, mock_streamlit):
        """Test uploaded images are cleared after building prompt."""
        mock_streamlit.session_state["uploaded_images"] = [
            {"media_type": "image/png", "data": "data", "name": "t.png"}
        ]
        mock_streamlit.session_state["uploaded_documents"] = []

        _build_agent_prompt("Test", mock_streamlit.session_state["uploaded_images"], [])

        assert mock_streamlit.session_state["uploaded_images"] == []


class TestSaveResponseToRedis:
    """Test _save_response_to_redis function."""

    @pytest.fixture
    def mock_streamlit(self):
        """Create streamlit mock."""
        with patch("rossum_agent.streamlit_app.app.st") as mock_st:
            mock_st.session_state = MockSessionState()
            yield mock_st

    @pytest.fixture
    def mock_deps(self, mock_streamlit):
        """Set up mock dependencies."""
        with (
            patch("rossum_agent.streamlit_app.app.get_commit_sha") as mock_sha,
            patch("rossum_agent.streamlit_app.app.ChatMetadata") as mock_meta,
        ):
            mock_sha.return_value = "abc123"
            yield {"st": mock_streamlit, "sha": mock_sha, "meta": mock_meta}

    def test_skips_when_redis_not_connected(self, mock_deps):
        """Test saving is skipped when Redis is not connected."""
        mock_redis = MagicMock()
        mock_redis.is_connected.return_value = False
        mock_deps["st"].session_state["redis_storage"] = mock_redis

        chat_response = MagicMock()

        _save_response_to_redis(chat_response)

        mock_redis.save_chat.assert_not_called()

    def test_saves_when_redis_connected(self, mock_deps):
        """Test response is saved when Redis is connected."""
        mock_redis = MagicMock()
        mock_redis.is_connected.return_value = True
        mock_deps["st"].session_state["redis_storage"] = mock_redis
        mock_deps["st"].session_state["chat_id"] = "test-chat"
        mock_deps["st"].session_state["messages"] = []
        mock_deps["st"].session_state["output_dir"] = tempfile.gettempdir()
        mock_deps["st"].session_state["user_isolation_enabled"] = False

        chat_response = MagicMock()
        chat_response.total_input_tokens = 100
        chat_response.total_output_tokens = 50
        chat_response.total_tool_calls = 2
        chat_response.total_steps = 3

        _save_response_to_redis(chat_response)

        mock_redis.save_chat.assert_called_once()

    def test_saves_with_user_isolation_enabled(self, mock_deps):
        """Test response is saved with user ID when isolation is enabled."""
        mock_redis = MagicMock()
        mock_redis.is_connected.return_value = True
        mock_deps["st"].session_state["redis_storage"] = mock_redis
        mock_deps["st"].session_state["chat_id"] = "test-chat"
        mock_deps["st"].session_state["messages"] = []
        mock_deps["st"].session_state["output_dir"] = tempfile.gettempdir()
        mock_deps["st"].session_state["user_isolation_enabled"] = True
        mock_deps["st"].session_state["user_id"] = "test-user"

        chat_response = MagicMock()
        chat_response.total_input_tokens = 100
        chat_response.total_output_tokens = 50
        chat_response.total_tool_calls = 2
        chat_response.total_steps = 3

        _save_response_to_redis(chat_response)

        mock_redis.save_chat.assert_called_once()


class TestLoadMessagesFromRedisWithSharedUser:
    """Test _load_messages_from_redis with shared user scenarios."""

    @pytest.fixture
    def mock_streamlit(self):
        """Create streamlit mock."""
        with patch("rossum_agent.streamlit_app.app.st") as mock_st:
            mock_st.session_state = MockSessionState()
            yield mock_st

    def test_loads_from_shared_user_when_isolation_enabled(self, mock_streamlit):
        """Test loading messages from shared user when isolation is enabled."""
        mock_redis = MagicMock()
        mock_redis.is_connected.return_value = True
        chat_data = MagicMock()
        chat_data.messages = [{"role": "user", "content": "Shared message"}]
        mock_redis.load_chat.return_value = chat_data

        mock_streamlit.session_state["redis_storage"] = mock_redis
        mock_streamlit.session_state["chat_id"] = "shared-chat"
        mock_streamlit.session_state["output_dir"] = Path(tempfile.gettempdir())
        mock_streamlit.session_state["user_isolation_enabled"] = True
        mock_streamlit.session_state["user_id"] = "current-user"
        mock_streamlit.session_state["shared_user_id"] = "original-owner"

        _load_messages_from_redis()

        assert mock_streamlit.session_state["messages"] == [{"role": "user", "content": "Shared message"}]
        mock_redis.load_chat.assert_called_once()

    def test_loads_own_messages_without_shared_user(self, mock_streamlit):
        """Test loading own messages when no shared_user_id."""
        mock_redis = MagicMock()
        mock_redis.is_connected.return_value = True
        mock_redis.load_chat.return_value = None

        mock_streamlit.session_state["redis_storage"] = mock_redis
        mock_streamlit.session_state["chat_id"] = "own-chat"
        mock_streamlit.session_state["output_dir"] = Path(tempfile.gettempdir())
        mock_streamlit.session_state["user_isolation_enabled"] = True
        mock_streamlit.session_state["user_id"] = "current-user"

        _load_messages_from_redis()

        assert mock_streamlit.session_state["messages"] == []


class TestInitializeChatIdFromUrl:
    """Test _initialize_chat_id with URL parameters."""

    @pytest.fixture
    def mock_streamlit(self):
        """Create streamlit mock."""
        with patch("rossum_agent.streamlit_app.app.st") as mock_st:
            mock_st.session_state = MockSessionState()
            mock_st.query_params = {}
            yield mock_st

    @pytest.fixture
    def mock_deps(self, mock_streamlit):
        """Set up mock dependencies."""
        with (
            patch("rossum_agent.streamlit_app.app.generate_chat_id") as mock_gen,
            patch("rossum_agent.streamlit_app.app.is_valid_chat_id") as mock_valid,
        ):
            mock_gen.return_value = "chat_20231201120000_abc123def456"
            yield {"st": mock_streamlit, "gen": mock_gen, "valid": mock_valid}

    def test_clears_session_on_chat_change(self, mock_deps):
        """Test session is cleared when chat ID changes via URL."""
        mock_deps["st"].session_state["chat_id"] = "old-chat-id"
        mock_deps["st"].session_state["messages"] = [{"role": "user", "content": "old"}]
        mock_deps["st"].session_state["output_dir"] = "/old/path"
        mock_deps["st"].session_state["uploaded_images"] = [{"data": "img"}]
        mock_deps["st"].session_state["uploader_key_counter"] = 5

        mock_deps["st"].query_params["chat_id"] = "chat_20231201120000_newchatid12"
        mock_deps["st"].query_params["user_id"] = "shared-owner"
        mock_deps["valid"].return_value = True

        _initialize_chat_id()

        assert mock_deps["st"].session_state["chat_id"] == "chat_20231201120000_newchatid12"
        assert mock_deps["st"].session_state["shared_user_id"] == "shared-owner"
        assert "messages" not in mock_deps["st"].session_state
        assert "output_dir" not in mock_deps["st"].session_state
        assert mock_deps["st"].session_state["uploaded_images"] == []
        assert mock_deps["st"].session_state["uploader_key_counter"] == 6


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
            patch("rossum_agent.streamlit_app.app.get_user_from_jwt") as mock_detect_user,
            patch("rossum_agent.streamlit_app.app.normalize_user_id") as mock_norm_user,
            patch.dict("os.environ", {}, clear=True),
        ):
            mock_redis_instance = MagicMock()
            mock_redis_instance.is_connected.return_value = False
            mock_redis_instance.load_chat.return_value = None
            mock_redis.return_value = mock_redis_instance

            mock_gen_chat.return_value = "chat-test-123"
            mock_create_dir.return_value = str(Path(tempfile.gettempdir()) / "test_output")
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
                "get_user_from_jwt": mock_detect_user,
                "normalize_user_id": mock_norm_user,
            }

    def test_main_initializes_session_state(self, mock_dependencies):
        """Test that main initializes required session state variables."""
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
        st = mock_dependencies["st"]
        main()

        assert st.session_state["chat_id"] == "chat-test-123"
        assert st.query_params["chat_id"] == "chat-test-123"

    def test_main_detects_user_from_jwt(self, mock_dependencies):
        """Test that main detects user ID from JWT headers."""
        st = mock_dependencies["st"]
        st.context.headers = {"Teleport-Jwt-Assertion": "jwt-token-here"}

        main()

        mock_dependencies["get_user_from_jwt"].assert_called_once_with("jwt-token-here")

    def test_main_enables_user_isolation_with_jwt_config(self, mock_dependencies):
        """Test that user isolation is enabled when JWT config is present."""
        with patch.dict("os.environ", {"TELEPORT_JWT_JWKS_URL": "https://example.com/jwks"}):
            st = mock_dependencies["st"]
            main()

            assert st.session_state["user_isolation_enabled"] is True

    def test_main_disables_user_isolation_without_jwt_config(self, mock_dependencies):
        """Test that user isolation is disabled when JWT config is absent."""
        st = mock_dependencies["st"]
        main()

        assert st.session_state["user_isolation_enabled"] is False

    def test_main_shows_credentials_warning_when_not_saved(self, mock_dependencies):
        """Test that credentials warning is shown when not saved."""
        st = mock_dependencies["st"]
        main()

        st.warning.assert_called()

    def test_main_disables_chat_input_without_credentials(self, mock_dependencies):
        """Test that chat input is disabled without credentials."""
        st = mock_dependencies["st"]
        main()

        st.chat_input.assert_called_with(
            "👈 Please enter your Rossum API credentials in the sidebar",
            disabled=True,
        )

    def test_main_loads_messages_from_redis(self, mock_dependencies):
        """Test that messages are loaded from Redis when connected."""
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
        redis_instance = mock_dependencies["redis_instance"]
        redis_instance.is_connected.return_value = True
        redis_instance.load_chat.return_value = None

        st = mock_dependencies["st"]
        main()

        assert st.session_state["messages"] == []

    def test_main_renders_title_and_description(self, mock_dependencies):
        """Test that title and description are rendered."""
        st = mock_dependencies["st"]
        main()

        st.title.assert_called_with("Rossum Agent")
        st.markdown.assert_any_call("Test-bed agent for automating Rossum setup processes.")

    def test_main_renders_logo(self, mock_dependencies):
        """Test that logo is rendered in sidebar."""
        st = mock_dependencies["st"]
        main()

        st.image.assert_called()

    def test_main_reads_debug_credentials_from_env(self, mock_dependencies):
        """Test that credentials are read from env in debug mode."""
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
        with patch.dict("os.environ", {"ROSSUM_DISABLE_READ_WRITE": "true"}):
            st = mock_dependencies["st"]
            main()

            assert st.session_state["read_write_disabled"] is True


class TestSaveDocumentsToOutputDir:
    """Test _save_documents_to_output_dir function."""

    @pytest.fixture
    def mock_streamlit(self):
        """Create streamlit mock."""
        with patch("rossum_agent.streamlit_app.app.st") as mock_st:
            mock_st.session_state = MockSessionState()
            yield mock_st

    def test_saves_document_to_output_dir(self, mock_streamlit):
        """Test that documents are saved correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            mock_streamlit.session_state["output_dir"] = output_dir

            test_content = b"test document content"
            encoded_content = base64.b64encode(test_content).decode("utf-8")
            documents = [{"name": "test.pdf", "data": encoded_content}]

            _save_documents_to_output_dir(documents)

            saved_file = output_dir / "test.pdf"
            assert saved_file.exists()
            assert saved_file.read_bytes() == test_content

    def test_saves_multiple_documents(self, mock_streamlit):
        """Test that multiple documents are saved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            mock_streamlit.session_state["output_dir"] = output_dir

            documents = [
                {"name": "doc1.pdf", "data": base64.b64encode(b"content1").decode()},
                {"name": "doc2.pdf", "data": base64.b64encode(b"content2").decode()},
            ]

            _save_documents_to_output_dir(documents)

            assert (output_dir / "doc1.pdf").exists()
            assert (output_dir / "doc2.pdf").exists()

    def test_handles_save_error_gracefully(self, mock_streamlit):
        """Test that save errors are logged but don't raise exceptions."""
        mock_streamlit.session_state["output_dir"] = Path("/nonexistent/path")

        documents = [{"name": "test.pdf", "data": base64.b64encode(b"content").decode()}]

        _save_documents_to_output_dir(documents)


class TestBuildAgentPromptWithDocuments:
    """Test _build_agent_prompt with documents."""

    @pytest.fixture
    def mock_streamlit(self):
        """Create streamlit mock."""
        with patch("rossum_agent.streamlit_app.app.st") as mock_st:
            mock_st.session_state = MockSessionState()
            mock_st.session_state["uploaded_images"] = []
            mock_st.session_state["uploaded_documents"] = []
            mock_st.session_state["output_dir"] = Path(tempfile.gettempdir())
            yield mock_st

    def test_returns_content_blocks_with_documents(self, mock_streamlit):
        """Test content blocks are returned when documents are present."""
        documents = [{"media_type": "application/pdf", "data": "base64data", "name": "test.pdf"}]

        result, num_images, num_documents = _build_agent_prompt("Process this document", [], documents)

        assert isinstance(result, list)
        assert num_images == 0
        assert num_documents == 1
        assert any(block.get("type") == "text" and "Uploaded documents" in block.get("text", "") for block in result)

    def test_returns_content_blocks_with_images_and_documents(self, mock_streamlit):
        """Test content blocks with both images and documents."""
        images = [{"media_type": "image/png", "data": "imgdata", "name": "img.png"}]
        documents = [{"media_type": "application/pdf", "data": "pdfdata", "name": "doc.pdf"}]

        result, num_images, num_documents = _build_agent_prompt("Process these", images, documents)

        assert isinstance(result, list)
        assert num_images == 1
        assert num_documents == 1

    def test_clears_uploaded_documents_after_build(self, mock_streamlit):
        """Test uploaded documents are cleared after building prompt."""
        mock_streamlit.session_state["uploaded_documents"] = [
            {"media_type": "application/pdf", "data": "data", "name": "t.pdf"}
        ]

        _build_agent_prompt("Test", [], mock_streamlit.session_state["uploaded_documents"])

        assert mock_streamlit.session_state["uploaded_documents"] == []


class TestInitializeChatIdWithDocuments:
    """Test _initialize_chat_id clearing uploaded_documents."""

    @pytest.fixture
    def mock_streamlit(self):
        """Create streamlit mock."""
        with patch("rossum_agent.streamlit_app.app.st") as mock_st:
            mock_st.session_state = MockSessionState()
            mock_st.query_params = {}
            yield mock_st

    @pytest.fixture
    def mock_deps(self, mock_streamlit):
        """Set up mock dependencies."""
        with (
            patch("rossum_agent.streamlit_app.app.generate_chat_id") as mock_gen,
            patch("rossum_agent.streamlit_app.app.is_valid_chat_id") as mock_valid,
        ):
            mock_gen.return_value = "chat_20231201120000_abc123def456"
            yield {"st": mock_streamlit, "gen": mock_gen, "valid": mock_valid}

    def test_clears_uploaded_documents_on_chat_change(self, mock_deps):
        """Test uploaded_documents is cleared when chat ID changes via URL."""
        mock_deps["st"].session_state["chat_id"] = "old-chat-id"
        mock_deps["st"].session_state["uploaded_documents"] = [{"name": "doc.pdf"}]

        mock_deps["st"].query_params["chat_id"] = "chat_20231201120000_newchatid12"
        mock_deps["valid"].return_value = True

        _initialize_chat_id()

        assert mock_deps["st"].session_state["uploaded_documents"] == []


class TestInitializeSessionDefaultsDocuments:
    """Test _initialize_session_defaults for uploaded_documents."""

    @pytest.fixture
    def mock_streamlit(self):
        """Create streamlit mock."""
        with patch("rossum_agent.streamlit_app.app.st") as mock_st:
            mock_st.session_state = MockSessionState()
            yield mock_st

    @pytest.fixture
    def mock_deps(self, mock_streamlit):
        """Set up mock dependencies."""
        with (
            patch("rossum_agent.streamlit_app.app.create_session_output_dir") as mock_create,
            patch("rossum_agent.streamlit_app.app.set_session_output_dir"),
            patch("rossum_agent.streamlit_app.app.set_output_dir"),
            patch("rossum_agent.streamlit_app.app.RossumUrlContext") as mock_ctx,
            patch.dict("os.environ", {}, clear=True),
        ):
            mock_create.return_value = Path(tempfile.mkdtemp())
            mock_ctx.return_value = MagicMock()
            yield {"st": mock_streamlit, "create": mock_create, "ctx": mock_ctx}

    def test_initializes_uploaded_documents(self, mock_deps):
        """Test uploaded documents list is initialized."""
        _initialize_session_defaults()

        assert mock_deps["st"].session_state["uploaded_documents"] == []
