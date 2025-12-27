from __future__ import annotations

import difflib
import json
import sys
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ANSI color codes
_RED = "\033[91m"
_GREEN = "\033[92m"
_CYAN = "\033[96m"
_RESET = "\033[0m"


def _format_unified_diff(
    source_value: Any,
    target_value: Any,
    field_name: str,
    use_color: bool = False,
    from_label: str = "remote",
    to_label: str = "local",
) -> str:
    """Format a unified diff between source and target values.

    Args:
        source_value: The source value to compare
        target_value: The target value to compare
        field_name: Name of the field being compared
        use_color: If True, add ANSI color codes (red for deletions, green for additions)
        from_label: Label for the source (e.g., "local", "source")
        to_label: Label for the target (e.g., "remote", "target")
    """
    source_str = json.dumps(source_value, indent=2, sort_keys=True, default=str)
    target_str = json.dumps(target_value, indent=2, sort_keys=True, default=str)

    source_lines = source_str.splitlines(keepends=True)
    target_lines = target_str.splitlines(keepends=True)

    diff = difflib.unified_diff(
        source_lines,
        target_lines,
        fromfile=f"{from_label}/{field_name}",
        tofile=f"{to_label}/{field_name}",
        lineterm="",
    )

    if not use_color:
        return "".join(diff)

    # Apply colors line by line
    colored_lines = []
    for line in diff:
        if line.startswith("---") or line.startswith("+++"):
            colored_lines.append(f"{_CYAN}{line}{_RESET}")
        elif line.startswith("-"):
            colored_lines.append(f"{_RED}{line}{_RESET}")
        elif line.startswith("+"):
            colored_lines.append(f"{_GREEN}{line}{_RESET}")
        elif line.startswith("@@"):
            colored_lines.append(f"{_CYAN}{line}{_RESET}")
        else:
            colored_lines.append(line)

    return "".join(colored_lines)


def _is_tty() -> bool:
    """Check if stdout is connected to a terminal."""
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


class ObjectType(str, Enum):
    """Supported Rossum object types."""

    WORKSPACE = "workspace"
    QUEUE = "queue"
    SCHEMA = "schema"
    INBOX = "inbox"
    HOOK = "hook"
    CONNECTOR = "connector"
    ENGINE = "engine"
    EMAIL_TEMPLATE = "email_template"
    RULE = "rule"


class ObjectMeta(BaseModel):
    pulled_at: datetime = Field(description="When the object was pulled from remote")
    remote_modified_at: datetime | None = Field(default=None, description="Remote modified_at timestamp at pull time")
    object_type: ObjectType = Field(description="Type of the Rossum object")
    object_id: int = Field(description="Remote object ID")


class LocalObject(BaseModel):
    meta: ObjectMeta = Field(alias="_meta")
    data: dict[str, Any] = Field(description="The actual object payload from API")

    model_config = {"populate_by_name": True}


class DiffStatus(str, Enum):
    """Status of an object when comparing local vs remote."""

    UNCHANGED = "unchanged"
    LOCAL_MODIFIED = "local_modified"
    REMOTE_MODIFIED = "remote_modified"
    CONFLICT = "conflict"
    LOCAL_ONLY = "local_only"
    REMOTE_ONLY = "remote_only"


class FieldDiff(BaseModel):
    """Difference in a single field between local and remote."""

    field: str
    source_value: Any
    target_value: Any


class ObjectDiff(BaseModel):
    """Difference information for a single object."""

    object_type: ObjectType
    object_id: int
    name: str
    status: DiffStatus
    local_modified_at: datetime | None = None
    remote_modified_at: datetime | None = None
    changed_fields: list[str] = Field(default_factory=list)
    field_diffs: list[FieldDiff] = Field(default_factory=list)


class DiffResult(BaseModel):
    """Result of comparing local workspace with remote."""

    objects: list[ObjectDiff] = Field(default_factory=list)
    total_unchanged: int = 0
    total_local_modified: int = 0
    total_remote_modified: int = 0
    total_conflicts: int = 0

    def _format_object_diffs(self, obj: ObjectDiff, use_color: bool) -> list[str]:
        """Format field diffs for a single object."""
        lines: list[str] = []
        lines.append(f"\n### {obj.object_type.value}: {obj.name} ({obj.object_id})")
        for diff in obj.field_diffs:
            lines.append(f"\n#### {diff.field}")
            if not use_color:
                lines.append("```diff")
            lines.append(_format_unified_diff(diff.source_value, diff.target_value, diff.field, use_color=use_color))
            if not use_color:
                lines.append("```")
        return lines

    def _format_section(self, status: DiffStatus, header: str, use_color: bool) -> list[str]:
        """Format a section of objects with a given status."""
        lines: list[str] = []
        matching = [obj for obj in self.objects if obj.status == status]
        if matching:
            lines.append(f"\n## {header}")
            for obj in matching:
                lines.extend(self._format_object_diffs(obj, use_color))
        return lines

    def summary(self, color: bool | None = None) -> str:
        """Human-readable summary of the diff with unified diff format.

        Args:
            color: If True, use ANSI colors. If False, no colors. If None (default),
                   auto-detect based on whether stdout is a TTY.
        """
        use_color = _is_tty() if color is None else color
        local_only_count = sum(1 for obj in self.objects if obj.status == DiffStatus.LOCAL_ONLY)

        lines = ["# Diff Summary", ""]
        lines.append(f"- Unchanged: {self.total_unchanged}")
        lines.append(f"- Local modified: {self.total_local_modified}")
        lines.append(f"- Remote modified: {self.total_remote_modified}")
        lines.append(f"- Conflicts: {self.total_conflicts}")
        lines.append(f"- Local only: {local_only_count}")

        lines.extend(self._format_section(DiffStatus.LOCAL_MODIFIED, "Local Changes (ready to push)", use_color))
        lines.extend(self._format_section(DiffStatus.REMOTE_MODIFIED, "Remote Changes (pull to update)", use_color))
        lines.extend(self._format_section(DiffStatus.CONFLICT, "Conflicts (require resolution)", use_color))

        if local_only_count > 0:
            lines.append("\n## Local Only (not on remote)")
            for obj in self.objects:
                if obj.status == DiffStatus.LOCAL_ONLY:
                    lines.append(f"- {obj.object_type.value}: {obj.name} ({obj.object_id})")

        return "\n".join(lines)

    def to_markdown(self) -> str:
        """Alias for summary() for agent integration - always without colors."""
        return self.summary(color=False)


class PushResult(BaseModel):
    """Result of pushing changes to remote."""

    pushed: list[tuple[ObjectType, int, str]] = Field(default_factory=list)
    skipped: list[tuple[ObjectType, int, str, str]] = Field(default_factory=list)
    failed: list[tuple[ObjectType, int, str, str]] = Field(default_factory=list)

    def summary(self) -> str:
        """Human-readable summary of the push."""
        lines = ["# Push Summary", ""]
        lines.append(f"- Pushed: {len(self.pushed)}")
        lines.append(f"- Skipped: {len(self.skipped)}")
        lines.append(f"- Failed: {len(self.failed)}")

        if self.pushed:
            lines.append("\n## Pushed")
            for obj_type, obj_id, name in self.pushed:
                lines.append(f"- {obj_type.value}: {name} ({obj_id})")

        if self.skipped:
            lines.append("\n## Skipped")
            for obj_type, obj_id, name, reason in self.skipped:
                lines.append(f"- {obj_type.value}: {name} ({obj_id}) - {reason}")

        if self.failed:
            lines.append("\n## Failed")
            for obj_type, obj_id, name, error in self.failed:
                lines.append(f"- {obj_type.value}: {name} ({obj_id}) - {error}")

        return "\n".join(lines)


class PullResult(BaseModel):
    """Result of pulling objects from remote."""

    organization_name: str | None = None
    workspace_name: str | None = None
    pulled: list[tuple[ObjectType, int, str]] = Field(default_factory=list)
    skipped: list[tuple[ObjectType, int, str, str]] = Field(default_factory=list)

    def summary(self) -> str:
        """Human-readable summary of the pull."""
        lines = ["# Pull Summary", ""]
        if self.organization_name:
            lines.append(f"- Organization: {self.organization_name}")
        if self.workspace_name:
            lines.append(f"- Workspace: {self.workspace_name}")
        lines.append(f"- Pulled: {len(self.pulled)}")
        lines.append(f"- Skipped: {len(self.skipped)}")

        if self.pulled:
            lines.append("\n## Pulled")
            for obj_type, obj_id, name in self.pulled:
                lines.append(f"- {obj_type.value}: {name} ({obj_id})")

        return "\n".join(lines)


class IdMapping(BaseModel):
    """Mapping of source IDs to target IDs for cross-org deployment."""

    source_org_id: int
    target_org_id: int
    mappings: dict[str, dict[int, int]] = Field(default_factory=dict)

    def add(self, obj_type: ObjectType, source_id: int, target_id: int) -> None:
        """Add a source->target ID mapping."""
        type_key = obj_type.value
        if type_key not in self.mappings:
            self.mappings[type_key] = {}
        self.mappings[type_key][source_id] = target_id

    def get(self, obj_type: ObjectType, source_id: int) -> int | None:
        """Get target ID for a source ID."""
        type_key = obj_type.value
        return self.mappings.get(type_key, {}).get(source_id)

    def get_all(self, obj_type: ObjectType) -> dict[int, int]:
        """Get all mappings for an object type."""
        return self.mappings.get(obj_type.value, {})

    def reverse(self) -> IdMapping:
        """Return a new IdMapping with source and target swapped."""
        reversed_mappings: dict[str, dict[int, int]] = {}
        for type_key, type_mappings in self.mappings.items():
            reversed_mappings[type_key] = {v: k for k, v in type_mappings.items()}
        return IdMapping(
            source_org_id=self.target_org_id,
            target_org_id=self.source_org_id,
            mappings=reversed_mappings,
        )


class CopyResult(BaseModel):
    """Result of copying objects between organizations."""

    created: list[tuple[ObjectType, int, int, str]] = Field(default_factory=list)
    skipped: list[tuple[ObjectType, int, str, str]] = Field(default_factory=list)
    failed: list[tuple[ObjectType, int, str, str]] = Field(default_factory=list)
    id_mapping: IdMapping | None = None

    def summary(self) -> str:
        """Human-readable summary of the copy operation."""
        lines = ["# Copy Summary", ""]
        lines.append(f"- Created: {len(self.created)}")
        lines.append(f"- Skipped: {len(self.skipped)}")
        lines.append(f"- Failed: {len(self.failed)}")

        if self.created:
            lines.append("\n## Created")
            for obj_type, source_id, target_id, name in self.created:
                lines.append(f"- {obj_type.value}: {name} (source: {source_id} → target: {target_id})")

        if self.skipped:
            lines.append("\n## Skipped")
            for obj_type, obj_id, name, reason in self.skipped:
                lines.append(f"- {obj_type.value}: {name} ({obj_id}) - {reason}")

        if self.failed:
            lines.append("\n## Failed")
            for obj_type, obj_id, name, error in self.failed:
                lines.append(f"- {obj_type.value}: {name} ({obj_id}) - {error}")

        return "\n".join(lines)


class DeployResult(BaseModel):
    """Result of deploying local changes to a target organization."""

    created: list[tuple[ObjectType, int, str]] = Field(default_factory=list)
    updated: list[tuple[ObjectType, int, str]] = Field(default_factory=list)
    skipped: list[tuple[ObjectType, int, str, str]] = Field(default_factory=list)
    failed: list[tuple[ObjectType, int, str, str]] = Field(default_factory=list)

    def summary(self) -> str:
        """Human-readable summary of the deploy."""
        lines = ["# Deploy Summary", ""]
        lines.append(f"- Created: {len(self.created)}")
        lines.append(f"- Updated: {len(self.updated)}")
        lines.append(f"- Skipped: {len(self.skipped)}")
        lines.append(f"- Failed: {len(self.failed)}")

        if self.created:
            lines.append("\n## Created")
            for obj_type, obj_id, name in self.created:
                lines.append(f"- {obj_type.value}: {name} ({obj_id})")

        if self.updated:
            lines.append("\n## Updated")
            for obj_type, obj_id, name in self.updated:
                lines.append(f"- {obj_type.value}: {name} ({obj_id})")

        if self.skipped:
            lines.append("\n## Skipped")
            for obj_type, obj_id, name, reason in self.skipped:
                lines.append(f"- {obj_type.value}: {name} ({obj_id}) - {reason}")

        if self.failed:
            lines.append("\n## Failed")
            for obj_type, obj_id, name, error in self.failed:
                lines.append(f"- {obj_type.value}: {name} ({obj_id}) - {error}")

        return "\n".join(lines)


class ObjectCompare(BaseModel):
    """Comparison between a source object and its copied target."""

    object_type: ObjectType
    source_id: int
    target_id: int
    name: str
    is_identical: bool = True
    field_diffs: list[FieldDiff] = Field(default_factory=list)


class CompareResult(BaseModel):
    """Result of comparing source workspace with its copy (target)."""

    source_workspace_id: int
    target_workspace_id: int
    objects: list[ObjectCompare] = Field(default_factory=list)
    source_only: list[tuple[ObjectType, int, str]] = Field(default_factory=list)
    target_only: list[tuple[ObjectType, int, str]] = Field(default_factory=list)
    total_identical: int = 0
    total_different: int = 0

    def summary(self, color: bool | None = None) -> str:
        """Human-readable summary of the comparison with unified diff format.

        Args:
            color: If True, use ANSI colors. If False, no colors. If None (default),
                   auto-detect based on whether stdout is a TTY.
        """
        use_color = _is_tty() if color is None else color

        lines = [
            "# Workspace Comparison",
            "",
            f"Source workspace: {self.source_workspace_id}",
            f"Target workspace: {self.target_workspace_id}",
            "",
            f"- Identical: {self.total_identical}",
            f"- Different: {self.total_different}",
            f"- Source only: {len(self.source_only)}",
            f"- Target only: {len(self.target_only)}",
        ]

        if self.total_different > 0:
            lines.append("\n## Differences")
            for obj in self.objects:
                if not obj.is_identical:
                    lines.append(
                        f"\n### {obj.object_type.value}: {obj.name} "
                        f"(source: {obj.source_id} → target: {obj.target_id})"
                    )
                    for diff in obj.field_diffs:
                        lines.append(f"\n#### {diff.field}")
                        if not use_color:
                            lines.append("```diff")
                        unified_diff = _format_unified_diff(
                            diff.source_value,
                            diff.target_value,
                            diff.field,
                            use_color=use_color,
                            from_label="source",
                            to_label="target",
                        )
                        lines.append(unified_diff)
                        if not use_color:
                            lines.append("```")

        if self.source_only:
            lines.append("\n## Source Only (not in target)")
            for obj_type, obj_id, name in self.source_only:
                lines.append(f"- {obj_type.value}: {name} ({obj_id})")

        if self.target_only:
            lines.append("\n## Target Only (not in source)")
            for obj_type, obj_id, name in self.target_only:
                lines.append(f"- {obj_type.value}: {name} ({obj_id})")

        return "\n".join(lines)

    def to_markdown(self) -> str:
        """Alias for summary() for agent integration - always without colors."""
        return self.summary(color=False)
