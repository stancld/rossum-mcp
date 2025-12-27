from __future__ import annotations

import pytest
from rossum_deploy.workspace import Workspace


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create a temporary workspace directory."""
    return tmp_path / "workspace"


@pytest.fixture
def workspace(tmp_workspace):
    """Create a Workspace instance with default test configuration."""
    return Workspace(tmp_workspace, api_base="https://api.example.com/v1", token="test-token")
