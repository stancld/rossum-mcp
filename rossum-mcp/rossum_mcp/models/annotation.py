"""Annotation models."""

from __future__ import annotations

from dataclasses import dataclass

from rossum_api.models.annotation import Annotation as RossumAnnotation

from rossum_mcp.models.base import RossumResourceWithResolvedWorkspaces


@dataclass
class Annotation(RossumResourceWithResolvedWorkspaces[RossumAnnotation], RossumAnnotation):
    """Enriched Annotation with resolved workspace URLs."""
