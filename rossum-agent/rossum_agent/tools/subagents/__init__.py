"""Sub-agents for the Rossum Agent.

Opus-powered sub-agents for complex iterative tasks:
- Hook debugging with sandboxed execution
- Knowledge base search with AI analysis
- Schema patching with programmatic bulk updates
"""

from __future__ import annotations

from rossum_agent.bedrock_client import OPUS_MODEL_ID
from rossum_agent.tools.subagents.base import SubAgent, SubAgentConfig, SubAgentResult
from rossum_agent.tools.subagents.hook_debug import HookDebugSubAgent, debug_hook, evaluate_python_hook
from rossum_agent.tools.subagents.knowledge_base import WebSearchError, search_knowledge_base
from rossum_agent.tools.subagents.mcp_helpers import call_mcp_tool
from rossum_agent.tools.subagents.schema_patching import SchemaPatchingSubAgent, patch_schema_with_subagent

__all__ = [
    "OPUS_MODEL_ID",
    "HookDebugSubAgent",
    "SchemaPatchingSubAgent",
    "SubAgent",
    "SubAgentConfig",
    "SubAgentResult",
    "WebSearchError",
    "call_mcp_tool",
    "debug_hook",
    "evaluate_python_hook",
    "patch_schema_with_subagent",
    "search_knowledge_base",
]
