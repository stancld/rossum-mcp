"""Mermaid diagram analysis using LLM."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from rossum_agent.bedrock_client import create_bedrock_client

if TYPE_CHECKING:
    from collections.abc import Sequence

HAIKU_MODEL_ID = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"

ANALYSIS_PROMPT = """You are evaluating whether mermaid diagrams match expected descriptions.

Here are the mermaid diagrams extracted from the answer:

{diagrams}

Here are the expected descriptions of what the diagrams should represent:

{descriptions}

For each expected description, determine if there is a matching diagram that represents it.

Respond with a JSON object:
{{
    "matches": true/false,
    "reasoning": "Brief explanation of match/mismatch",
    "missing": ["list of descriptions that have no matching diagram"]
}}

Be lenient - the diagram should capture the essence of the description, not match it exactly."""


def extract_mermaid_diagrams(text: str) -> list[str]:
    pattern = r"```mermaid\s*(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    return [m.strip() for m in matches]


def validate_mermaid_diagrams(
    final_answer: str, descriptions: Sequence[str], min_diagrams: int = 0
) -> tuple[bool, str]:
    """Validate mermaid diagrams in the answer against expected descriptions.

    Args:
        final_answer: The agent's final answer containing mermaid diagrams.
        descriptions: Expected descriptions of what diagrams should represent.
        min_diagrams: Minimum number of diagrams expected.

    Returns:
        Tuple of (success, message). Success is True if validation passes.
    """
    diagrams = extract_mermaid_diagrams(final_answer)

    if len(diagrams) < min_diagrams:
        return False, f"Expected at least {min_diagrams} diagrams, found {len(diagrams)}"

    if not descriptions:
        return True, "No diagram descriptions to validate"

    if not diagrams:
        return False, "No mermaid diagrams found but descriptions were expected"

    diagrams_text = "\n\n".join(f"Diagram {i + 1}:\n```\n{d}\n```" for i, d in enumerate(diagrams))
    descriptions_text = "\n".join(f"- {d}" for d in descriptions)

    client = create_bedrock_client()
    response = client.messages.create(
        model=HAIKU_MODEL_ID,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": ANALYSIS_PROMPT.format(diagrams=diagrams_text, descriptions=descriptions_text),
            }
        ],
    )

    response_text = response.content[0].text if response.content else ""

    json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if not json_match:
        return False, f"Could not parse LLM response: {response_text}"

    try:
        result = json.loads(json_match.group())
    except json.JSONDecodeError:
        return False, f"Invalid JSON in LLM response: {response_text}"

    if result.get("matches", False):
        return True, result.get("reasoning", "Diagrams match expectations")
    missing = result.get("missing", [])
    return False, f"Diagram mismatch: {result.get('reasoning', '')}. Missing: {missing}"
