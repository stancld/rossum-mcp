"""Rule models."""

from __future__ import annotations

from dataclasses import dataclass

from rossum_api.models.rule import Rule as RossumRule

from rossum_mcp.models.base import RossumResourceWithResolvedWorkspaces


@dataclass
class Rule(RossumResourceWithResolvedWorkspaces[RossumRule], RossumRule):
    """Enriched Rule with resolved workspace URLs."""
