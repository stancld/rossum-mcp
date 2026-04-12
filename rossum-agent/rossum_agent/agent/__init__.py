"""Agent module for Rossum document processing.

This module provides the RossumAgent class and related components for
interacting with the Rossum platform using Claude models via AWS Bedrock.
"""

from __future__ import annotations

from rossum_agent.agent.core import RossumAgent, create_agent
from rossum_agent.agent.memory import AgentMemory, MemoryStep, TaskStep
from rossum_agent.agent.models import (
    AgentStep,
    ErrorStep,
    FinalAnswerStep,
    ReasoningStep,
    TextDeltaStep,
    ToolCall,
    ToolResult,
    ToolResultStep,
    ToolStartStep,
)

__all__ = [
    "AgentMemory",
    "AgentStep",
    "ErrorStep",
    "FinalAnswerStep",
    "MemoryStep",
    "ReasoningStep",
    "RossumAgent",
    "TaskStep",
    "TextDeltaStep",
    "ToolCall",
    "ToolResult",
    "ToolResultStep",
    "ToolStartStep",
    "create_agent",
]
