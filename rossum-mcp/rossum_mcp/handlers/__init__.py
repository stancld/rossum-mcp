"""Handler modules for Rossum MCP Server"""

from __future__ import annotations

from rossum_mcp.handlers.annotations import AnnotationsHandler
from rossum_mcp.handlers.engines import EnginesHandler
from rossum_mcp.handlers.hooks import HooksHandler
from rossum_mcp.handlers.queues import QueuesHandler
from rossum_mcp.handlers.relations import RelationsHandler
from rossum_mcp.handlers.rules import RulesHandler
from rossum_mcp.handlers.schemas import SchemasHandler
from rossum_mcp.handlers.workspaces import WorkspacesHandler

__all__ = [
    "AnnotationsHandler",
    "EnginesHandler",
    "HooksHandler",
    "QueuesHandler",
    "RelationsHandler",
    "RulesHandler",
    "SchemasHandler",
    "WorkspacesHandler",
]
