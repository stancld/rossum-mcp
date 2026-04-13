from __future__ import annotations

import json

import structlog
from anthropic import beta_tool

from rossum_agent.agent.skills import get_skill, get_skill_registry
from rossum_agent.tools.dynamic_tools import load_tool, mark_skill_loaded

logger = structlog.get_logger(__name__)


def _auto_load_tools(tool_names: list[str]) -> str | None:
    """Auto-load MCP tools declared by a skill. Returns result message or None on failure."""
    try:
        result = load_tool(tool_names)
        if result.startswith("Error"):
            logger.warning(f"Failed to auto-load skill tools: {result}")
            return None
        return result
    except Exception as e:
        logger.warning(f"Failed to auto-load skill tools: {e}")
        return None


@beta_tool
def load_skill(name: str) -> str:
    """Load a specialized skill that provides domain-specific instructions and workflows.

    Use this tool when you recognize that a task matches one of the available skills.
    The skill will provide detailed instructions, workflows, and context for the task.

    Args:
        name: The name of the skill to load (e.g., "schema-patching").

    Returns:
        JSON with skill instructions, or error with available skills if not found.
    """
    if (skill := get_skill(name)) is None:
        available = get_skill_registry().get_skill_names()
        logger.error(f"Skill '{name}' not found. Available skills: {available}")
        return json.dumps({"status": "error", "message": f"Skill '{name}' not found.", "available_skills": available})
    logger.info(f"Loaded skill '{skill.name}'")
    mark_skill_loaded(name)

    loaded_tools: str | None = None
    if skill.mcp_tools:
        loaded_tools = _auto_load_tools(skill.mcp_tools)

    result: dict[str, object] = {
        "status": "success",
        "skill_name": skill.name,
        "instructions": skill.content,
    }
    if loaded_tools:
        result["loaded_tools"] = loaded_tools
    return json.dumps(result)
