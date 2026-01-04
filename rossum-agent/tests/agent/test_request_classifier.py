"""Tests for rossum_agent.agent.request_classifier module."""

from __future__ import annotations

from unittest.mock import MagicMock

from rossum_agent.agent.request_classifier import (
    CLASSIFIER_MODEL_ID,
    RequestScope,
    classify_request,
    generate_rejection_response,
)


class TestClassifyRequest:
    """Test the classify_request function."""

    def test_in_scope_request(self) -> None:
        """Test that Rossum-related requests are classified as in-scope."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="IN_SCOPE")]
        mock_client.messages.create.return_value = mock_response

        result = classify_request(mock_client, "How do I configure a hook?")

        assert result.scope == RequestScope.IN_SCOPE
        assert result.raw_response == "IN_SCOPE"
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == CLASSIFIER_MODEL_ID
        assert call_kwargs["max_tokens"] == 10

    def test_out_of_scope_request(self) -> None:
        """Test that non-Rossum requests are classified as out-of-scope."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="OUT_OF_SCOPE")]
        mock_client.messages.create.return_value = mock_response

        result = classify_request(mock_client, "What's the weather today?")

        assert result.scope == RequestScope.OUT_OF_SCOPE
        assert result.raw_response == "OUT_OF_SCOPE"

    def test_handles_lowercase_response(self) -> None:
        """Test that lowercase responses are handled correctly."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="out_of_scope")]
        mock_client.messages.create.return_value = mock_response

        result = classify_request(mock_client, "Make me a pie chart")

        assert result.scope == RequestScope.OUT_OF_SCOPE

    def test_handles_extra_text_in_response(self) -> None:
        """Test that extra text around the classification is handled."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="The answer is IN_SCOPE because...")]
        mock_client.messages.create.return_value = mock_response

        result = classify_request(mock_client, "List all hooks")

        assert result.scope == RequestScope.IN_SCOPE

    def test_defaults_to_in_scope_on_error(self) -> None:
        """Test that API errors default to in-scope to avoid blocking valid requests."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")

        result = classify_request(mock_client, "Some request")

        assert result.scope == RequestScope.IN_SCOPE
        assert "error" in result.raw_response

    def test_defaults_to_in_scope_on_empty_response(self) -> None:
        """Test that empty responses default to in-scope."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = []
        mock_client.messages.create.return_value = mock_response

        result = classify_request(mock_client, "Some request")

        assert result.scope == RequestScope.IN_SCOPE

    def test_prompt_format(self) -> None:
        """Test that the prompt is formatted correctly with the user message."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="IN_SCOPE")]
        mock_client.messages.create.return_value = mock_response

        classify_request(mock_client, "Debug my hook")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        message_content = call_kwargs["messages"][0]["content"]
        assert "Debug my hook" in message_content
        assert "IN_SCOPE or OUT_OF_SCOPE" in message_content


class TestGenerateRejectionResponse:
    """Test the dynamic rejection response generation."""

    def test_generates_response_from_model(self) -> None:
        """Test that rejection response is generated via model."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="I focus on Rossum platform. Can I help with hooks?")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response

        result = generate_rejection_response(mock_client, "What's the weather?")

        assert result.response == "I focus on Rossum platform. Can I help with hooks?"
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        mock_client.messages.create.assert_called_once()

    def test_falls_back_on_error(self) -> None:
        """Test fallback response when model fails."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")

        result = generate_rejection_response(mock_client, "Some request")

        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert "rossum" in result.response.lower()
        assert "hooks" in result.response.lower()
        assert "queue" in result.response.lower()
