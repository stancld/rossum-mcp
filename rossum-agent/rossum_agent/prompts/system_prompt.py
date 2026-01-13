"""System prompt for the RossumAgent using Anthropic's tool use API.

This module provides the system prompt that defines the agent's behavior,
capabilities, and guidelines for interacting with the Rossum platform.
The prompt is adapted for use with Anthropic's native tool use API.
"""

from __future__ import annotations

from rossum_agent.prompts.base_prompt import ROSSUM_EXPERT_INTRO, get_shared_prompt_sections

SYSTEM_PROMPT = f"""{ROSSUM_EXPERT_INTRO}

---
{get_shared_prompt_sections()}"""


def get_system_prompt() -> str:
    """Get the system prompt for the RossumAgent.

    Returns:
        The system prompt string defining agent behavior.
    """
    return SYSTEM_PROMPT
