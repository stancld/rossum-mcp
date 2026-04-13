"""Unit tests for message routes."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest
from rossum_agent.agent.models import FinalAnswerStep, ReasoningStep
from rossum_agent.api.models.schemas import StreamDoneEvent
from rossum_agent.api.routes.helpers import (
    SSE_KEEPALIVE_INTERVAL,
    generate_chat_summary,
    save_chat_history,
    with_sse_keepalive,
)
from rossum_agent.api.routes.messages import RESPONSE_HEADERS, _format_sse
from rossum_agent.api.routes.stream_adapter import (
    StreamState,
    build_finish_events,
    convert_agent_event,
)
from rossum_agent.chat_models import ChatData, ChatMetadata


class TestFormatSSE:
    def test_uses_data_lines_not_event_names(self):
        state = StreamState()
        events = convert_agent_event(FinalAnswerStep(step_number=1, final_answer="Hello"), state)

        for event in events:
            sse_line = _format_sse(event)
            assert sse_line.startswith("data: ")
            assert "event: " not in sse_line

    def test_response_headers_include_ai_sdk_protocol(self):
        assert RESPONSE_HEADERS["x-vercel-ai-ui-message-stream"] == "v1"

    def test_produces_finish_lifecycle(self):
        state = StreamState()
        finish_events = build_finish_events(state)
        assert finish_events[-1]["type"] == "finish"


class TestWithSSEKeepalive:
    @pytest.mark.asyncio
    async def test_forwards_events_without_delay(self):
        async def fast_events():
            yield ReasoningStep(step_number=1, reasoning="Thinking...")
            yield FinalAnswerStep(step_number=2, final_answer="Done!")

        results = []
        async for event, is_keepalive in with_sse_keepalive(fast_events()):
            results.append((event, is_keepalive))

        real_events = [event for event, is_keepalive in results if not is_keepalive]
        assert len(real_events) == 2
        assert isinstance(real_events[0], ReasoningStep)
        assert isinstance(real_events[1], FinalAnswerStep)

    @pytest.mark.asyncio
    async def test_emits_keepalive_during_pause(self):
        async def slow_events():
            yield ReasoningStep(step_number=1, reasoning="Thinking...")
            await asyncio.sleep(0.15)
            yield FinalAnswerStep(step_number=2, final_answer="Done!")

        results = []
        async for event, is_keepalive in with_sse_keepalive(slow_events(), interval=0.05):
            results.append((event, is_keepalive))

        real_events = [event for event, is_keepalive in results if not is_keepalive]
        assert len(real_events) == 2

        keepalive_events = [event for event, is_keepalive in results if is_keepalive]
        assert len(keepalive_events) >= 1

    @pytest.mark.asyncio
    async def test_empty_stream(self):
        async def no_events():
            return
            yield

        results = []
        async for event, is_keepalive in with_sse_keepalive(no_events()):
            results.append((event, is_keepalive))

        assert results == []

    @pytest.mark.asyncio
    async def test_keepalive_interval_is_reasonable(self):
        assert SSE_KEEPALIVE_INTERVAL < 60


class TestGenerateChatSummary:
    @pytest.mark.asyncio
    async def test_returns_summary_on_success(self):
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = "  User asked about deployments.  "
        mock_response.content = [mock_text_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("rossum_agent.api.routes.helpers.create_async_bedrock_client", return_value=mock_client):
            result = await generate_chat_summary("How do I deploy a queue?")

        assert result == "User asked about deployments."

    @pytest.mark.asyncio
    async def test_returns_none_when_no_text_block(self):
        mock_response = MagicMock()
        mock_response.content = []

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("rossum_agent.api.routes.helpers.create_async_bedrock_client", return_value=mock_client):
            result = await generate_chat_summary("What is Rossum?")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_api_error(self):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API unavailable"))

        with patch("rossum_agent.api.routes.helpers.create_async_bedrock_client", return_value=mock_client):
            result = await generate_chat_summary("Trigger an error")

        assert result is None

    @pytest.mark.asyncio
    async def test_includes_previous_summary_in_prompt(self):
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = "Schema deployment and hook configuration."
        mock_response.content = [mock_text_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("rossum_agent.api.routes.helpers.create_async_bedrock_client", return_value=mock_client):
            result = await generate_chat_summary("Now configure a hook", previous_summary="User deployed a schema")

        assert result == "Schema deployment and hook configuration."
        call_args = mock_client.messages.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        assert "User deployed a schema" in prompt
        assert "Now configure a hook" in prompt

    @pytest.mark.asyncio
    async def test_includes_url_context_in_prompt(self):
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = "Queue 123 schema help."
        mock_response.content = [mock_text_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("rossum_agent.api.routes.helpers.create_async_bedrock_client", return_value=mock_client):
            result = await generate_chat_summary(
                "Help me with this queue", url_context="Queue ID: 123, Page type: schema_settings"
            )

        assert result == "Queue 123 schema help."
        call_args = mock_client.messages.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        assert "Queue ID: 123" in prompt

    @pytest.mark.asyncio
    async def test_no_url_context_prefix_when_none(self):
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = "General help."
        mock_response.content = [mock_text_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("rossum_agent.api.routes.helpers.create_async_bedrock_client", return_value=mock_client):
            await generate_chat_summary("Help me")

        call_args = mock_client.messages.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        assert not prompt.startswith("Context:")


class TestSaveChatHistoryTokenTracking:
    """Tests for token usage accumulation in save_chat_history."""

    def _make_deps(self):
        """Create mock dependencies for save_chat_history."""

        chat_service = MagicMock()
        chat_service.save_messages.return_value = True
        agent_service = MagicMock()
        agent_service.build_updated_history.return_value = []
        credentials = MagicMock()
        credentials.user_id = "test_user"
        chat_data = ChatData(messages=[], metadata=ChatMetadata())
        return chat_service, agent_service, credentials, chat_data

    def test_accumulates_tokens_from_done_event(self):
        """Token counts from done_event are accumulated into chat metadata."""

        chat_service, agent_service, credentials, chat_data = self._make_deps()
        done_event = StreamDoneEvent(total_steps=3, input_tokens=1000, output_tokens=500)

        save_chat_history(
            chat_service=chat_service,
            agent_service=agent_service,
            credentials=credentials,
            chat_id="chat_1",
            chat_data=chat_data,
            history=[],
            user_prompt="hello",
            final_response="hi",
            images=None,
            documents=None,
            output_dir=None,
            memory=None,
            done_event=done_event,
        )

        assert chat_data.metadata.total_input_tokens == 1000
        assert chat_data.metadata.total_output_tokens == 500
        assert chat_data.metadata.total_steps == 3

    def test_accumulates_tokens_across_multiple_turns(self):
        """Token counts accumulate across multiple calls (multi-turn chats)."""

        chat_service, agent_service, credentials, chat_data = self._make_deps()

        for i in range(3):
            done_event = StreamDoneEvent(total_steps=2, input_tokens=100, output_tokens=50)
            save_chat_history(
                chat_service=chat_service,
                agent_service=agent_service,
                credentials=credentials,
                chat_id="chat_1",
                chat_data=chat_data,
                history=[],
                user_prompt=f"turn {i}",
                final_response=f"response {i}",
                images=None,
                documents=None,
                output_dir=None,
                memory=None,
                done_event=done_event,
            )

        assert chat_data.metadata.total_input_tokens == 300
        assert chat_data.metadata.total_output_tokens == 150
        assert chat_data.metadata.total_steps == 6

    def test_no_done_event_leaves_tokens_unchanged(self):
        """When done_event is None, token counts remain at zero."""

        chat_service, agent_service, credentials, chat_data = self._make_deps()

        save_chat_history(
            chat_service=chat_service,
            agent_service=agent_service,
            credentials=credentials,
            chat_id="chat_1",
            chat_data=chat_data,
            history=[],
            user_prompt="hello",
            final_response="hi",
            images=None,
            documents=None,
            output_dir=None,
            memory=None,
        )

        assert chat_data.metadata.total_input_tokens == 0
        assert chat_data.metadata.total_output_tokens == 0
        assert chat_data.metadata.total_steps == 0
