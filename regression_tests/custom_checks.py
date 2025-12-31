"""Custom check functions for regression tests.

Each check function takes list[AgentStep] and returns tuple[bool, str] (passed, reasoning).
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from rossum_agent.bedrock_client import create_bedrock_client

from regression_tests.framework.constants import HAIKU_MODEL_ID

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep

_HIDDEN_MULTIVALUE_CHECK_PROMPT = """Analyze the following knowledge base search result about document splitting.

Does the response clearly warn about the requirements for datapoints used in document splitting?
Specifically, does it mention BOTH of these requirements:
1. The datapoint must NOT be hidden ("hidden": false) - hidden datapoints cannot be predicted by AI
2. The datapoint must be multivalue

Response to analyze:
{analysis}

Answer with a JSON object:
{{"passed": true/false, "reasoning": "Brief explanation of what requirements were mentioned or missing"}}"""


def check_knowledge_base_hidden_multivalue_warning(steps: list[AgentStep]) -> tuple[bool, str]:
    """Verify search_knowledge_base warns about hidden and multivalue datapoint requirements.

    Uses Haiku to semantically verify that the Opus sub-agent's analysis
    mentions datapoints used for document splitting must NOT be hidden or multivalue.

    Returns:
        Tuple of (passed, reasoning) where reasoning explains the LLM's evaluation.
    """
    for step in steps:
        for tr in step.tool_results:
            if tr.name != "search_knowledge_base":
                continue

            try:
                result = json.loads(tr.content)
            except json.JSONDecodeError:
                continue

            analysis = result.get("analysis", "")
            if not analysis:
                continue

            client = create_bedrock_client()
            response = client.messages.create(
                model=HAIKU_MODEL_ID,
                max_tokens=256,
                temperature=0,
                messages=[
                    {"role": "user", "content": _HIDDEN_MULTIVALUE_CHECK_PROMPT.format(analysis=analysis[:8000])}
                ],
            )

            text = "".join(block.text for block in response.content if hasattr(block, "text"))

            try:
                json_match = re.search(r"\{.*\}", text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return result.get("passed", False), result.get("reasoning", text)
            except json.JSONDecodeError:
                pass

            return False, f"Could not parse LLM response: {text}"

    return False, "No search_knowledge_base tool result found"
