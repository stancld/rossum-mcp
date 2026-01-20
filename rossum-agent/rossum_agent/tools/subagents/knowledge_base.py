"""Knowledge base search sub-agent.

Provides tools for searching and analyzing the Rossum Knowledge Base.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
from typing import TYPE_CHECKING

import httpx
from anthropic import beta_tool
from ddgs import DDGS
from ddgs.exceptions import DDGSException

from rossum_agent.bedrock_client import create_bedrock_client, get_model_id
from rossum_agent.tools.core import (
    SubAgentProgress,
    SubAgentText,
    SubAgentTokenUsage,
    report_progress,
    report_text,
    report_token_usage,
)

if TYPE_CHECKING:
    from collections.abc import Coroutine

logger = logging.getLogger(__name__)

_WEB_SEARCH_ANALYSIS_SYSTEM_PROMPT = """Goal: Extract actionable technical information from Rossum Knowledge Base search results.

## Output Format

| Section | Content |
|---------|---------|
| Key Information | Facts, JSON configs, code examples answering the query |
| Implementation | Steps, code patterns if applicable |
| Configuration | Data types, singlevalue vs multivalue (bold) |
| Related Topics | Brief mention of related docs |

## AI Feature Requirements

For document splitting, AI predictions, or field-based automation:

| Requirement | Rule |
|-------------|------|
| hidden | Must be `false`. Hidden datapoints invisible to AI—features fail silently. |
| Multivalue parent | Required for splitting (one value per split document). |

## JSON Schema Examples

For AI features, always use `"hidden": false`:
```json
{"hidden": false, "type": "string", "id": "invoice_id"}
```

Never `"hidden": true`—causes silent failures."""

_KNOWLEDGE_BASE_DOMAIN = "knowledge-base.rossum.ai"
_MAX_SEARCH_RESULTS = 5
_WEBPAGE_FETCH_TIMEOUT = 30
_JINA_READER_PREFIX = "https://r.jina.ai/"


class WebSearchError(Exception):
    """Raised when web search fails."""


def _run_async[T](coro: Coroutine[None, None, T]) -> T:
    """Run a coroutine, handling both sync and async caller contexts."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # In async context: run in new thread with its own event loop
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()  # type: ignore[return-value] - Future.result() returns Any


def _call_opus_for_web_search_analysis(
    query: str, search_results: str, user_query: str | None = None
) -> tuple[str, int, int]:
    """Call Opus model to analyze web search results.

    Returns:
        Tuple of (analysis_text, input_tokens, output_tokens).
    """
    try:
        report_progress(
            SubAgentProgress(tool_name="search_knowledge_base", iteration=1, max_iterations=1, status="analyzing")
        )

        client = create_bedrock_client()

        user_query_context = ""
        if user_query and user_query != query:
            user_query_context = f"""
## User's Original Question

The user asked: "{user_query}"

Keep this context in mind when analyzing the search results and tailor your response to address the user's specific question.

"""

        user_content = f"""Analyze these Rossum Knowledge Base search results for the query: "{query}"
{user_query_context}
## Search Results

{search_results}

## Goal

Extract actionable technical information a developer can use immediately.

| Priority | Content |
|----------|---------|
| Schema definitions | Data types, singlevalue vs multivalue |
| Code examples | JSON configs, API payloads |
| Implementation steps | When present |

## AI Feature Topics (document splitting, AI predictions, field automation)

When the topic involves document splitting, beware of the bug in knowledge base, emphasize below:

⛔ CRITICAL SCHEMA REQUIREMENTS
| Property | Constraint |
|----------|------------|
| hidden | false |
| Multivalue parent | Required for splitting (one value per split document)."""

        response = client.messages.create(
            model=get_model_id(),
            max_tokens=4096,
            temperature=0.25,
            system=_WEB_SEARCH_ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        logger.info(f"search_knowledge_base: LLM analysis, tokens in={input_tokens} out={output_tokens}")

        report_token_usage(
            SubAgentTokenUsage(
                tool_name="search_knowledge_base", input_tokens=input_tokens, output_tokens=output_tokens, iteration=1
            )
        )

        text_parts = [block.text for block in response.content if hasattr(block, "text")]
        analysis_result = "\n".join(text_parts) if text_parts else "No analysis provided"

        report_progress(
            SubAgentProgress(tool_name="search_knowledge_base", iteration=1, max_iterations=1, status="completed")
        )

        report_text(SubAgentText(tool_name="search_knowledge_base", text=analysis_result, is_final=True))

        return analysis_result, input_tokens, output_tokens

    except Exception as e:
        logger.exception("Error calling Opus for web search analysis")
        return f"Error analyzing search results: {e}\n\nRaw results:\n{search_results}", 0, 0


async def _fetch_webpage_content(client: httpx.AsyncClient, url: str) -> str:
    """Fetch and extract webpage content using Jina Reader for JS-rendered pages.

    Uses Jina Reader API to render JavaScript content from SPAs like the Rossum knowledge base.

    Returns:
        Markdown content of the page, or error message if fetch fails.
    """
    jina_url = f"{_JINA_READER_PREFIX}{url}"
    try:
        response = await client.get(jina_url, timeout=_WEBPAGE_FETCH_TIMEOUT)
        response.raise_for_status()
        content = response.text
        return content[:50000]
    except httpx.HTTPError as e:
        logger.warning(f"Failed to fetch webpage {url} via Jina Reader: {e}")
        return f"[Failed to fetch content: {e}]"


async def _search_knowledge_base(query: str) -> list[dict[str, str]]:
    """Search Rossum Knowledge Base using DDGS metasearch library.

    Args:
        query: Search query string.

    Returns:
        List of search result dicts with title, url, and content.

    Raises:
        WebSearchError: If search fails completely.
    """
    report_progress(
        SubAgentProgress(tool_name="search_knowledge_base", iteration=0, max_iterations=0, status="searching")
    )

    site_query = f"site:{_KNOWLEDGE_BASE_DOMAIN} {query}"
    logger.info(f"Searching knowledge base: {site_query}")

    try:
        with DDGS() as ddgs:
            raw_results = ddgs.text(site_query, max_results=_MAX_SEARCH_RESULTS)
    except DDGSException as e:
        logger.error(f"Knowledge base search failed: {e}")
        raise WebSearchError(f"Search failed: {e}")

    filtered_results = [r for r in raw_results if _KNOWLEDGE_BASE_DOMAIN in r.get("href", "")][:2]

    async with httpx.AsyncClient() as client:
        fetch_tasks = []
        for r in filtered_results:
            url = r.get("href", "")
            logger.info(f"Fetching full content from: {url}")
            fetch_tasks.append(_fetch_webpage_content(client, url))

        contents = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    results = []
    for r, content in zip(filtered_results, contents):
        if isinstance(content, Exception):
            logger.warning(f"Failed to fetch {r.get('href', '')}: {content}")
            content = f"[Failed to fetch content: {content}]"
        results.append({"title": r.get("title", ""), "url": r.get("href", ""), "content": content})

    logger.info(f"Found {len(results)} results for query: {query}")
    return results


async def _search_and_analyze_knowledge_base(query: str, user_query: str | None = None) -> str:
    """Search Rossum Knowledge Base and analyze results with Opus.

    Args:
        query: Search query string.
        user_query: The original user query/question for context (optional).

    Returns:
        JSON string with analyzed results or error message.

    Raises:
        WebSearchError: If search fails completely.
    """
    results = await _search_knowledge_base(query)

    if not results:
        logger.warning(f"No results found for query: {query}")
        return json.dumps(
            {
                "status": "no_results",
                "query": query,
                "message": (
                    f"No results found in Rossum Knowledge Base for: '{query}'. "
                    "Try different keywords or check the extension/hook name spelling."
                ),
                "input_tokens": 0,
                "output_tokens": 0,
            }
        )

    search_results_text = "\n\n---\n\n".join(f"## {r['title']}\nURL: {r['url']}\n\n{r['content']}" for r in results)
    logger.info("Analyzing knowledge base results with Opus sub-agent")
    analyzed, input_tokens, output_tokens = _call_opus_for_web_search_analysis(
        query, search_results_text, user_query=user_query
    )

    logger.info(f"search_knowledge_base: completed, tokens in={input_tokens} out={output_tokens}")

    return json.dumps(
        {
            "status": "success",
            "query": query,
            "analysis": analyzed,
            "source_urls": [r["url"] for r in results],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
    )


@beta_tool
def search_knowledge_base(query: str, user_query: str | None = None) -> str:
    """Search the Rossum Knowledge Base for documentation about extensions, hooks, and configurations.

    Use this tool to find information about Rossum features, troubleshoot errors,
    and understand extension configurations. The search is performed against
    https://knowledge-base.rossum.ai/docs.

    Args:
        query: Search query. Be specific - include extension names, error messages,
        or feature names. Examples: 'document splitting extension',
        'duplicate handling configuration', 'webhook timeout error'.
        user_query: The original user question for context. Pass the user's full
        question here so Opus can tailor the analysis to address their specific needs.

    Returns:
        JSON with search results containing title, URL, snippet, and token usage.
    """
    if not query:
        return json.dumps({"status": "error", "message": "Query is required", "input_tokens": 0, "output_tokens": 0})
    return _run_async(_search_and_analyze_knowledge_base(query, user_query=user_query))
