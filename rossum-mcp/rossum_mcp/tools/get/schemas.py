from __future__ import annotations

from rossum_api.models.schema import Datapoint, Multivalue, Schema, Tuple

from rossum_mcp.tools.get.models import SchemaTreeNode


def _node_from_datapoint(dp: Datapoint) -> SchemaTreeNode:
    return SchemaTreeNode(
        id=dp.id,
        label=dp.label or "",
        category=dp.category,
        type=dp.type,
        required=dp.constraints.get("required", False) if dp.constraints else False,
        hidden=dp.hidden,
    )


def _node_from_multivalue(mv: Multivalue) -> SchemaTreeNode:
    return SchemaTreeNode(
        id=mv.id,
        label=mv.label or "",
        category=mv.category,
        hidden=mv.hidden,
        children=[_node_from_child(mv.children)] if mv.children is not None else None,
    )


def _node_from_tuple(tpl: Tuple) -> SchemaTreeNode:
    return SchemaTreeNode(
        id=tpl.id,
        label=tpl.label or "",
        category=tpl.category,
        hidden=tpl.hidden,
        children=[_node_from_datapoint(dp) for dp in tpl.children] or None,
    )


def _node_from_child(child: Datapoint | Multivalue | Tuple) -> SchemaTreeNode:
    if isinstance(child, Datapoint):
        return _node_from_datapoint(child)
    if isinstance(child, Multivalue):
        return _node_from_multivalue(child)
    return _node_from_tuple(child)


def extract_schema_tree(schema: Schema) -> list[dict]:
    return [
        SchemaTreeNode(
            id=section.id,
            label=section.label or "",
            category=section.category,
            children=[_node_from_child(c) for c in section.children] or None,
        ).to_dict()
        for section in schema.content
    ]
