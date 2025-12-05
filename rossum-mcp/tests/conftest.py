"""Shared test fixtures and helpers for rossum_mcp tests."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest
from rossum_api.models.annotation import Annotation
from rossum_api.models.engine import Engine, EngineField
from rossum_api.models.hook import Hook
from rossum_api.models.queue import Queue
from rossum_api.models.schema import Schema
from rossum_api.models.workspace import Workspace
from rossum_mcp.server import RossumMCPServer

if TYPE_CHECKING:
    from collections.abc import Iterator

    from _pytest.monkeypatch import MonkeyPatch

# Store the original asdict function
_original_asdict = dataclasses.asdict


def mock_aware_asdict(obj, *, dict_factory=dict):
    """A version of dataclasses.asdict that works with Mock objects.

    If the object is a Mock, convert it to a dictionary using its attributes.
    Otherwise, use the standard dataclasses.asdict.
    """
    if isinstance(obj, Mock):
        # For Mock objects, extract all set attributes
        result = {}
        for attr in dir(obj):
            if not attr.startswith("_") and not callable(getattr(obj, attr, None)):
                try:
                    value = getattr(obj, attr)
                    # Skip Mock's default attributes
                    if not isinstance(value, type(obj.return_value)):
                        result[attr] = value
                except AttributeError:
                    pass
        return result
    # Use original asdict for real dataclasses
    return _original_asdict(obj, dict_factory=dict_factory)


# Patch dataclasses.asdict globally for all tests
dataclasses.asdict = mock_aware_asdict


@pytest.fixture
def mock_env_vars(monkeypatch: MonkeyPatch) -> None:
    """Set up environment variables for testing."""
    monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai")
    monkeypatch.setenv("ROSSUM_API_TOKEN", "test-token-123")
    # Ensure ROSSUM_MCP_MODE is not set, so default "read-write" is used
    monkeypatch.delenv("ROSSUM_MCP_MODE", raising=False)


@pytest.fixture
def mock_rossum_client() -> Iterator[AsyncMock]:
    """Create a mock Rossum API client."""
    with patch("rossum_mcp.server.AsyncRossumAPIClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def server(mock_env_vars: None, mock_rossum_client: AsyncMock) -> RossumMCPServer:
    """Create a RossumMCPServer instance for testing."""
    return RossumMCPServer()


def create_mock_annotation(**kwargs) -> Annotation:
    """Create a mock Annotation dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/annotations/1",
        "status": "to_review",
        "schema": "https://api.test.rossum.ai/v1/schemas/1",
        "modifier": None,
        "content": None,
        "queue": "https://api.test.rossum.ai/v1/queues/1",
        "creator": None,
        "created_at": "2025-01-01T00:00:00Z",
        "rir_poll_id": None,
        "email": None,
        "email_thread": None,
        "has_email_thread_with_replies": False,
        "has_email_thread_with_new_replies": False,
        "suggested_edit": None,
        "messages": [],
        "time_spent": 0,
        "relations": [],
        "pages": [],
        "document": "https://api.test.rossum.ai/v1/documents/1",
        "confirmed_at": None,
        "modified_at": "2025-01-01T00:00:00Z",
        "exported_at": None,
        "arrived_at": None,
        "assigned_at": None,
        "purged_at": None,
        "rejected_at": None,
        "deleted_at": None,
        "export_failed_at": None,
        "organization": "https://api.test.rossum.ai/v1/organizations/1",
        "metadata": {},
        "automated": False,
        "automation_blocker": None,
        "related_emails": [],
        "automatically_rejected": False,
        "prediction": None,
        "assignees": [],
        "labels": [],
        "restricted_access": False,
        "training_enabled": True,
        "einvoice": None,
        "purged_by": None,
        "rejected_by": None,
        "deleted_by": None,
        "exported_by": None,
        "confirmed_by": None,
        "modified_by": None,
    }
    defaults.update(kwargs)
    return Annotation(**defaults)


def create_mock_schema(**kwargs) -> Schema:
    """Create a mock Schema dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/schemas/1",
        "name": "Test Schema",
        "queues": [],
        "content": [],
        "metadata": {},
        "modified_by": None,
        "modified_at": "2025-01-01T00:00:00Z",
    }
    defaults.update(kwargs)
    return Schema(**defaults)


def create_mock_queue(**kwargs) -> Queue:
    """Create a mock Queue dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/queues/1",
        "name": "Test Queue",
        "workspace": "https://api.test.rossum.ai/v1/workspaces/1",
        "connector": None,
        "schema": "https://api.test.rossum.ai/v1/schemas/1",
        "inbox": "https://api.test.rossum.ai/v1/inboxes/1",
        "hooks": [],
        "users": [],
        "groups": [],
        "use_confirmed_state": True,
        "default_score_threshold": 0.8,
        "locale": "en",
        "training_enabled": True,
        "automation_enabled": True,
        "automation_level": "never",
        "generic_engine": None,
        "dedicated_engine": None,
        "counts": {},
        "metadata": {},
        "created_at": "2025-01-01T00:00:00Z",
        "modified_at": "2025-01-01T00:00:00Z",
        "status": "active",
        "description": "",
        "document_lifetime": None,
        "delete_after": None,
        "formula_fields": [],
    }
    defaults.update(kwargs)
    return Queue(**defaults)


def create_mock_hook(**kwargs) -> Hook:
    """Create a mock Hook dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/hooks/1",
        "name": "Test Hook",
        "type": "function",
        "queues": [],
        "events": [],
        "active": True,
        "config": {},
        "settings": {},
        "sideload": [],
        "run_after": [],
        "metadata": {},
        "extension_source": None,
        "test": {},
        "token_owner": None,
        "extension_image_url": None,
        "extension_pages": [],
    }
    defaults.update(kwargs)
    return Hook(**defaults)


def create_mock_workspace(**kwargs) -> Workspace:
    """Create a mock Workspace dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/workspaces/1",
        "name": "Test Workspace",
        "organization": "https://api.test.rossum.ai/v1/organizations/1",
        "queues": [],
        "autopilot": False,
        "metadata": {},
    }
    defaults.update(kwargs)
    return Workspace(**defaults)


def create_mock_engine(**kwargs) -> Engine:
    """Create a mock Engine dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/engines/1",
        "name": "Test Engine",
        "type": "extractor",
        "organization": "https://api.test.rossum.ai/v1/organizations/1",
        "learning_enabled": True,
        "training_queues": [],
        "description": "",
        "metadata": {},
        "modified_at": "2025-01-01T00:00:00Z",
        "created_at": "2025-01-01T00:00:00Z",
    }
    defaults.update(kwargs)
    return Engine(**defaults)


def create_mock_engine_field(**kwargs) -> EngineField:
    """Create a mock EngineField dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/engine_fields/1",
        "engine": "https://api.test.rossum.ai/v1/engines/1",
        "label": "Test Field",
        "type": "string",
        "subtype": None,
        "pre_trained_field_id": None,
        "options": [],
        "metadata": {},
    }
    defaults.update(kwargs)
    return EngineField(**defaults)
