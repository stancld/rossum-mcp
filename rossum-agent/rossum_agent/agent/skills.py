"""Skills module for loading and managing agent skills.

Skills are markdown files that provide domain-specific instructions and workflows
to the agent. They are loaded from the skills directory and injected into the
agent's system prompt.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Default skills directory path relative to rossum_agent package
_SKILLS_DIR = Path(__file__).parent.parent / "skills"


@dataclass
class Skill:
    """Represents a loaded skill with its content and metadata."""

    name: str
    content: str
    file_path: Path

    @property
    def slug(self) -> str:
        """Get the skill slug (filename without extension)."""
        return self.file_path.stem


class SkillRegistry:
    """Registry for loading and managing agent skills.

    Skills are markdown files in the skills directory that provide
    domain-specific instructions for the agent.
    """

    def __init__(self, skills_dir: Path | None = None) -> None:
        """Initialize the skill registry.

        Args:
            skills_dir: Optional custom skills directory path.
                       Defaults to the package's skills directory.
        """
        self.skills_dir = skills_dir or _SKILLS_DIR
        self._skills: dict[str, Skill] = {}
        self._loaded = False

    def _load_skills(self) -> None:
        """Load all skills from the skills directory."""
        if self._loaded:
            return

        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            self._loaded = True
            return

        for skill_file in self.skills_dir.glob("*.md"):
            try:
                content = skill_file.read_text(encoding="utf-8")
                skill = Skill(
                    name=skill_file.stem.replace("-", " ").replace("_", " ").title(),
                    content=content,
                    file_path=skill_file,
                )
                self._skills[skill.slug] = skill
                logger.debug(f"Loaded skill: {skill.name} from {skill_file}")
            except Exception as e:
                logger.error(f"Failed to load skill from {skill_file}: {e}")

        self._loaded = True
        logger.info(f"Loaded {len(self._skills)} skills from {self.skills_dir}")

    def get_skill(self, slug: str) -> Skill | None:
        """Get a skill by its slug (filename without extension).

        Args:
            slug: The skill slug (e.g., "rossum-deployment").

        Returns:
            The Skill object if found, None otherwise.
        """
        self._load_skills()
        return self._skills.get(slug)

    def get_all_skills(self) -> list[Skill]:
        """Get all loaded skills.

        Returns:
            List of all loaded Skill objects.
        """
        self._load_skills()
        return list(self._skills.values())

    def get_skill_names(self) -> list[str]:
        """Get the names of all available skills.

        Returns:
            List of skill slugs.
        """
        self._load_skills()
        return list(self._skills.keys())

    def reload(self) -> None:
        """Force reload all skills from disk."""
        self._skills.clear()
        self._loaded = False
        self._load_skills()


# Module-level default registry instance
_default_registry: SkillRegistry | None = None


def get_skill_registry(skills_dir: Path | None = None) -> SkillRegistry:
    """Get the skill registry, creating it if necessary.

    Args:
        skills_dir: Optional custom skills directory path.

    Returns:
        The SkillRegistry instance.
    """
    global _default_registry
    if _default_registry is None or skills_dir is not None:
        _default_registry = SkillRegistry(skills_dir)
    return _default_registry


def get_skill(slug: str) -> Skill | None:
    """Get a skill by its slug.

    Args:
        slug: The skill slug (e.g., "rossum-deployment").

    Returns:
        The Skill object if found, None otherwise.
    """
    return get_skill_registry().get_skill(slug)


def get_all_skills() -> list[Skill]:
    """Get all loaded skills.

    Returns:
        List of all loaded Skill objects.
    """
    return get_skill_registry().get_all_skills()


def format_skills_for_prompt(skills: list[Skill] | None = None) -> str:
    """Format skills into a string suitable for system prompt injection.

    Args:
        skills: Optional list of skills to format. If None, uses all skills.

    Returns:
        Formatted string with all skill contents, or empty string if no skills.
    """
    if skills is None:
        skills = get_all_skills()

    if not skills:
        return ""

    sections = []
    for skill in skills:
        sections.append(f"\n{'=' * 60}\n{skill.content}\n{'=' * 60}")

    return "\n\n## Available Skills\n" + "\n".join(sections)


def get_skill_content(slug: str) -> str | None:
    """Get the content of a skill by its slug.

    Args:
        slug: The skill slug (e.g., "rossum-deployment").

    Returns:
        The skill content as a string, or None if not found.
    """
    skill = get_skill(slug)
    return skill.content if skill else None
