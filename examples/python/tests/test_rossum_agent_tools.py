"""Tests for parse_annotation_content tool"""

import json
from collections import defaultdict

import pytest

from rossum_agent_tools import parse_annotation_content

# Sample annotation content structure (simplified)
sample_content = [
    {
        "category": "section",
        "schema_id": "header_section",
        "children": [
            {"category": "datapoint", "schema_id": "sender_name", "content": {"value": "Acme Corporation", "page": 1}},
            {"category": "datapoint", "schema_id": "invoice_date", "content": {"value": "2025-01-15", "page": 1}},
        ],
    },
    {"category": "datapoint", "schema_id": "amount_total", "content": {"value": "1500.00", "page": 1}},
    {
        "category": "section",
        "schema_id": "line_items_section",
        "children": [
            {
                "category": "multivalue",
                "schema_id": "line_items",
                "children": [
                    {
                        "category": "tuple",
                        "children": [
                            {
                                "category": "datapoint",
                                "schema_id": "item_description",
                                "content": {"value": "Widget A"},
                            },
                            {"category": "datapoint", "schema_id": "item_amount", "content": {"value": "500.00"}},
                        ],
                    },
                    {
                        "category": "tuple",
                        "children": [
                            {
                                "category": "datapoint",
                                "schema_id": "item_description",
                                "content": {"value": "Widget B"},
                            },
                            {"category": "datapoint", "schema_id": "item_amount", "content": {"value": "1000.00"}},
                        ],
                    },
                ],
            }
        ],
    },
]

# Real Rossum structure with complete metadata
real_structure = [
    {
        "id": 2641983912,
        "category": "section",
        "schema_id": "line_items_section",
        "children": [
            {
                "id": 2641983915,
                "category": "multivalue",
                "schema_id": "line_items",
                "children": [
                    {
                        "id": 2641983917,
                        "category": "tuple",
                        "schema_id": "line_item",
                        "children": [
                            {
                                "id": 2641983959,
                                "category": "datapoint",
                                "schema_id": "item_description",
                                "content": {"value": "API Integration Development"},
                            },
                            {
                                "id": 2641983960,
                                "category": "datapoint",
                                "schema_id": "item_quantity",
                                "content": {"value": "17"},
                            },
                            {
                                "id": 2641983967,
                                "category": "datapoint",
                                "schema_id": "item_amount_total",
                                "content": {"value": "2 147.29"},
                            },
                        ],
                    },
                    {
                        "id": 2641983918,
                        "category": "tuple",
                        "schema_id": "line_item",
                        "children": [
                            {
                                "id": 2641983969,
                                "category": "datapoint",
                                "schema_id": "item_description",
                                "content": {"value": "System Architecture Design"},
                            },
                            {
                                "id": 2641983970,
                                "category": "datapoint",
                                "schema_id": "item_quantity",
                                "content": {"value": "5"},
                            },
                            {
                                "id": 2641983977,
                                "category": "datapoint",
                                "schema_id": "item_amount_total",
                                "content": {"value": "660.15"},
                            },
                        ],
                    },
                    {
                        "id": 2641983919,
                        "category": "tuple",
                        "schema_id": "line_item",
                        "children": [
                            {
                                "id": 2641983979,
                                "category": "datapoint",
                                "schema_id": "item_description",
                                "content": {"value": "DevOps Automation Setup"},
                            },
                            {
                                "id": 2641983980,
                                "category": "datapoint",
                                "schema_id": "item_quantity",
                                "content": {"value": "24"},
                            },
                            {
                                "id": 2641983987,
                                "category": "datapoint",
                                "schema_id": "item_amount_total",
                                "content": {"value": "2 782.13"},
                            },
                        ],
                    },
                ],
            }
        ],
    }
]


def test_extract_all_datapoints() -> None:
    """Test extracting all datapoints from simple structure"""
    result_json = parse_annotation_content(json.dumps(sample_content), "extract_all_datapoints")
    result = json.loads(result_json)

    assert result["sender_name"] == "Acme Corporation"
    assert result["invoice_date"] == "2025-01-15"
    assert result["amount_total"] == "1500.00"


def test_get_single_datapoint() -> None:
    """Test getting a single datapoint by schema_id"""
    result_json = parse_annotation_content(json.dumps(sample_content), "get_datapoint_value", schema_id="sender_name")
    result = json.loads(result_json)

    assert result["value"] == "Acme Corporation"
    assert result["schema_id"] == "sender_name"


def test_extract_line_items_simple() -> None:
    """Test extracting line items from simple structure"""
    result_json = parse_annotation_content(
        json.dumps(sample_content), "extract_line_items", multivalue_schema_id="line_items"
    )
    result = json.loads(result_json)

    assert len(result) == 2
    assert result[0]["item_description"] == "Widget A"
    assert result[0]["item_amount"] == "500.00"
    assert result[1]["item_description"] == "Widget B"
    assert result[1]["item_amount"] == "1000.00"


def test_extract_line_items_real_structure() -> None:
    """Test extracting line items from real Rossum structure"""
    result_json = parse_annotation_content(
        json.dumps(real_structure), "extract_line_items", multivalue_schema_id="line_items"
    )
    result = json.loads(result_json)

    assert len(result) == 3
    assert result[0]["item_description"] == "API Integration Development"
    assert result[0]["item_quantity"] == "17"
    assert result[0]["item_amount_total"] == "2 147.29"

    assert result[1]["item_description"] == "System Architecture Design"
    assert result[1]["item_quantity"] == "5"
    assert result[1]["item_amount_total"] == "660.15"

    assert result[2]["item_description"] == "DevOps Automation Setup"
    assert result[2]["item_quantity"] == "24"
    assert result[2]["item_amount_total"] == "2 782.13"


def test_line_items_aggregation() -> None:
    """Test aggregating line items by description - demonstrates correct approach"""
    result_json = parse_annotation_content(
        json.dumps(real_structure), "extract_line_items", multivalue_schema_id="line_items"
    )
    line_items = json.loads(result_json)

    # Aggregate by description
    aggregated = defaultdict(float)
    for item in line_items:
        desc = item.get("item_description")
        amount_str = item.get("item_amount_total", "0")

        # Convert to float, handling spaces in numbers
        try:
            amount = float(amount_str.replace(" ", "").replace(",", ""))
        except (ValueError, AttributeError):
            amount = 0.0

        aggregated[desc] += amount

    assert aggregated["API Integration Development"] == pytest.approx(2147.29)
    assert aggregated["System Architecture Design"] == pytest.approx(660.15)
    assert aggregated["DevOps Automation Setup"] == pytest.approx(2782.13)


def test_extract_all_datapoints_loses_line_item_associations() -> None:
    """Test that extract_all_datapoints loses line item associations (anti-pattern)"""
    result_json = parse_annotation_content(json.dumps(real_structure), "extract_all_datapoints")
    result = json.loads(result_json)

    # This will only have the LAST occurrence of each field
    assert result["item_description"] == "DevOps Automation Setup"
    assert result["item_quantity"] == "24"
    assert result["item_amount_total"] == "2 782.13"

    # Note: The first two line items are lost due to dict overwriting


def test_error_handling_missing_schema_id() -> None:
    """Test error handling for missing schema_id"""
    result_json = parse_annotation_content(json.dumps(sample_content), "get_datapoint_value")
    result = json.loads(result_json)

    assert "error" in result
    assert "schema_id" in result["error"].lower()


def test_error_handling_missing_multivalue_schema_id() -> None:
    """Test error handling for missing multivalue_schema_id"""
    result_json = parse_annotation_content(json.dumps(sample_content), "extract_line_items")
    result = json.loads(result_json)

    assert "error" in result
    assert "multivalue_schema_id" in result["error"].lower()


def test_error_handling_unknown_operation() -> None:
    """Test error handling for unknown operation"""
    result_json = parse_annotation_content(json.dumps(sample_content), "unknown_operation")
    result = json.loads(result_json)

    assert "error" in result
    assert "unknown" in result["error"].lower() or "operation" in result["error"].lower()


def test_error_handling_invalid_json() -> None:
    """Test error handling for invalid JSON"""
    result_json = parse_annotation_content("not valid json", "extract_all_datapoints")
    result = json.loads(result_json)

    assert "error" in result
