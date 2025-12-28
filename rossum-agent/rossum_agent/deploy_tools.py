"""Deployment tools for the Rossum Agent.

This module provides tools for managing Rossum configuration deployments,
including pull, diff, push, and cross-org copy operations using rossum-deploy.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from anthropic import beta_tool
from rossum_deploy.models import IdMapping
from rossum_deploy.workspace import Workspace

if TYPE_CHECKING:
    from anthropic._tools import BetaTool
    from rossum_deploy.workspace import Workspace as WorkspaceType

logger = logging.getLogger(__name__)

# Import get_output_dir from internal_tools to share output directory
from rossum_agent.internal_tools import get_output_dir


def _get_workspace_credentials() -> tuple[str, str]:
    """Get Rossum API credentials from environment.

    Returns:
        Tuple of (api_base_url, api_token).
    """
    if not (api_base := os.getenv("ROSSUM_API_BASE_URL")):
        raise ValueError("ROSSUM_API_BASE_URL environment variable is required")
    if not (token := os.getenv("ROSSUM_API_TOKEN")):
        raise ValueError("ROSSUM_API_TOKEN environment variable is required")

    return api_base, token


def _create_workspace(
    path: str | None = None, api_base_url: str | None = None, token: str | None = None
) -> WorkspaceType:
    """Create a Workspace instance with current credentials.

    Args:
        path: Optional workspace directory path. Defaults to output directory.
        api_base_url: Optional API base URL. Defaults to env ROSSUM_API_BASE_URL.
        token: Optional API token. Defaults to env ROSSUM_API_TOKEN.

    Returns:
        Workspace instance.
    """
    default_api_base, default_token = _get_workspace_credentials()
    api_base = api_base_url or default_api_base
    api_token = token or default_token

    workspace_path = Path(path) if path else get_output_dir() / "rossum-config"
    workspace_path.mkdir(parents=True, exist_ok=True)

    return Workspace(workspace_path, api_base=api_base, token=api_token)


@beta_tool
def deploy_pull(
    org_id: int, workspace_path: str | None = None, api_base_url: str | None = None, token: str | None = None
) -> str:
    """Pull Rossum configuration objects from an organization to local files.

    Downloads workspaces, queues, schemas, hooks, inboxes, and other objects
    to local JSON files for version control and deployment workflows.

    Args:
        org_id: The organization ID to pull from.
        workspace_path: Optional path to the workspace directory.
            Defaults to './rossum-config' in the session output directory.
        api_base_url: Optional API base URL for the target environment.
            Use this when pulling from sandbox/different environment.
        token: Optional API token for the target environment.
            Use this when pulling from sandbox/different environment.

    Returns:
        JSON with pull summary including counts of pulled objects.
    """
    start_time = time.perf_counter()

    try:
        ws = _create_workspace(workspace_path, api_base_url=api_base_url, token=token)
        result = ws.pull(org_id=org_id)

        return json.dumps(
            {
                "status": "success",
                "summary": result.summary(),
                "pulled_count": len(result.pulled),
                "skipped_count": len(result.skipped),
                "workspace_path": str(ws.path),
                "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
            }
        )
    except Exception as e:
        logger.exception("Error in deploy_pull")
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
            }
        )


@beta_tool
def deploy_diff(workspace_path: str | None = None) -> str:
    """Compare local workspace files with remote Rossum configuration.

    Shows which objects have been modified locally, remotely, or have conflicts.

    Args:
        workspace_path: Optional path to the workspace directory.
            Defaults to './rossum-config' in the session output directory.

    Returns:
        JSON with diff summary showing unchanged, modified, and conflicting objects.
    """
    start_time = time.perf_counter()

    try:
        ws = _create_workspace(workspace_path)
        result = ws.diff()

        return json.dumps(
            {
                "status": "success",
                "summary": result.summary(),
                "unchanged": result.total_unchanged,
                "local_modified": result.total_local_modified,
                "remote_modified": result.total_remote_modified,
                "conflicts": result.total_conflicts,
                "workspace_path": str(ws.path),
                "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
            }
        )
    except Exception as e:
        logger.exception("Error in deploy_diff")
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
            }
        )


@beta_tool
def deploy_push(dry_run: bool = False, force: bool = False, workspace_path: str | None = None) -> str:
    """Push local changes to Rossum.

    Uploads modified local configuration to the remote Rossum organization.

    Args:
        dry_run: If True, only show what would be pushed without making changes.
        force: If True, push even if there are conflicts.
        workspace_path: Optional path to the workspace directory.
            Defaults to './rossum-config' in the session output directory.

    Returns:
        JSON with push summary including counts of pushed, skipped, and failed objects.
    """
    start_time = time.perf_counter()

    try:
        ws = _create_workspace(workspace_path)

        if dry_run:
            result = ws.push(dry_run=True)
            return json.dumps(
                {
                    "status": "success",
                    "dry_run": True,
                    "summary": result.summary(),
                    "would_push_count": len(result.pushed),
                    "would_skip_count": len(result.skipped),
                    "workspace_path": str(ws.path),
                    "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
                }
            )

        result = ws.push(force=force)

        return json.dumps(
            {
                "status": "success",
                "dry_run": False,
                "summary": result.summary(),
                "pushed_count": len(result.pushed),
                "skipped_count": len(result.skipped),
                "failed_count": len(result.failed),
                "workspace_path": str(ws.path),
                "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
            }
        )
    except Exception as e:
        logger.exception("Error in deploy_push")
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
            }
        )


@beta_tool
def deploy_copy_org(
    source_org_id: int,
    target_org_id: int,
    target_api_base: str | None = None,
    target_token: str | None = None,
    workspace_path: str | None = None,
) -> str:
    """Copy all objects from source organization to target organization.

    Creates copies of all workspaces, queues, schemas, hooks, and other objects
    from source org to target org. Saves ID mappings for later deployment.

    Use this to mirror production to sandbox before making changes.

    Args:
        source_org_id: Source organization ID (e.g., production).
        target_org_id: Target organization ID (e.g., sandbox).
        target_api_base: Target API base URL if different from source.
        target_token: Target API token if different from source.
        workspace_path: Optional path to the workspace directory.
            Defaults to './rossum-config' in the session output directory.

    Returns:
        JSON with copy summary including counts of created, skipped, and failed objects.
    """
    start_time = time.perf_counter()

    try:
        ws = _create_workspace(workspace_path)

        result = ws.copy_org(
            source_org_id=source_org_id,
            target_org_id=target_org_id,
            target_api_base=target_api_base,
            target_token=target_token,
        )

        return json.dumps(
            {
                "status": "success",
                "summary": result.summary(),
                "created_count": len(result.created),
                "skipped_count": len(result.skipped),
                "failed_count": len(result.failed),
                "workspace_path": str(ws.path),
                "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
            }
        )
    except Exception as e:
        logger.exception("Error in deploy_copy_org")
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
            }
        )


@beta_tool
def deploy_copy_workspace(
    source_workspace_id: int,
    target_org_id: int,
    target_api_base: str | None = None,
    target_token: str | None = None,
    workspace_path: str | None = None,
) -> str:
    """Copy a single workspace and all its objects to target organization.

    Copies a workspace with all its queues, schemas, engines, hooks, connectors,
    inboxes, email templates, and rules to the target organization.

    Useful when you only need to replicate part of an org rather than the entire organization.

    Args:
        source_workspace_id: Source workspace ID to copy.
        target_org_id: Target organization ID to copy to.
        target_api_base: Target API base URL if different from source.
        target_token: Target API token if different from source.
        workspace_path: Optional path to the workspace directory.
            Defaults to './rossum-config' in the session output directory.

    Returns:
        JSON with copy summary including counts of created, skipped, and failed objects.
    """
    start_time = time.perf_counter()

    try:
        ws = _create_workspace(workspace_path)

        result = ws.copy_workspace(
            source_workspace_id=source_workspace_id,
            target_org_id=target_org_id,
            target_api_base=target_api_base,
            target_token=target_token,
        )

        return json.dumps(
            {
                "status": "success",
                "summary": result.summary(),
                "created_count": len(result.created),
                "skipped_count": len(result.skipped),
                "failed_count": len(result.failed),
                "workspace_path": str(ws.path),
                "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
            }
        )
    except Exception as e:
        logger.exception("Error in deploy_copy_workspace")
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
            }
        )


@beta_tool
def deploy_compare_workspaces(
    source_workspace_path: str,
    target_workspace_path: str,
    id_mapping_path: str | None = None,
) -> str:
    """Compare two local workspaces to see differences between source and target.

    Use after copying a workspace to sandbox and making changes to see exactly
    what changed. Shows field-level diffs for all modified objects.

    Two use cases:
    1. Compare prod vs sandbox: Pass id_mapping_path from copy_workspace to map IDs
    2. Compare before vs after: Pass id_mapping_path=None to compare same workspace

    Args:
        source_workspace_path: Path to the source (original/production) workspace directory.
        target_workspace_path: Path to the target (modified/sandbox) workspace directory.
        id_mapping_path: Optional path to ID mapping JSON file from copy_workspace.
            If None, objects are matched by their original IDs.

    Returns:
        JSON with comparison summary showing identical, different, source-only,
        and target-only objects with field-level diffs.
    """
    start_time = time.perf_counter()

    try:
        api_base, token = _get_workspace_credentials()

        source_ws = Workspace(Path(source_workspace_path), api_base=api_base, token=token)
        target_ws = Workspace(Path(target_workspace_path), api_base=api_base, token=token)

        id_mapping = None
        if id_mapping_path:
            with open(id_mapping_path) as f:
                id_mapping = IdMapping.model_validate(json.load(f))

        result = source_ws.compare_workspaces(target_ws, id_mapping=id_mapping)

        return json.dumps(
            {
                "status": "success",
                "summary": result.summary(color=False),
                "source_workspace_id": result.source_workspace_id,
                "target_workspace_id": result.target_workspace_id,
                "total_identical": result.total_identical,
                "total_different": result.total_different,
                "source_only_count": len(result.source_only),
                "target_only_count": len(result.target_only),
                "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
            }
        )
    except Exception as e:
        logger.exception("Error in deploy_compare_workspaces")
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
            }
        )


@beta_tool
def deploy_to_org(
    target_org_id: int,
    target_api_base: str | None = None,
    target_token: str | None = None,
    dry_run: bool = False,
    workspace_path: str | None = None,
) -> str:
    """Deploy local configuration changes to a target organization.

    Uses saved ID mappings from copy_org to update the corresponding objects
    in the target organization. This is the final step in the deployment workflow.

    Args:
        target_org_id: Target organization ID to deploy to.
        target_api_base: Target API base URL if different from source.
        target_token: Target API token if different from source.
        dry_run: If True, only show what would be deployed without making changes.
        workspace_path: Optional path to the workspace directory.
            Defaults to './rossum-config' in the session output directory.

    Returns:
        JSON with deploy summary including counts of created, updated, skipped, and failed objects.
    """
    start_time = time.perf_counter()

    try:
        ws = _create_workspace(workspace_path)

        result = ws.deploy(
            target_org_id=target_org_id,
            target_api_base=target_api_base,
            target_token=target_token,
            dry_run=dry_run,
        )

        return json.dumps(
            {
                "status": "success",
                "dry_run": dry_run,
                "summary": result.summary(),
                "created_count": len(result.created),
                "updated_count": len(result.updated),
                "skipped_count": len(result.skipped),
                "failed_count": len(result.failed),
                "workspace_path": str(ws.path),
                "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
            }
        )
    except Exception as e:
        logger.exception("Error in deploy_to_org")
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
            }
        )


DEPLOY_TOOLS: list[BetaTool[..., str]] = [
    deploy_pull,
    deploy_diff,
    deploy_push,
    deploy_copy_org,
    deploy_copy_workspace,
    deploy_compare_workspaces,
    deploy_to_org,
]


def get_deploy_tools() -> list[dict[str, object]]:
    """Get all deployment tools in Anthropic format."""
    return [tool.to_dict() for tool in DEPLOY_TOOLS]


def get_deploy_tool_names() -> set[str]:
    """Get the names of all deployment tools."""
    return {tool.name for tool in DEPLOY_TOOLS}


def execute_deploy_tool(name: str, arguments: dict[str, object]) -> str:
    """Execute a deployment tool by name.

    Args:
        name: The name of the tool to execute.
        arguments: The arguments to pass to the tool.

    Returns:
        The result of the tool execution as a string.

    Raises:
        ValueError: If the tool name is not recognized.
    """
    for tool in DEPLOY_TOOLS:
        if tool.name == name:
            result: str = tool(**arguments)
            return result

    raise ValueError(f"Unknown deploy tool: {name}")
