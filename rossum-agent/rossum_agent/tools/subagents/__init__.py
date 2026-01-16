"""Sub-agents for the Rossum Agent.

This package provides Opus-powered sub-agents for complex iterative tasks:
- Hook debugging with sandboxed execution
- Knowledge base search with AI analysis
- Schema patching with verification
"""

from __future__ import annotations

from rossum_agent.tools.subagents.hook_debug import debug_hook, evaluate_python_hook
from rossum_agent.tools.subagents.knowledge_base import OPUS_MODEL_ID, WebSearchError, search_knowledge_base
from rossum_agent.tools.subagents.schema_patching import patch_schema_with_subagent

__all__ = [
    "OPUS_MODEL_ID",
    "WebSearchError",
    "debug_hook",
    "evaluate_python_hook",
    "patch_schema_with_subagent",
    "search_knowledge_base",
]
