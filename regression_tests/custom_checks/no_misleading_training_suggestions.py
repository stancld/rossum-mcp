"""Check that agent doesn't make misleading training suggestions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from regression_tests.custom_checks._utils import call_haiku_check

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep

_PROMPT = """Analyze the following agent response about a document workflow.

Does the response contain any MISLEADING suggestions about engine training?
1. Suggesting to add Inbox queue to engine's training_queues (Inbox has unsplit docs without document_type - cannot train)
2. Claiming the classification engine can learn from Inbox documents
3. Any misleading claim that Inbox documents contribute to training

Response to analyze:
{final_answer}

Answer with a JSON object:
{{"passed": true/false, "reasoning": "Explain if any misleading suggestions were found and what they were, or confirm the response is accurate"}}

IMPORTANT: "passed": true means the response is ACCURATE (no misleading suggestions found).
"passed": false means MISLEADING suggestions were found."""


def check_no_misleading_training_suggestions(
    steps: list[AgentStep], _api_base_url: str, _api_token: str
) -> tuple[bool, str]:
    """Verify the final answer doesn't contain misleading training suggestions.

    Uses Haiku to semantically verify that the agent's response doesn't make
    misleading claims like suggesting Inbox can train the classification engine.

    Returns:
        Tuple of (passed, reasoning) where reasoning explains the LLM's evaluation.
    """
    final_answer = None
    for step in reversed(steps):
        if step.final_answer:
            final_answer = step.final_answer
            break

    if not final_answer:
        return False, "No final answer found in agent steps"

    return call_haiku_check(_PROMPT.format(final_answer=final_answer[:12000]))
