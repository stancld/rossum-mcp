"""Agent module for Rossum document processing.

This module provides the RossumAgent class and related components for
interacting with the Rossum platform using Claude models via AWS Bedrock.
"""

from __future__ import annotations

from rossum_agent.agent.core import RossumAgent, create_agent
from rossum_agent.agent.memory import AgentMemory, MemoryStep, TaskStep
from rossum_agent.agent.models import (
    MAX_TOOL_OUTPUT_LENGTH,
    AgentConfig,
    AgentStep,
    ToolCall,
    ToolResult,
    truncate_content,
)

__all__ = [
    "MAX_TOOL_OUTPUT_LENGTH",
    "AgentConfig",
    "AgentMemory",
    "AgentStep",
    "MemoryStep",
    "RossumAgent",
    "TaskStep",
    "ToolCall",
    "ToolResult",
    "create_agent",
    "truncate_content",
]
