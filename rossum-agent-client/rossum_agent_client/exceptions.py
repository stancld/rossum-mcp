"""Exceptions for Rossum Agent API client."""

from __future__ import annotations


class RossumAgentError(Exception):
    """Base exception for Rossum Agent API errors."""

    def __init__(self, message: str, status_code: int | None = None, response_body: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body


class AuthenticationError(RossumAgentError):
    """Raised when authentication fails (401)."""


class NotFoundError(RossumAgentError):
    """Raised when a resource is not found (404)."""


class ValidationError(RossumAgentError):
    """Raised when request validation fails (422)."""


class RateLimitError(RossumAgentError):
    """Raised when rate limit is exceeded (429)."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message, status_code, response_body)
        self.retry_after = retry_after


class ServerError(RossumAgentError):
    """Raised when server returns 5xx error."""
