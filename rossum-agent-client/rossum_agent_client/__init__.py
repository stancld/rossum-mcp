"""Rossum Agent API Client - Python client for AI-powered document processing."""

from rossum_agent_client.client import AsyncRossumAgentClient, RossumAgentClient
from rossum_agent_client.exceptions import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    RossumAgentError,
    ServerError,
    ValidationError,
)

__version__ = "1.0.0"

__all__ = [
    "RossumAgentClient",
    "AsyncRossumAgentClient",
    "RossumAgentError",
    "AuthenticationError",
    "NotFoundError",
    "RateLimitError",
    "ValidationError",
    "ServerError",
]
