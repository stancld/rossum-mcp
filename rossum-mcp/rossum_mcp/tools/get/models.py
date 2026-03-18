from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SchemaTreeNode:
    """Lightweight schema node for tree structure display."""

    id: str
    label: str
    category: str
    type: str | None = None
    required: bool = False
    hidden: bool = False
    children: list[SchemaTreeNode] | None = None

    def to_dict(self) -> dict:
        result: dict = {
            "id": self.id,
            "label": self.label,
            "category": self.category,
            "required": self.required,
            "hidden": self.hidden,
        }
        if self.type:
            result["type"] = self.type
        if self.children:
            result["children"] = [child.to_dict() for child in self.children]
        return result
