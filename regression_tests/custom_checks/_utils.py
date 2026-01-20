"""Shared utilities for custom checks."""

from __future__ import annotations

import json
import re

from rossum_agent.bedrock_client import HAIKU_MODEL_ID, create_bedrock_client


def call_haiku_check(prompt: str) -> tuple[bool, str]:
    """Call Haiku with a check prompt and parse the JSON response.

    Args:
        prompt: The fully formatted prompt to send to Haiku.

    Returns:
        Tuple of (passed, reasoning) from Haiku's response.
    """
    client = create_bedrock_client()
    response = client.messages.create(
        model=HAIKU_MODEL_ID, max_tokens=256, temperature=0, messages=[{"role": "user", "content": prompt}]
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
