from __future__ import annotations

import json
import logging

from anthropic import beta_tool

from rossum_agent.agent.skills import get_skill, get_skill_registry

logger = logging.getLogger(__name__)


@beta_tool
def load_skill(name: str) -> str:
    """Load a specialized skill that provides domain-specific instructions and workflows.

    Use this tool when you recognize that a task matches one of the available skills.
    The skill will provide detailed instructions, workflows, and context for the task.

    Args:
        name: The name of the skill to load (e.g., "rossum-deployment").

    Returns:
        JSON with skill instructions, or error with available skills if not found.
    """
    if (skill := get_skill(name)) is None:
        available = get_skill_registry().get_skill_names()
        logger.error(f"Skill '{name}' not found. Available skills: {available}")
        return json.dumps({"status": "error", "message": f"Skill '{name}' not found.", "available_skills": available})
    logger.info(f"Loaded skill '{skill.name}'")
    return json.dumps({"status": "success", "skill_name": skill.name, "instructions": skill.content})
