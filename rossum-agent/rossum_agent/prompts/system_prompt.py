"""System prompt for the RossumAgent using Anthropic's tool use API.

This module provides the system prompt that defines the agent's behavior,
capabilities, and guidelines for interacting with the Rossum platform.
The prompt is adapted for use with Anthropic's native tool use API.
"""

from __future__ import annotations

from rossum_agent.prompts.base_prompt import (
    ROSSUM_EXPERT_INTRO,
    get_shared_prompt_sections,
)

TOOL_USE_INTRO = """
You have access to tools for interacting with the Rossum API. Use these tools to:
- List and inspect queues, schemas, hooks, and annotations
- Analyze hook dependencies and workflows
- Document configurations
- Debug issues

When using tools:
1. Think through what information you need
2. Call the appropriate tools with correct parameters
3. Analyze the results
4. Provide clear, actionable responses"""

SYSTEM_PROMPT = f"""{ROSSUM_EXPERT_INTRO}
{TOOL_USE_INTRO}

---
{get_shared_prompt_sections()}"""


def get_system_prompt() -> str:
    """Get the system prompt for the RossumAgent.

    Returns:
        The system prompt string defining agent behavior.
    """
    return SYSTEM_PROMPT


def get_system_prompt_with_tools_summary(tool_names: list[str]) -> str:
    """Get the system prompt with a summary of available tools appended.

    Args:
        tool_names: List of available tool names.

    Returns:
        The system prompt with tool summary appended.
    """
    tools_section = f"""

---

# Available Tools

You have access to the following tools:

{chr(10).join(f"- `{name}`" for name in sorted(tool_names))}

Use these tools to accomplish the user's requests. Call tools with their required parameters.
"""
    return SYSTEM_PROMPT + tools_section
