from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Literal


@dataclass
class AgentConfig:
    """Configuration for the RossumAgent."""

    max_output_tokens: int = 128000  # Opus 4.6 limit
    max_steps: int = 50
    temperature: float = 1.0  # Required for extended thinking
    request_delay: float = 3.0  # Delay in seconds between API calls to avoid rate limiting
    effort: Literal["max", "high", "medium", "low"] = "high"

    def __post_init__(self) -> None:
        if self.temperature != 1.0:
            msg = "temperature must be 1.0 when extended thinking is enabled"
            raise ValueError(msg)


MAX_TOOL_OUTPUT_LENGTH = 30000


def truncate_content(content: str, max_length: int = MAX_TOOL_OUTPUT_LENGTH) -> str:
    """Truncate content preserving head and tail."""
    if len(content) <= max_length:
        return content
    half = max_length // 2
    return content[:half] + f"\n..._Content truncated to stay below {max_length} characters_...\n" + content[-half:]
