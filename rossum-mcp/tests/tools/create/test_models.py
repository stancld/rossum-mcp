"""Tests for schema dataclass models (create layer)."""

from __future__ import annotations

from rossum_mcp.tools.models import (
    SchemaDatapoint,
    SchemaMultivalue,
    SchemaTuple,
)


class TestSchemaDataclasses:
    """Tests for schema dataclass types."""

    def test_schema_datapoint_to_dict(self) -> None:
        """Test SchemaDatapoint converts to dict excluding None values."""
        datapoint = SchemaDatapoint(label="Invoice Number", type="string", score_threshold=0.8)
        result = datapoint.to_dict()

        assert result["label"] == "Invoice Number"
        assert result["type"] == "string"
        assert result["category"] == "datapoint"
        assert result["score_threshold"] == 0.8
        assert "rir_field_names" not in result
        assert "formula" not in result

    def test_schema_datapoint_with_formula(self) -> None:
        """Test SchemaDatapoint with formula field."""
        datapoint = SchemaDatapoint(label="Total", type="number", formula="field_a + field_b")
        result = datapoint.to_dict()

        assert result["formula"] == "field_a + field_b"
        assert result["type"] == "number"

    def test_schema_tuple_to_dict(self) -> None:
        """Test SchemaTuple converts to dict with nested children."""
        tuple_node = SchemaTuple(
            id="line_item",
            label="Line Item",
            children=[
                SchemaDatapoint(label="Description", type="string"),
                SchemaDatapoint(label="Amount", type="number"),
            ],
        )
        result = tuple_node.to_dict()

        assert result["id"] == "line_item"
        assert result["label"] == "Line Item"
        assert result["category"] == "tuple"
        assert len(result["children"]) == 2
        assert result["children"][0]["label"] == "Description"
        assert result["children"][1]["label"] == "Amount"

    def test_schema_multivalue_with_tuple(self) -> None:
        """Test SchemaMultivalue with tuple children (table structure)."""
        multivalue = SchemaMultivalue(
            label="Line Items",
            children=SchemaTuple(
                id="line_item",
                label="Line Item",
                children=[
                    SchemaDatapoint(label="Description", type="string"),
                    SchemaDatapoint(label="Amount", type="number"),
                ],
            ),
        )
        result = multivalue.to_dict()

        assert result["label"] == "Line Items"
        assert result["category"] == "multivalue"
        assert result["children"]["id"] == "line_item"
        assert result["children"]["label"] == "Line Item"
        assert result["children"]["category"] == "tuple"

    def test_schema_multivalue_with_datapoint(self) -> None:
        """Test SchemaMultivalue with single datapoint (repeating field)."""
        multivalue = SchemaMultivalue(
            label="PO Numbers",
            children=SchemaDatapoint(label="PO Number", type="string"),
        )
        result = multivalue.to_dict()

        assert result["label"] == "PO Numbers"
        assert result["category"] == "multivalue"
        assert result["children"]["label"] == "PO Number"
        assert result["children"]["category"] == "datapoint"

    def test_schema_tuple_with_hidden_true(self) -> None:
        """Test SchemaTuple with hidden=True includes hidden field in output."""
        tuple_node = SchemaTuple(
            id="hidden_tuple",
            label="Hidden Tuple",
            children=[SchemaDatapoint(label="Field", type="string")],
            hidden=True,
        )
        result = tuple_node.to_dict()

        assert result["id"] == "hidden_tuple"
        assert result["hidden"] is True
        assert result["category"] == "tuple"

    def test_schema_datapoint_with_lookup_matching(self) -> None:
        """Test SchemaDatapoint with lookup field matching configuration."""
        matching = {
            "type": "master_data_hub",
            "configuration": {
                "dataset": "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b",
                "queries": [
                    {
                        "aggregate": [
                            {"$match": {"Name": "$sender_name"}},
                            {"$limit": 5},
                            {"$project": {"label": "$Name", "value": "$ID"}},
                        ]
                    }
                ],
                "variables": {"sender_name": {"__formula": 'default_to(field.sender_name, "UNKNOWN")'}},
            },
        }
        datapoint = SchemaDatapoint(
            label="Vendor Match",
            type="enum",
            ui_configuration={"type": "lookup", "edit": "enabled"},
            matching=matching,
            enum_value_type="string",
            options=[],
        )
        result = datapoint.to_dict()

        assert result["type"] == "enum"
        assert result["ui_configuration"] == {"type": "lookup", "edit": "enabled"}
        assert result["matching"]["type"] == "master_data_hub"
        assert result["matching"]["configuration"]["dataset"].startswith("imported-")
        assert len(result["matching"]["configuration"]["queries"]) == 1
        assert result["enum_value_type"] == "string"
        assert result["options"] == []

    def test_schema_multivalue_all_optional_fields(self) -> None:
        """Test SchemaMultivalue with all optional fields set."""
        multivalue = SchemaMultivalue(
            label="Line Items",
            children=SchemaDatapoint(label="Item", type="string"),
            id="line_items_mv",
            rir_field_names=["line_items"],
            min_occurrences=1,
            max_occurrences=10,
            hidden=True,
        )
        result = multivalue.to_dict()

        assert result["id"] == "line_items_mv"
        assert result["rir_field_names"] == ["line_items"]
        assert result["min_occurrences"] == 1
        assert result["max_occurrences"] == 10
        assert result["hidden"] is True
        assert result["category"] == "multivalue"
