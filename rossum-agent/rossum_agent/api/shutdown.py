"""Graceful shutdown state for the API server.

On SIGTERM, the server enters graceful shutdown: new requests are rejected with
503 while in-flight requests (including SSE streams) are allowed to complete.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio


@dataclass
class ShutdownState:
    shutting_down: bool = False
    active_requests: int = 0
    drain_task: asyncio.Task | None = field(default=None, repr=False)


# Module-level singleton shared across middleware and signal handler
shutdown_state = ShutdownState()
