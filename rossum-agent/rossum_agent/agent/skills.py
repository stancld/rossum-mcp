"""Skills module for loading and managing agent skills.

Skills are markdown files with YAML frontmatter that provide domain-specific instructions
and workflow to the agent. Frontmatter supplies metadata (name, description); the body
after the closing ``---`` is the skill content delivered to the agent.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Default skills directory path relative to rossum_agent package
_SKILLS_DIR = Path(__file__).parent.parent / "skills"

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, str | list[str]], str]:
    """Parse YAML frontmatter from markdown text.

    Supports scalar values (``key: value``) and YAML lists::

        tools:
          - tool_a
          - tool_b

    Returns ``(metadata, body)``.  If no frontmatter is found the full text
    is returned as the body with an empty metadata dict.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict[str, str | list[str]] = {}
    current_key: str | None = None
    current_list: list[str] | None = None
    for line in match.group(1).strip().splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and current_key is not None:
            if current_list is None:
                current_list = []
            current_list.append(stripped[2:].strip())
        else:
            if current_key is not None and current_list is not None:
                meta[current_key] = current_list
                current_list = None
            key, _, value = line.partition(":")
            if key.strip():
                current_key = key.strip()
                value = value.strip()
                if value:
                    meta[current_key] = value
    if current_key is not None and current_list is not None:
        meta[current_key] = current_list
    return meta, text[match.end() :]


@dataclass
class Skill:
    """Represents a loaded skill with its content and metadata."""

    name: str
    content: str
    file_path: Path
    description: str = field(default="")
    mcp_tools: list[str] = field(default_factory=list)

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

        for skill_file in self.skills_dir.rglob("*.md"):
            try:
                raw = skill_file.read_text(encoding="utf-8")
                meta, body = _parse_frontmatter(raw)
                name_raw = meta.get("name", "")
                name = (
                    name_raw
                    if isinstance(name_raw, str)
                    else skill_file.stem.replace("-", " ").replace("_", " ").title()
                )
                if not name:
                    name = skill_file.stem.replace("-", " ").replace("_", " ").title()
                desc_raw = meta.get("description", "")
                description = desc_raw if isinstance(desc_raw, str) else ""
                mcp_tools_raw = meta.get("mcp_tools", "")
                if isinstance(mcp_tools_raw, list):
                    mcp_tools = mcp_tools_raw
                else:
                    mcp_tools = [t.strip() for t in mcp_tools_raw.split(",") if t.strip()] if mcp_tools_raw else []
                skill = Skill(
                    name=name,
                    description=description,
                    content=body,
                    file_path=skill_file,
                    mcp_tools=mcp_tools,
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
            slug: The skill slug (e.g., "schema-patching").

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
