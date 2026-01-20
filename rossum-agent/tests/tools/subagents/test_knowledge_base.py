"""Tests for rossum_agent.tools.subagents.knowledge_base module."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from ddgs.exceptions import DDGSException
from rossum_agent.bedrock_client import OPUS_MODEL_ID
from rossum_agent.tools.subagents.knowledge_base import (
    _KNOWLEDGE_BASE_DOMAIN,
    _MAX_SEARCH_RESULTS,
    _WEBPAGE_FETCH_TIMEOUT,
    WebSearchError,
    _fetch_webpage_content,
    _run_async,
    _search_and_analyze_knowledge_base,
    _search_knowledge_base,
    search_knowledge_base,
)


class TestConstants:
    """Test module constants."""

    def test_opus_model_id_is_set(self):
        """Test that OPUS_MODEL_ID constant is defined."""
        assert OPUS_MODEL_ID is not None
        assert isinstance(OPUS_MODEL_ID, str)
        assert "opus" in OPUS_MODEL_ID.lower()

    def test_knowledge_base_domain(self):
        """Test KNOWLEDGE_BASE_DOMAIN constant value."""
        assert _KNOWLEDGE_BASE_DOMAIN == "knowledge-base.rossum.ai"

    def test_max_search_results(self):
        """Test MAX_SEARCH_RESULTS constant value."""
        assert _MAX_SEARCH_RESULTS == 5

    def test_webpage_fetch_timeout(self):
        """Test WEBPAGE_FETCH_TIMEOUT constant value."""
        assert _WEBPAGE_FETCH_TIMEOUT == 30


class TestRunAsync:
    """Test _run_async helper function."""

    def test_runs_coroutine_from_sync_context(self):
        """Test that _run_async works when called from sync context."""

        async def simple_coro():
            return "success"

        result = _run_async(simple_coro())
        assert result == "success"

    @pytest.mark.asyncio
    async def test_runs_coroutine_from_async_context(self):
        """Test that _run_async works when called from within an async context."""

        async def simple_coro():
            return "success from nested"

        # This would fail with plain asyncio.run() - "cannot be called from a running event loop"
        result = _run_async(simple_coro())
        assert result == "success from nested"


class TestFetchWebpageContent:
    """Test _fetch_webpage_content function."""

    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        """Test successful webpage fetch via Jina Reader."""
        mock_response = MagicMock()
        mock_response.text = "# Sample Markdown Content\n\nThis is the page content."
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response

        result = await _fetch_webpage_content(mock_client, "https://knowledge-base.rossum.ai/docs/test")

        assert result == "# Sample Markdown Content\n\nThis is the page content."
        mock_client.get.assert_called_once_with(
            "https://r.jina.ai/https://knowledge-base.rossum.ai/docs/test",
            timeout=30,
        )

    @pytest.mark.asyncio
    async def test_fetch_truncates_long_content(self):
        """Test that content longer than 50000 chars is truncated."""
        long_content = "x" * 60000
        mock_response = MagicMock()
        mock_response.text = long_content
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response

        result = await _fetch_webpage_content(mock_client, "https://example.com")

        assert len(result) == 50000

    @pytest.mark.asyncio
    async def test_failed_fetch_returns_error_message(self):
        """Test that failed fetch returns error message."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.side_effect = httpx.HTTPError("Connection timed out")

        result = await _fetch_webpage_content(mock_client, "https://example.com/failing")

        assert "[Failed to fetch content:" in result
        assert "Connection timed out" in result


class TestSearchKnowledgeBase:
    """Test _search_knowledge_base function."""

    @pytest.mark.asyncio
    async def test_reports_searching_progress(self):
        """Test that searching status is reported before search starts."""
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = []
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=None)

        progress_calls: list = []

        def capture_progress(progress):
            progress_calls.append(progress)

        with (
            patch("rossum_agent.tools.subagents.knowledge_base.DDGS", return_value=mock_ddgs_instance),
            patch("rossum_agent.tools.subagents.knowledge_base.report_progress", side_effect=capture_progress),
        ):
            await _search_knowledge_base("test query")

            assert len(progress_calls) == 1
            assert progress_calls[0].tool_name == "search_knowledge_base"
            assert progress_calls[0].status == "searching"

    @pytest.mark.asyncio
    async def test_no_results_found(self):
        """Test search with no results found."""
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = []
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=None)

        with patch("rossum_agent.tools.subagents.knowledge_base.DDGS", return_value=mock_ddgs_instance):
            result = await _search_knowledge_base("nonexistent topic")

            assert result == []

    @pytest.mark.asyncio
    async def test_results_found(self):
        """Test search with results found."""
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = [
            {"title": "Document Splitting", "href": "https://knowledge-base.rossum.ai/docs/splitting"},
            {"title": "Other Result", "href": "https://other-site.com/page"},
        ]
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=None)

        async def mock_fetch(client, url):
            return "Page content here"

        with (
            patch("rossum_agent.tools.subagents.knowledge_base.DDGS", return_value=mock_ddgs_instance),
            patch(
                "rossum_agent.tools.subagents.knowledge_base._fetch_webpage_content",
                side_effect=mock_fetch,
            ),
        ):
            result = await _search_knowledge_base("document splitting")

            assert len(result) == 1
            assert result[0]["title"] == "Document Splitting"
            assert result[0]["content"] == "Page content here"

    def test_search_exception_raises_web_search_error(self):
        """Test that DDGSException is converted to WebSearchError."""
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.side_effect = DDGSException("Rate limit exceeded")
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=None)

        with patch("rossum_agent.tools.subagents.knowledge_base.DDGS", return_value=mock_ddgs_instance):
            with pytest.raises(WebSearchError, match="Rate limit exceeded"):
                search_knowledge_base("test query")

    @pytest.mark.asyncio
    async def test_filters_only_knowledge_base_domain_results(self):
        """Test that only results from knowledge-base.rossum.ai are included."""
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = [
            {"title": "External", "href": "https://external-site.com/page"},
            {"title": "KB Page 1", "href": "https://knowledge-base.rossum.ai/docs/page1"},
            {"title": "KB Page 2", "href": "https://knowledge-base.rossum.ai/docs/page2"},
            {"title": "KB Page 3", "href": "https://knowledge-base.rossum.ai/docs/page3"},
        ]
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=None)

        fetch_call_count = 0

        async def mock_fetch(client, url):
            nonlocal fetch_call_count
            fetch_call_count += 1
            return "Content"

        with (
            patch("rossum_agent.tools.subagents.knowledge_base.DDGS", return_value=mock_ddgs_instance),
            patch(
                "rossum_agent.tools.subagents.knowledge_base._fetch_webpage_content",
                side_effect=mock_fetch,
            ),
        ):
            result = await _search_knowledge_base("test")

            assert len(result) == 2
            assert fetch_call_count == 2

    @pytest.mark.asyncio
    async def test_handles_partial_fetch_failures(self):
        """Test that partial fetch failures don't break the entire search."""
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = [
            {"title": "KB Page 1", "href": "https://knowledge-base.rossum.ai/docs/page1"},
            {"title": "KB Page 2", "href": "https://knowledge-base.rossum.ai/docs/page2"},
        ]
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=None)

        call_count = 0

        async def mock_fetch(client, url):
            nonlocal call_count
            call_count += 1
            if "page1" in url:
                raise RuntimeError("Simulated network failure")
            return "Content for page 2"

        with (
            patch("rossum_agent.tools.subagents.knowledge_base.DDGS", return_value=mock_ddgs_instance),
            patch(
                "rossum_agent.tools.subagents.knowledge_base._fetch_webpage_content",
                side_effect=mock_fetch,
            ),
        ):
            result = await _search_knowledge_base("test")

            # Both fetches were attempted
            assert call_count == 2
            # Both results returned, but first one has error message
            assert len(result) == 2
            assert "[Failed to fetch content:" in result[0]["content"]
            assert result[1]["content"] == "Content for page 2"


class TestCallOpusForWebSearchAnalysis:
    """Test _call_opus_for_web_search_analysis function."""

    def test_reports_analyzing_progress(self):
        """Test that analyzing status is reported before Opus analysis starts."""
        from rossum_agent.tools.subagents.knowledge_base import _call_opus_for_web_search_analysis

        progress_calls: list = []

        def capture_progress(progress):
            progress_calls.append(progress)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Analysis result")]

        with (
            patch("rossum_agent.tools.subagents.knowledge_base.create_bedrock_client") as mock_client,
            patch("rossum_agent.tools.subagents.knowledge_base.report_progress", side_effect=capture_progress),
            patch("rossum_agent.tools.subagents.knowledge_base.report_text"),
        ):
            mock_client.return_value.messages.create.return_value = mock_response
            _call_opus_for_web_search_analysis("test query", "search results")

            assert len(progress_calls) == 2
            assert progress_calls[0].tool_name == "search_knowledge_base"
            assert progress_calls[0].status == "analyzing"
            assert progress_calls[1].status == "completed"


class TestSearchAndAnalyzeKnowledgeBase:
    """Test _search_and_analyze_knowledge_base function."""

    @pytest.mark.asyncio
    async def test_no_results_found(self):
        """Test search with no results found."""

        async def mock_search(query):
            return []

        with patch(
            "rossum_agent.tools.subagents.knowledge_base._search_knowledge_base",
            side_effect=mock_search,
        ):
            result = await _search_and_analyze_knowledge_base("nonexistent topic")

            parsed = json.loads(result)
            assert parsed["status"] == "no_results"
            assert parsed["query"] == "nonexistent topic"
            assert "No results found" in parsed["message"]

    @pytest.mark.asyncio
    async def test_results_found_with_opus_analysis(self):
        """Test search with results found and Opus analysis."""
        mock_results = [{"title": "Hook Config", "url": "https://kb.rossum.ai/hooks", "content": "Hook docs"}]

        async def mock_search(query):
            return mock_results

        with (
            patch(
                "rossum_agent.tools.subagents.knowledge_base._search_knowledge_base",
                side_effect=mock_search,
            ),
            patch(
                "rossum_agent.tools.subagents.knowledge_base._call_opus_for_web_search_analysis",
                return_value=("Analyzed hook configuration info", 100, 50),
            ) as mock_opus,
        ):
            result = await _search_and_analyze_knowledge_base(
                "hook configuration", user_query="How to configure hooks?"
            )

            parsed = json.loads(result)
            assert parsed["status"] == "success"
            assert parsed["query"] == "hook configuration"
            assert parsed["analysis"] == "Analyzed hook configuration info"
            assert parsed["input_tokens"] == 100
            assert parsed["output_tokens"] == 50
            assert "source_urls" in parsed
            mock_opus.assert_called_once()
            call_args = mock_opus.call_args
            assert call_args[0][0] == "hook configuration"
            assert call_args[1]["user_query"] == "How to configure hooks?"


class TestSearchKnowledgeBaseTool:
    """Test search_knowledge_base tool function."""

    def test_empty_query_returns_error(self):
        """Test that empty query returns error JSON."""
        result = search_knowledge_base("")

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "Query is required" in parsed["message"]

    def test_valid_query_calls_search_and_analyze(self):
        """Test that valid query calls _search_and_analyze_knowledge_base."""
        with patch(
            "rossum_agent.tools.subagents.knowledge_base._search_and_analyze_knowledge_base",
            return_value='{"status": "success", "results": []}',
        ) as mock_search:
            result = search_knowledge_base("document splitting", user_query="How to split documents?")

            mock_search.assert_called_once_with("document splitting", user_query="How to split documents?")
            parsed = json.loads(result)
            assert parsed["status"] == "success"

    def test_none_query_returns_error(self):
        """Test that None-like empty query returns error."""
        result = search_knowledge_base(query="")

        parsed = json.loads(result)
        assert parsed["status"] == "error"

    def test_whitespace_only_query_is_accepted(self):
        """Test that whitespace-only query is passed through (not validated as empty)."""
        with patch(
            "rossum_agent.tools.subagents.knowledge_base._search_and_analyze_knowledge_base",
            return_value='{"status": "no_results"}',
        ) as mock_search:
            search_knowledge_base("   ")

            mock_search.assert_called_once_with("   ", user_query=None)
