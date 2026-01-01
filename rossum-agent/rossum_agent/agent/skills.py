"""Skills module for loading and managing agent skills.

Skills are markdown files that provide domain-specific instructions and workflow to the agent. They are loaded
from the skills directory and injected into the agent's system prompt.
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

    Skills are markdown files in the skills directory that provide domain-specific instructions for the agent.
    """

    def __init__(self, skills_dir: Path | None = None) -> None:
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
        self._load_skills()
        return list(self._skills.values())

    def get_skill_names(self) -> list[str]:
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
    global _default_registry
    if _default_registry is None or skills_dir is not None:
        _default_registry = SkillRegistry(skills_dir)
    return _default_registry


def get_skill(slug: str) -> Skill | None:
    return get_skill_registry().get_skill(slug)


def get_all_skills() -> list[Skill]:
    return get_skill_registry().get_all_skills()


def format_skills_summary_for_prompt(skills: list[Skill] | None = None) -> str:
    """Format a brief summary of available skills for the system prompt.

    Only includes skill name and first paragraph (description), not full content.
    Full content is injected when load_skill is called.
    """
    if skills is None:
        skills = get_all_skills()

    if not skills:
        return ""

    lines = ["## Available Skills", "", 'Call `load_skill("<skill-slug>")` to load full instructions.', ""]
    for skill in skills:
        first_para = skill.content.split("\n\n")[0].strip()
        lines.append(f"- **{skill.slug}**: {first_para}")

    return "\n".join(lines)


def format_skills_for_prompt(skills: list[Skill] | None = None) -> str:
    """Format full skill content for injection after load_skill is called."""
    if skills is None:
        skills = get_all_skills()

    if not skills:
        return ""

    sections = []
    for skill in skills:
        sections.append(f"\n{'=' * 60}\n{skill.content}\n{'=' * 60}")

    return "\n\n## Loaded Skills\n" + "\n".join(sections)


def get_skill_content(slug: str) -> str | None:
    skill = get_skill(slug)
    return skill.content if skill else None
