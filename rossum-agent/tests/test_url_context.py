"""Tests for URL context extraction."""

from __future__ import annotations

from rossum_agent.url_context import (
    RossumUrlContext,
    extract_url_context,
    format_context_for_prompt,
)


class TestExtractUrlContext:
    """Tests for extract_url_context function."""

    def test_extract_queue_id_from_settings_url(self):
        """Test extracting queue_id from a queue settings URL."""
        url = "https://review-ac-elis-frontend-11055.review.r8.lol/queues/3866808/settings/basic"
        context = extract_url_context(url)

        assert context.queue_id == 3866808
        assert context.page_type == "queue_settings"
        assert context.raw_url == url

    def test_extract_queue_id_from_all_documents_url(self):
        """Test extracting queue_id from all documents view."""
        url = "https://elis.rossum.ai/queues/12345/all"
        context = extract_url_context(url)

        assert context.queue_id == 12345
        assert context.page_type == "all_documents"

    def test_extract_hook_id(self):
        """Test extracting hook_id from hooks URL."""
        url = "https://elis.rossum.ai/hooks/11111"
        context = extract_url_context(url)

        assert context.hook_id == 11111

    def test_extract_hook_id_from_extensions(self):
        """Test extracting hook_id from extensions URL."""
        url = "https://elis.rossum.ai/extensions/22222"
        context = extract_url_context(url)

        assert context.hook_id == 22222

    def test_extract_engine_id(self):
        """Test extracting engine_id."""
        url = "https://elis.rossum.ai/engines/77777"
        context = extract_url_context(url)

        assert context.engine_id == 77777

    def test_empty_url(self):
        """Test handling of empty URL."""
        context = extract_url_context("")
        assert context.is_empty()

    def test_none_url(self):
        """Test handling of None URL."""
        context = extract_url_context(None)
        assert context.is_empty()

    def test_non_rossum_url(self):
        """Test handling of non-Rossum URL."""
        context = extract_url_context("https://example.com/some/path")
        assert context.is_empty()

    def test_page_type_schema_settings(self):
        """Test detecting schema settings page type."""
        url = "https://elis.rossum.ai/queues/12345/settings/schema"
        context = extract_url_context(url)

        assert context.queue_id == 12345
        assert context.page_type == "schema_settings"

    def test_page_type_hooks_settings(self):
        """Test detecting hooks settings page type."""
        url = "https://elis.rossum.ai/queues/12345/settings/hooks"
        context = extract_url_context(url)

        assert context.queue_id == 12345
        assert context.page_type == "hooks_settings"

    def test_extract_hook_id_from_my_extensions(self):
        """Test extracting hook_id from my-extensions URL."""
        url = "https://elis.rossum.ai/extensions/my-extensions/3"
        context = extract_url_context(url)

        assert context.hook_id == 3

    def test_extract_engine_id_from_automation_path(self):
        """Test extracting engine_id from automation/engines URL."""
        url = "https://elis.rossum.ai/automation/engines/39207/settings/basic"
        context = extract_url_context(url)

        assert context.engine_id == 39207
        assert context.page_type == "engine_settings"

    def test_extract_queue_from_documents_view_filtering(self):
        """Test extracting queue_id from documents view with filtering parameter."""
        url = (
            "https://review-ac-elis-frontend-11055.review.r8.lol/documents"
            "?filtering=%7B%22items%22%3A%5B%7B%22field%22%3A%22queue%22%2C%22value%22"
            "%3A%5B%223866808%22%5D%2C%22operator%22%3A%22isAnyOf%22%7D%5D%7D"
            "&level=queue&ordering=created_at&page=1&page_size=100&view=documents"
        )
        context = extract_url_context(url)

        assert context.queue_id == 3866808
        assert context.page_type == "documents_list"
        assert context.additional_context.get("view_level") == "queue"

    def test_extract_multiple_queues_from_documents_view(self):
        """Test extracting multiple queue_ids from documents view."""
        url = (
            "https://elis.rossum.ai/documents"
            "?filtering=%7B%22items%22%3A%5B%7B%22field%22%3A%22queue%22%2C%22value%22"
            "%3A%5B%22111%22%2C%22222%22%2C%22333%22%5D%7D%5D%7D"
        )
        context = extract_url_context(url)

        assert context.queue_id is None
        assert context.additional_context.get("queue_ids") == "111,222,333"
        assert context.page_type == "documents_list"

    def test_documents_view_without_filtering(self):
        """Test documents view URL without filtering parameter."""
        url = "https://elis.rossum.ai/documents"
        context = extract_url_context(url)

        assert context.queue_id is None
        assert context.page_type == "documents_list"


class TestRossumUrlContext:
    """Tests for RossumUrlContext dataclass."""

    def test_is_empty_when_no_ids(self):
        """Test is_empty returns True when no IDs are set."""
        context = RossumUrlContext()
        assert context.is_empty()

    def test_is_empty_false_when_queue_id_set(self):
        """Test is_empty returns False when queue_id is set."""
        context = RossumUrlContext(queue_id=12345)
        assert not context.is_empty()

    def test_to_context_string_single_id(self):
        """Test context string with single ID."""
        context = RossumUrlContext(queue_id=12345)
        assert context.to_context_string() == "Queue ID: 12345"

    def test_to_context_string_multiple_ids(self):
        """Test context string with multiple IDs."""
        context = RossumUrlContext(queue_id=12345, hook_id=67890)
        result = context.to_context_string()
        assert "Queue ID: 12345" in result
        assert "Hook ID: 67890" in result

    def test_to_context_string_with_page_type(self):
        """Test context string includes page type."""
        context = RossumUrlContext(queue_id=12345, page_type="queue_settings")
        result = context.to_context_string()
        assert "Queue ID: 12345" in result
        assert "Page type: queue_settings" in result

    def test_to_context_string_empty(self):
        """Test context string is empty when no context."""
        context = RossumUrlContext()
        assert context.to_context_string() == ""


class TestFormatContextForPrompt:
    """Tests for format_context_for_prompt function."""

    def test_format_with_context(self):
        """Test formatting context for prompt."""
        context = RossumUrlContext(queue_id=12345)
        result = format_context_for_prompt(context)

        assert "Current Context from URL" in result
        assert "Queue ID: 12345" in result
        assert "this queue" in result

    def test_format_empty_context(self):
        """Test formatting returns empty string for empty context."""
        context = RossumUrlContext()
        result = format_context_for_prompt(context)

        assert result == ""

    def test_format_includes_instructions(self):
        """Test that formatting includes usage instructions."""
        context = RossumUrlContext(queue_id=12345, hook_id=67890)
        result = format_context_for_prompt(context)

        assert "use the IDs from the context above" in result
