"""Handler modules for Rossum MCP Server"""

from rossum_mcp.handlers.annotations import AnnotationsHandler
from rossum_mcp.handlers.engines import EnginesHandler
from rossum_mcp.handlers.hooks import HooksHandler
from rossum_mcp.handlers.queues import QueuesHandler
from rossum_mcp.handlers.rules import RulesHandler
from rossum_mcp.handlers.schemas import SchemasHandler
from rossum_mcp.handlers.workspaces import WorkspacesHandler

__all__ = [
    "AnnotationsHandler",
    "EnginesHandler",
    "HooksHandler",
    "QueuesHandler",
    "RulesHandler",
    "SchemasHandler",
    "WorkspacesHandler",
]
