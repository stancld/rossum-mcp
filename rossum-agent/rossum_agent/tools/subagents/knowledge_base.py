"""Knowledge base search tools for the Rossum Agent.

This module provides tools for searching the Rossum Knowledge Base.
"""

from __future__ import annotations

import json
import logging

import requests
from anthropic import beta_tool
from ddgs import DDGS
from ddgs.exceptions import DDGSException

from rossum_agent.bedrock_client import create_bedrock_client
from rossum_agent.tools.core import SubAgentProgress, SubAgentText, report_progress, report_text

logger = logging.getLogger(__name__)

OPUS_MODEL_ID = "eu.anthropic.claude-opus-4-5-20251101-v1:0"

_WEB_SEARCH_ANALYSIS_SYSTEM_PROMPT = """You are a Rossum documentation expert. Your role is to analyze search results from the Rossum Knowledge Base and extract the most relevant information.

## Your Task

Given search results from the Rossum Knowledge Base, you must:

1. **Analyze the results**: Identify which results are most relevant to the user's query
2. **Extract key information**: Pull out the specific technical details, code examples, and JSON configurations
3. **Synthesize a response**: Provide a clear, actionable summary that directly addresses the user's needs

## Output Format

Your response MUST start with this section if the query involves document splitting, AI predictions, or field-based automation:

### ⛔ CRITICAL SCHEMA REQUIREMENTS FOR AI-BASED FEATURES ⛔

Before providing any configuration, state these MANDATORY requirements:

1. **"hidden": false is REQUIRED** - The datapoint MUST NOT be hidden. Hidden datapoints (`"hidden": true`) are invisible to Rossum AI and CANNOT receive predictions. Document splitting, field validation, and any AI-based feature will FAIL SILENTLY if the datapoint is hidden.

2. **Multivalue parent is REQUIRED for splitting** - Document splitting requires the target field to be inside a multivalue section (one value per split document).

Then continue with:

1. **Most Relevant Information**: The key facts, JSON configurations, or code examples that answer the query
2. **Implementation Details**: Specific steps or code patterns if applicable
3. **Configuration Details**: Specific configuration details, i.e. file datatypes, singlevalue vs multivalue datapoints must be returned as bold text
4. **Related Topics**: Brief mention of related documentation pages for further reading

## ⛔ JSON EXAMPLE VALIDATION RULES ⛔

When you write ANY JSON schema example for datapoints used with AI features (splitting, validation, etc.):

✅ CORRECT - Always use this pattern:
```json
{"hidden": false, "type": "string", "id": "invoice_id", ...}
```

❌ WRONG - NEVER output this (will cause silent failures):
```json
{"hidden": true, "type": "string", "id": "invoice_id", ...}
```

IMPORTANT: You must return exact configuration requirements and mention they are CRITICAL!.

Be direct and technical. Focus on actionable information that helps with Rossum hook development, extension configuration, or API usage."""

_KNOWLEDGE_BASE_DOMAIN = "knowledge-base.rossum.ai"
_MAX_SEARCH_RESULTS = 5
_WEBPAGE_FETCH_TIMEOUT = 30
_JINA_READER_PREFIX = "https://r.jina.ai/"


class WebSearchError(Exception):
    """Raised when web search fails."""

    pass


def _call_opus_for_web_search_analysis(query: str, search_results: str, user_query: str | None = None) -> str:
    """Call Opus model to analyze web search results."""
    try:
        report_progress(
            SubAgentProgress(tool_name="search_knowledge_base", iteration=0, max_iterations=0, status="analyzing")
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

## Instructions

Extract and summarize the most relevant information from these search results. Focus on:
- Specific technical details, configurations, and code examples
- **Exact schema definition - data types, singlevalue datapoints vs multivalues**
- Step-by-step instructions if present
- API endpoints, parameters, and payloads
- Common patterns and best practices

Provide a clear, actionable summary that a developer can use immediately.

⛔ MANDATORY OUTPUT REQUIREMENT:
If the topic involves document splitting, AI predictions, or field-based automation:
1. START your response with the "⛔ CRITICAL SCHEMA REQUIREMENTS" section
2. State BOTH requirements: "hidden": false AND multivalue parent
3. In ALL JSON examples, use "hidden": false - NEVER "hidden": true"""

        response = client.messages.create(
            model=OPUS_MODEL_ID,
            max_tokens=4096,
            temperature=0.25,
            system=_WEB_SEARCH_ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        text_parts = [block.text for block in response.content if hasattr(block, "text")]
        analysis_result = "\n".join(text_parts) if text_parts else "No analysis provided"

        report_progress(
            SubAgentProgress(tool_name="search_knowledge_base", iteration=0, max_iterations=0, status="completed")
        )

        report_text(SubAgentText(tool_name="search_knowledge_base", text=analysis_result, is_final=True))

        return analysis_result

    except Exception as e:
        logger.exception("Error calling Opus for web search analysis")
        return f"Error analyzing search results: {e}\n\nRaw results:\n{search_results}"


def _fetch_webpage_content(url: str) -> str:
    """Fetch and extract webpage content using Jina Reader for JS-rendered pages.

    Uses Jina Reader API to render JavaScript content from SPAs like the Rossum knowledge base.

    Returns:
        Markdown content of the page, or error message if fetch fails.
    """
    jina_url = f"{_JINA_READER_PREFIX}{url}"
    try:
        response = requests.get(jina_url, timeout=_WEBPAGE_FETCH_TIMEOUT)
        response.raise_for_status()
        content = response.text
        return content[:50000]
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch webpage {url} via Jina Reader: {e}")
        return f"[Failed to fetch content: {e}]"


def _search_knowledge_base(query: str) -> list[dict[str, str]]:
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

    results = []
    for r in filtered_results:
        url = r.get("href", "")
        logger.info(f"Fetching full content from: {url}")
        full_content = _fetch_webpage_content(url)
        results.append({"title": r.get("title", ""), "url": url, "content": full_content})

    logger.info(f"Found {len(results)} results for query: {query}")
    return results


def _search_and_analyze_knowledge_base(query: str, user_query: str | None = None) -> str:
    """Search Rossum Knowledge Base and analyze results with Opus.

    Args:
        query: Search query string.
        user_query: The original user query/question for context (optional).

    Returns:
        JSON string with analyzed results or error message.

    Raises:
        WebSearchError: If search fails completely.
    """
    results = _search_knowledge_base(query)

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
            }
        )

    search_results_text = "\n\n---\n\n".join(f"## {r['title']}\nURL: {r['url']}\n\n{r['content']}" for r in results)
    logger.info("Analyzing knowledge base results with Opus sub-agent")
    analyzed = _call_opus_for_web_search_analysis(query, search_results_text, user_query=user_query)
    return json.dumps(
        {"status": "success", "query": query, "analysis": analyzed, "source_urls": [r["url"] for r in results]}
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
        JSON with search results containing title, URL, and snippet for each result.
    """
    if not query:
        return json.dumps({"status": "error", "message": "Query is required"})
    return _search_and_analyze_knowledge_base(query, user_query=user_query)
