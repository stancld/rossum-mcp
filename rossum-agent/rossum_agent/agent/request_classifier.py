"""Lightweight request classifier for filtering out-of-scope requests.

This module provides a fast pre-filter that checks if a user request is within
the scope of the Rossum platform assistant before engaging the full agent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anthropic import AnthropicBedrock

logger = logging.getLogger(__name__)

CLASSIFIER_PROMPT = """You are a scope classifier for a Rossum document processing platform assistant.

The assistant can help with:
- Queue, hook, schema, and extension analysis/configuration
- Debugging document processing issues and errors
- Investigating hook logs and extension behavior
- Explaining workflows and automation
- Writing analysis reports about Rossum configuration issues

IN_SCOPE: Request relates to Rossum PLATFORM operations - setuping new organization, analyzing/configuring queues, hooks, schemas, extensions, debugging errors, investigating logs, explaining workflows, analysis and structured report of customer use-cases on the platform. Also: user asks what the assistant can do, greets assistant.

OUT_OF_SCOPE: Request is for DATA analytics - aggregating extracted data, generating charts/plots from document data, summarizing line items/amounts across documents, creating files unrelated to Rossum debugging. Even if it mentions Rossum annotations, if the goal is data aggregation/visualization, it's OUT_OF_SCOPE.

Examples:
- "Investigate errors with document splitting on queue X" → IN_SCOPE (debugging)
- "Aggregate line item amounts and generate a bar chart" → OUT_OF_SCOPE (data analytics)
- "Create a markdown saying hello" → OUT_OF_SCOPE (generic file creation)

Respond with exactly one word: IN_SCOPE or OUT_OF_SCOPE

User request: {message}"""

CLASSIFIER_MODEL_ID = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
CLASSIFIER_MAX_TOKENS = 10


class RequestScope(Enum):
    """Classification result for a user request."""

    IN_SCOPE = "IN_SCOPE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


@dataclass
class ClassificationResult:
    """Result of request classification."""

    scope: RequestScope
    raw_response: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class RejectionResult:
    """Result of rejection response generation."""

    response: str
    input_tokens: int = 0
    output_tokens: int = 0


REJECTION_PROMPT = """You are an expert Rossum platform specialist. The user made a request that is outside your scope.

I can help with:
- Analyzing and debugging hooks, extensions, and workflows
- Documenting queue configurations
- Investigating processing errors
- Configuring automation

The user asked: {message}

Write a brief, helpful response that:
1. Politely explains this is outside your Rossum platform expertise
2. Briefly mentions 2-3 relevant things you CAN help with from the capabilities above
3. Asks if they have any Rossum-related questions

Keep it concise (3-4 sentences max). Be friendly, not robotic."""

REJECTION_MAX_TOKENS = 300


def generate_rejection_response(client: AnthropicBedrock, message: str) -> RejectionResult:
    """Generate a contextual rejection response for out-of-scope requests."""
    prompt = REJECTION_PROMPT.format(message=message)
    try:
        response = client.messages.create(
            model=CLASSIFIER_MODEL_ID, max_tokens=REJECTION_MAX_TOKENS, messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip() if response.content else _fallback_response()
        return RejectionResult(
            response=text, input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens
        )
    except Exception as e:
        logger.warning(f"Rejection response generation failed: {e}")
        return RejectionResult(response=_fallback_response())


def _fallback_response() -> str:
    return (
        "I'm an expert Rossum platform specialist focused on document processing workflows. "
        "Your request appears to be outside my area of expertise. "
        "I can help with analyzing hooks, debugging extensions, documenting queue configurations, "
        "and configuring automation workflows. Do you have any Rossum-related questions?"
    )


def classify_request(client: AnthropicBedrock, message: str) -> ClassificationResult:
    """Classify whether a user request is within scope.

    Uses a fast, cheap model (Haiku) with minimal tokens to quickly determine if the request should be processed by the main agent.
    """
    prompt = CLASSIFIER_PROMPT.format(message=message)

    try:
        response = client.messages.create(
            model=CLASSIFIER_MODEL_ID, max_tokens=CLASSIFIER_MAX_TOKENS, messages=[{"role": "user", "content": prompt}]
        )

        raw_response = response.content[0].text.strip().upper() if response.content else ""

        scope = RequestScope.OUT_OF_SCOPE if "OUT_OF_SCOPE" in raw_response else RequestScope.IN_SCOPE

        logger.debug(f"Request classified as {scope.value}: {message[:50]}...")
        return ClassificationResult(
            scope=scope,
            raw_response=raw_response,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    except Exception as e:
        logger.warning(f"Classification failed, defaulting to IN_SCOPE: {e}")
        return ClassificationResult(scope=RequestScope.IN_SCOPE, raw_response=f"error: {e}")
