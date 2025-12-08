"""FastAPI server for rossum-agent.

This module re-exports from rossum_agent.api for backwards compatibility.

Usage:
    uvicorn rossum_agent.api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from rossum_agent.api import app, main

__all__ = ["app", "main"]

if __name__ == "__main__":
    main()
