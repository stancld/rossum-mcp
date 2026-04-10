"""Base model mixins and protocols."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Generic, Protocol, TypeVar

if TYPE_CHECKING:
    from typing import Any, Self


class RossumResource(Protocol):
    __dataclass_fields__: ClassVar[dict[str, dataclasses.Field]]


T = TypeVar("T", bound=RossumResource)


@dataclass
class RossumResourceWithResolvedWorkspaces(Generic[T]):  # noqa: UP046 - PEP 695 breaks sphinx-autodoc-typehints with PEP 563
    workspaces: list[str] = field(default_factory=list)

    @classmethod
    def from_base(cls, resource: T, workspaces: list[str]) -> Self:
        base_fields: dict[str, Any] = {f.name: getattr(resource, f.name) for f in dataclasses.fields(resource)}
        return cls(**base_fields, workspaces=workspaces)
