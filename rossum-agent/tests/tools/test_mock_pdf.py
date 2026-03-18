"""Tests for the generate_mock_pdf tool."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from rossum_agent.tools.core import AgentContext, set_context
from rossum_agent.tools.mock_pdf import (
    _apply_base_tax_split,
    _build_header_rir_resolver,
    _find_item_column,
    _find_item_total_key,
    _generate_value_for_field,
    _is_hidden,
    _is_line_item_field,
    _make_amounts_consistent,
    _make_line_items_internally_consistent,
    _render_pdf,
    generate_mock_pdf,
)

if TYPE_CHECKING:
    from pathlib import Path


# -- Sample field fixtures --


def _field(
    field_id: str, label: str, rir: list[str] | None = None, field_type: str = "string", **kwargs: object
) -> dict:
    return {"id": field_id, "label": label, "type": field_type, "rir_field_names": rir or [], **kwargs}


INVOICE_FIELDS = [
    _field("sender_name", "Vendor Name", ["sender_name"]),
    _field("invoice_id", "Invoice Number", ["invoice_id"]),
    _field("date_issue", "Issue Date", ["date_issue"], "date"),
    _field("date_due", "Due Date", ["date_due"], "date"),
    _field("amount_total", "Total Amount", ["amount_total"], "number"),
    _field("amount_total_base", "Subtotal", ["amount_total_base"], "number"),
    _field("amount_total_tax", "Tax", ["amount_total_tax"], "number"),
    _field("currency", "Currency", ["currency"]),
    _field("item_description", "Description", ["item_description"]),
    _field("item_quantity", "Qty", ["item_quantity"], "number"),
    _field("item_amount_total", "Amount", ["item_amount_total"], "number"),
]


class TestValueGeneration:
    """Tests for _generate_value_for_field."""

    def test_invoice_id_format(self) -> None:
        field = _field("invoice_id", "Invoice Number", ["invoice_id"])
        value = _generate_value_for_field(field)
        assert value.startswith("INV-")
        parts = value.split("-")
        assert len(parts) == 3
        assert parts[1].isdigit()
        assert len(parts[2]) == 5

    def test_date_issue_iso_format(self) -> None:
        field = _field("date_issue", "Issue Date", ["date_issue"], "date")
        value = _generate_value_for_field(field)
        parts = value.split("-")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_sender_name_from_pool(self) -> None:
        field = _field("sender_name", "Vendor", ["sender_name"])
        value = _generate_value_for_field(field)
        assert isinstance(value, str)
        assert len(value) > 0

    def test_amount_is_numeric(self) -> None:
        field = _field("amount_total", "Total", ["amount_total"], "number")
        value = _generate_value_for_field(field)
        float(value)  # should not raise

    def test_vat_id_format(self) -> None:
        field = _field("sender_vat_id", "VAT ID", ["sender_vat_id"])
        value = _generate_value_for_field(field)
        assert value.startswith("CZ")
        assert len(value) == 10

    def test_fallback_by_type_number(self) -> None:
        field = _field("custom_amount", "Custom Amount", [], "number")
        value = _generate_value_for_field(field)
        float(value)  # should not raise

    def test_fallback_by_type_date(self) -> None:
        field = _field("custom_date", "Custom Date", [], "date")
        value = _generate_value_for_field(field)
        parts = value.split("-")
        assert len(parts) == 3

    def test_fallback_by_type_enum(self) -> None:
        field = {
            "id": "payment_method",
            "label": "Payment Method",
            "type": "enum",
            "rir_field_names": [],
            "options": [{"value": "bank_transfer", "label": "Bank Transfer"}],
        }
        value = _generate_value_for_field(field)
        assert value == "bank_transfer"

    def test_fallback_by_type_enum_empty_options(self) -> None:
        field = {"id": "status", "label": "Status", "type": "enum", "rir_field_names": [], "options": []}
        value = _generate_value_for_field(field)
        assert value == "option_1"

    def test_fallback_string_default(self) -> None:
        field = _field("unknown_field", "Unknown Field", [])
        value = _generate_value_for_field(field)
        assert value == "Sample Unknown Field"

    def test_field_id_fallback_when_no_rir(self) -> None:
        """Field id matches a known generator even without rir_field_names."""
        field = _field("invoice_id", "Invoice Number", [])
        value = _generate_value_for_field(field)
        assert value.startswith("INV-")


class TestFieldClassification:
    """Tests for _is_line_item_field."""

    def test_item_prefix_id(self) -> None:
        assert _is_line_item_field({"id": "item_description", "rir_field_names": []}) is True

    def test_item_prefix_rir(self) -> None:
        assert _is_line_item_field({"id": "description", "rir_field_names": ["item_description"]}) is True

    def test_header_field(self) -> None:
        assert _is_line_item_field({"id": "invoice_id", "rir_field_names": ["invoice_id"]}) is False

    def test_no_rir_no_item_prefix(self) -> None:
        assert _is_line_item_field({"id": "amount_total", "rir_field_names": []}) is False

    def test_empty_field(self) -> None:
        assert _is_line_item_field({}) is False


class TestAmountConsistency:
    """Tests for _make_amounts_consistent."""

    def test_total_equals_sum_of_items(self) -> None:
        header_fields = [
            _field("amount_total", "Total", ["amount_total"], "number"),
        ]
        header_values = {"amount_total": "999.99"}
        line_items = [
            {"item_amount_total": "100.00"},
            {"item_amount_total": "200.50"},
            {"item_amount_total": "50.25"},
        ]
        _make_amounts_consistent(header_values, line_items, header_fields)
        assert float(header_values["amount_total"]) == 350.75

    def test_base_plus_tax_equals_total(self) -> None:
        header_fields = [
            _field("amount_total", "Total", ["amount_total"], "number"),
            _field("amount_total_base", "Base", ["amount_total_base"], "number"),
            _field("amount_total_tax", "Tax", ["amount_total_tax"], "number"),
        ]
        header_values = {"amount_total": "0", "amount_total_base": "0", "amount_total_tax": "0"}
        line_items = [{"item_amount_total": "121.00"}]
        _make_amounts_consistent(header_values, line_items, header_fields)

        total = float(header_values["amount_total"])
        base = float(header_values["amount_total_base"])
        tax = float(header_values["amount_total_tax"])
        assert abs(total - (base + tax)) < 0.01

    def test_amount_due_matches_total(self) -> None:
        header_fields = [
            _field("amount_total", "Total", ["amount_total"], "number"),
            _field("amount_due", "Due", ["amount_due"], "number"),
        ]
        header_values = {"amount_total": "0", "amount_due": "0"}
        line_items = [{"item_amount_total": "500.00"}]
        _make_amounts_consistent(header_values, line_items, header_fields)
        assert header_values["amount_total"] == header_values["amount_due"]

    def test_no_line_items_no_change(self) -> None:
        header_fields = [_field("amount_total", "Total", ["amount_total"], "number")]
        header_values = {"amount_total": "999.99"}
        _make_amounts_consistent(header_values, [], header_fields)
        assert header_values["amount_total"] == "999.99"

    def test_rir_name_mapping(self) -> None:
        """Fields matched by rir_field_name even when id differs."""
        header_fields = [
            {"id": "total_amount", "label": "Total", "type": "number", "rir_field_names": ["amount_total"]},
        ]
        header_values = {"total_amount": "0"}
        line_items = [{"item_amount_total": "200.00"}, {"item_amount_total": "300.00"}]
        _make_amounts_consistent(header_values, line_items, header_fields)
        assert float(header_values["total_amount"]) == 500.00


class TestPdfRendering:
    """Tests for _render_pdf."""

    def test_returns_valid_pdf_bytes(self) -> None:
        header_values = {"invoice_id": "INV-2024-00001", "sender_name": "Acme Corp"}
        pdf_bytes = _render_pdf(
            "invoice",
            header_values,
            [],
            [_field("invoice_id", "Invoice"), _field("sender_name", "Vendor")],
            [],
        )
        assert pdf_bytes[:5] == b"%PDF-"

    def test_all_document_types(self) -> None:
        for doc_type in ["invoice", "purchase_order", "receipt", "delivery_note", "credit_note"]:
            header_values = {"invoice_id": "DOC-2024-00001"}
            pdf_bytes = _render_pdf(
                doc_type,
                header_values,
                [],
                [_field("invoice_id", "Doc ID")],
                [],
            )
            assert pdf_bytes[:5] == b"%PDF-", f"Failed for {doc_type}"

    def test_with_line_items(self) -> None:
        header_values = {"invoice_id": "INV-2024-00001"}
        line_items = [
            {"item_description": "Widget", "item_quantity": "5", "item_amount_total": "100.00"},
            {"item_description": "Gadget", "item_quantity": "3", "item_amount_total": "75.00"},
        ]
        li_fields = [
            _field("item_description", "Description"),
            _field("item_quantity", "Qty"),
            _field("item_amount_total", "Amount"),
        ]
        pdf_bytes = _render_pdf(
            "invoice",
            header_values,
            line_items,
            [_field("invoice_id", "Invoice")],
            li_fields,
        )
        assert pdf_bytes[:5] == b"%PDF-"
        assert len(pdf_bytes) > 100

    def test_with_totals_section(self) -> None:
        header_values = {
            "amount_total": "1000.00",
            "amount_total_base": "826.45",
            "amount_total_tax": "173.55",
        }
        header_fields = [
            _field("amount_total", "Total"),
            _field("amount_total_base", "Subtotal"),
            _field("amount_total_tax", "Tax"),
        ]
        pdf_bytes = _render_pdf("invoice", header_values, [], header_fields, [])
        assert pdf_bytes[:5] == b"%PDF-"


class TestGenerateMockPdf:
    """End-to-end tests for generate_mock_pdf."""

    def test_success(self, tmp_path: Path) -> None:
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(fields=INVOICE_FIELDS)
            result = json.loads(result_json)

            assert result["status"] == "success"
            assert "file_path" in result
            assert "expected_values" in result
            assert "line_items" in result
            assert len(result["line_items"]) == 3

            # Verify file exists and is valid PDF
            file_path = tmp_path / result["file_path"].split("/")[-1]
            assert file_path.exists()
            assert file_path.read_bytes()[:5] == b"%PDF-"

            # Verify expected_values has header fields
            expected = result["expected_values"]
            assert "sender_name" in expected
            assert "invoice_id" in expected
            assert "date_issue" in expected
        finally:
            set_context(AgentContext())

    def test_custom_line_item_count(self, tmp_path: Path) -> None:
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(fields=INVOICE_FIELDS, line_item_count=5)
            result = json.loads(result_json)

            assert result["status"] == "success"
            assert len(result["line_items"]) == 5
        finally:
            set_context(AgentContext())

    def test_overrides(self, tmp_path: Path) -> None:
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(
                fields=INVOICE_FIELDS,
                overrides={"invoice_id": "TEST-001", "sender_name": "Test Vendor"},
            )
            result = json.loads(result_json)

            assert result["status"] == "success"
            assert result["expected_values"]["invoice_id"] == "TEST-001"
            assert result["expected_values"]["sender_name"] == "Test Vendor"
        finally:
            set_context(AgentContext())

    def test_custom_filename(self, tmp_path: Path) -> None:
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(fields=INVOICE_FIELDS, filename="my_test.pdf")
            result = json.loads(result_json)

            assert result["status"] == "success"
            assert result["file_path"].endswith("my_test.pdf")
            assert (tmp_path / "my_test.pdf").exists()
        finally:
            set_context(AgentContext())

    def test_all_document_types(self, tmp_path: Path) -> None:
        set_context(AgentContext(output_dir=tmp_path))
        try:
            for doc_type in ["invoice", "purchase_order", "receipt", "delivery_note", "credit_note"]:
                result_json = generate_mock_pdf(
                    fields=INVOICE_FIELDS,
                    document_type=doc_type,
                    filename=f"{doc_type}.pdf",
                )
                result = json.loads(result_json)
                assert result["status"] == "success", f"Failed for {doc_type}"
        finally:
            set_context(AgentContext())

    def test_empty_fields_error(self, tmp_path: Path) -> None:
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(fields=[])
            result = json.loads(result_json)
            assert result["status"] == "error"
            assert "fields list is required" in result["message"]
        finally:
            set_context(AgentContext())

    def test_invalid_document_type_error(self, tmp_path: Path) -> None:
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(fields=INVOICE_FIELDS, document_type="unknown")
            result = json.loads(result_json)
            assert result["status"] == "error"
            assert "Unknown document_type" in result["message"]
        finally:
            set_context(AgentContext())

    def test_amounts_consistent_in_output(self, tmp_path: Path) -> None:
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(fields=INVOICE_FIELDS, line_item_count=3)
            result = json.loads(result_json)

            assert result["status"] == "success"
            expected = result["expected_values"]
            items = result["line_items"]

            # Total should equal sum of item amounts
            total = float(expected["amount_total"])
            item_sum = sum(float(item["item_amount_total"]) for item in items)
            assert abs(total - item_sum) < 0.01

            # Base + tax should equal total
            base = float(expected["amount_total_base"])
            tax = float(expected["amount_total_tax"])
            assert abs(total - (base + tax)) < 0.01
        finally:
            set_context(AgentContext())

    def test_header_only_fields(self, tmp_path: Path) -> None:
        """Test with only header fields (no line items)."""
        set_context(AgentContext(output_dir=tmp_path))
        try:
            fields = [
                _field("sender_name", "Vendor", ["sender_name"]),
                _field("invoice_id", "Invoice #", ["invoice_id"]),
            ]
            result_json = generate_mock_pdf(fields=fields, filename="header_only.pdf")
            result = json.loads(result_json)

            assert result["status"] == "success"
            assert len(result["line_items"]) == 0
        finally:
            set_context(AgentContext())

    def test_path_traversal_sanitized(self, tmp_path: Path) -> None:
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(
                fields=INVOICE_FIELDS,
                filename="../../../etc/evil.pdf",
            )
            result = json.loads(result_json)
            assert result["status"] == "success"
            assert (tmp_path / "evil.pdf").exists()
            assert not (tmp_path.parent / "evil.pdf").exists()
        finally:
            set_context(AgentContext())

    def test_overrides_applied_to_line_items(self, tmp_path: Path) -> None:
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(
                fields=INVOICE_FIELDS,
                overrides={"item_description": "Overridden Item"},
                line_item_count=2,
            )
            result = json.loads(result_json)
            assert result["status"] == "success"
            for item in result["line_items"]:
                assert item["item_description"] == "Overridden Item"
        finally:
            set_context(AgentContext())

    def test_auto_filename_from_order_id(self, tmp_path: Path) -> None:
        """Auto-generated filename falls back to order_id when no invoice_id."""
        fields = [
            _field("order_id", "Order Number", ["order_id"]),
            _field("sender_name", "Vendor", ["sender_name"]),
        ]
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(fields=fields, document_type="purchase_order")
            result = json.loads(result_json)
            assert result["status"] == "success"
            assert result["file_path"].endswith(".pdf")
        finally:
            set_context(AgentContext())

    def test_item_column_sums_match_header_totals(self, tmp_path: Path) -> None:
        """sum(item_amount_base) == amount_total_base and sum(item_amount) == amount_total."""
        fields = [
            _field("document_id", "Document ID"),
            _field("sender_name", "Vendor Name", ["sender_name"]),
            _field("amount_total", "Total Amount", ["amount_total"], "number"),
            _field("amount_total_base", "Total Without Tax", ["amount_total_base"], "number"),
            _field("amount_total_tax", "Total Tax", ["amount_total_tax"], "number"),
            _field("item_description", "Description", ["item_description"]),
            _field("item_quantity", "Quantity", ["item_quantity"], "number"),
            _field("item_amount_base", "Unit Price Base", ["item_amount_base"], "number"),
            _field("item_amount", "Unit Price", ["item_amount"], "number"),
            _field("item_amount_total", "Total Amount", ["item_amount_total"], "number"),
        ]
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(fields=fields, line_item_count=4)
            result = json.loads(result_json)

            assert result["status"] == "success"
            expected = result["expected_values"]
            items = result["line_items"]

            # sum of item_amount_base matches amount_total_base
            sum_base = sum(float(item["item_amount_base"]) for item in items)
            assert abs(float(expected["amount_total_base"]) - sum_base) < 0.01

            # sum of item_amount matches amount_total
            sum_amount = sum(float(item["item_amount"]) for item in items)
            assert abs(float(expected["amount_total"]) - sum_amount) < 0.01

            # tax should still be consistent: total = base + tax
            total = float(expected["amount_total"])
            base = float(expected["amount_total_base"])
            tax = float(expected["amount_total_tax"])
            assert abs(total - (base + tax)) < 0.01
        finally:
            set_context(AgentContext())

    def test_qty_times_rate_equals_item_total(self, tmp_path: Path) -> None:
        """qty * unit_price = item_amount_total for every line item row."""
        fields = [
            _field("invoice_id", "Invoice #", ["invoice_id"]),
            _field("amount_total", "Total", ["amount_total"], "number"),
            _field("item_description", "Description", ["item_description"]),
            _field("item_quantity", "Qty", ["item_quantity"], "number"),
            _field("item_rate", "Unit Price", ["item_rate"], "number"),
            _field("item_amount_total", "Line Total", ["item_amount_total"], "number"),
        ]
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result = json.loads(generate_mock_pdf(fields=fields, line_item_count=3))
            assert result["status"] == "success"
            for item in result["line_items"]:
                expected_total = round(float(item["item_quantity"]) * float(item["item_rate"]), 2)
                assert abs(float(item["item_amount_total"]) - expected_total) < 0.01
        finally:
            set_context(AgentContext())

    def test_item_amount_total_base_is_total_base(self, tmp_path: Path) -> None:
        """item_amount_total_base = item_amount_total / 1.21 (total excl. tax, not unit price)."""
        fields = [
            _field("invoice_id", "Invoice #", ["invoice_id"]),
            _field("amount_total", "Total", ["amount_total"], "number"),
            _field("item_description", "Description", ["item_description"]),
            _field("item_quantity", "Qty", ["item_quantity"], "number"),
            _field("item_rate", "Unit Price", ["item_rate"], "number"),
            _field("item_amount_total", "Line Total", ["item_amount_total"], "number"),
            _field("item_amount_total_base", "Line Base Total", ["item_amount_total_base"], "number"),
        ]
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result = json.loads(generate_mock_pdf(fields=fields, line_item_count=3))
            assert result["status"] == "success"
            for item in result["line_items"]:
                expected_base = round(float(item["item_amount_total"]) / 1.21, 2)
                assert abs(float(item["item_amount_total_base"]) - expected_base) < 0.015
        finally:
            set_context(AgentContext())

    def test_item_total_base_is_supported_schema_variant(self, tmp_path: Path) -> None:
        """item_total_base = item_amount_total / 1.21 for Rossum schemas using that field name."""
        fields = [
            _field("invoice_id", "Invoice #", ["invoice_id"]),
            _field("amount_total", "Total", ["amount_total"], "number"),
            _field("item_description", "Description", ["item_description"]),
            _field("item_quantity", "Qty", ["item_quantity"], "number"),
            _field("item_rate", "Unit Price", ["item_rate"], "number"),
            _field("item_amount_total", "Line Total", ["item_amount_total"], "number"),
            _field("item_total_base", "Line Base Total", ["item_total_base"], "number"),
        ]
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result = json.loads(generate_mock_pdf(fields=fields, line_item_count=3))
            assert result["status"] == "success"
            for item in result["line_items"]:
                expected_base = round(float(item["item_amount_total"]) / 1.21, 2)
                assert abs(float(item["item_total_base"]) - expected_base) < 0.015
        finally:
            set_context(AgentContext())


class TestApplyBaseTaxSplit:
    """Tests for _apply_base_tax_split edge cases."""

    def test_both_base_and_tax(self) -> None:
        header_values: dict[str, str] = {}
        _apply_base_tax_split(header_values, 121.0, "base", "tax")
        base = float(header_values["base"])
        tax = float(header_values["tax"])
        assert abs(base + tax - 121.0) < 0.01

    def test_only_base_id(self) -> None:
        header_values: dict[str, str] = {}
        _apply_base_tax_split(header_values, 500.0, "base", None)
        assert header_values["base"] == "500.0"
        assert "tax" not in header_values

    def test_only_tax_id(self) -> None:
        header_values: dict[str, str] = {}
        _apply_base_tax_split(header_values, 500.0, None, "tax")
        assert header_values["tax"] == "0.00"
        assert "base" not in header_values

    def test_neither_base_nor_tax(self) -> None:
        header_values: dict[str, str] = {}
        _apply_base_tax_split(header_values, 500.0, None, None)
        assert header_values == {}


class TestFindItemTotalKey:
    """Tests for _find_item_total_key."""

    def test_finds_amount_total_key(self) -> None:
        items = [{"item_description": "A", "item_amount_total": "100"}]
        assert _find_item_total_key(items) == "item_amount_total"

    def test_fallback_to_amount_key(self) -> None:
        items = [{"item_description": "A", "line_amount": "100"}]
        assert _find_item_total_key(items) == "line_amount"

    def test_no_matching_key(self) -> None:
        items = [{"item_description": "A", "item_quantity": "5"}]
        assert _find_item_total_key(items) is None

    def test_empty_items(self) -> None:
        assert _find_item_total_key([]) is None

    def test_rir_field_names_resolve_custom_id(self) -> None:
        """Field with custom id but rir_field_names containing item_amount_total."""
        fields = [_field("item_total", "Total", ["item_amount_total"], "number")]
        items = [{"item_total": "100"}]
        assert _find_item_total_key(items, fields) == "item_total"

    def test_item_total_key_without_amount(self) -> None:
        """item_total as dict key (no 'amount' substring) found via name pattern."""
        items = [{"item_description": "A", "item_total": "100"}]
        assert _find_item_total_key(items) == "item_total"

    def test_rir_takes_priority_over_key_scan(self) -> None:
        """When rir_field_names match, use that field even if another key has 'amount'."""
        fields = [
            _field("item_total", "Total", ["item_amount_total"], "number"),
            _field("item_tax_amount", "Tax", [], "number"),
        ]
        items = [{"item_total": "100", "item_tax_amount": "21"}]
        assert _find_item_total_key(items, fields) == "item_total"

    def test_generic_total_key(self) -> None:
        """Key containing 'total' but not 'amount' is found."""
        items = [{"item_description": "A", "item_total_price": "100"}]
        assert _find_item_total_key(items) == "item_total_price"


class TestBuildHeaderRirResolver:
    """Tests for _build_header_rir_resolver."""

    def test_builds_correct_structures(self) -> None:
        fields = [
            _field("total_amount", "Total", ["amount_total"]),
            _field("due_amount", "Due", ["amount_due"]),
        ]
        field_ids, rir_map = _build_header_rir_resolver(fields)
        assert field_ids == {"total_amount", "due_amount"}
        assert rir_map == {"amount_total": "total_amount", "amount_due": "due_amount"}

    def test_empty_fields(self) -> None:
        field_ids, rir_map = _build_header_rir_resolver([])
        assert field_ids == set()
        assert rir_map == {}


class TestValueGenerationExtended:
    """Additional value generation edge cases."""

    def test_enum_with_label_only(self) -> None:
        """Enum option with label but no value key falls back to label."""
        field = {
            "id": "status",
            "label": "Status",
            "type": "enum",
            "rir_field_names": [],
            "options": [{"label": "Active"}],
        }
        value = _generate_value_for_field(field)
        assert value == "Active"


class TestFindItemColumn:
    """Tests for _find_item_column."""

    def test_finds_by_direct_key(self) -> None:
        items = [{"item_amount_base": "100"}]
        assert _find_item_column(items, None, "item_amount_base") == "item_amount_base"

    def test_finds_by_rir(self) -> None:
        fields = [_field("base_price", "Base", ["item_amount_base"], "number")]
        items = [{"base_price": "100"}]
        assert _find_item_column(items, fields, "item_amount_base") == "base_price"

    def test_returns_none_when_missing(self) -> None:
        items = [{"item_description": "A"}]
        assert _find_item_column(items, None, "item_amount_base") is None

    def test_empty_items(self) -> None:
        assert _find_item_column([], None, "item_amount_base") is None


class TestAmountConsistencyExtended:
    """Additional amount consistency edge cases."""

    def test_items_without_amount_key(self) -> None:
        """Line items with no amount-like key → no changes."""
        header_fields = [_field("amount_total", "Total", ["amount_total"], "number")]
        header_values = {"amount_total": "999.99"}
        line_items = [{"item_description": "Widget", "item_quantity": "5"}]
        _make_amounts_consistent(header_values, line_items, header_fields)
        assert header_values["amount_total"] == "999.99"

    def test_custom_item_total_field_via_rir(self) -> None:
        """item_total field with rir_field_names=['item_amount_total'] sums correctly."""
        header_fields = [
            _field("total_amount", "Total Amount", ["amount_total"], "number"),
        ]
        line_item_fields = [
            _field("item_total", "Line Total", ["item_amount_total"], "number"),
        ]
        header_values = {"total_amount": "0"}
        line_items = [{"item_total": "150.00"}, {"item_total": "250.00"}]
        _make_amounts_consistent(header_values, line_items, header_fields, line_item_fields)
        assert float(header_values["total_amount"]) == 400.00

    def test_item_total_without_amount_in_name(self) -> None:
        """item_total field (no 'amount' substring) still triggers consistency."""
        header_fields = [
            _field("amount_total", "Total", ["amount_total"], "number"),
        ]
        header_values = {"amount_total": "0"}
        line_items = [{"item_total": "100.00"}, {"item_total": "200.00"}]
        _make_amounts_consistent(header_values, line_items, header_fields)
        assert float(header_values["amount_total"]) == 300.00

    def test_item_amount_base_distributed_to_match_total_base(self) -> None:
        """item_amount_base values are adjusted so their sum equals amount_total_base."""
        header_fields = [
            _field("amount_total", "Total", ["amount_total"], "number"),
            _field("amount_total_base", "Base", ["amount_total_base"], "number"),
            _field("amount_total_tax", "Tax", ["amount_total_tax"], "number"),
        ]
        line_item_fields = [
            _field("item_amount_base", "Unit Base", ["item_amount_base"], "number"),
            _field("item_amount_total", "Line Total", ["item_amount_total"], "number"),
        ]
        header_values = {"amount_total": "0", "amount_total_base": "0", "amount_total_tax": "0"}
        line_items = [
            {"item_amount_base": "999", "item_amount_total": "200.00"},
            {"item_amount_base": "999", "item_amount_total": "300.00"},
        ]
        _make_amounts_consistent(header_values, line_items, header_fields, line_item_fields)

        total_base = float(header_values["amount_total_base"])
        sum_item_base = sum(float(item["item_amount_base"]) for item in line_items)
        assert abs(total_base - sum_item_base) < 0.01

    def test_item_amount_distributed_to_match_total(self) -> None:
        """item_amount values are adjusted so their sum equals amount_total."""
        header_fields = [
            _field("amount_total", "Total", ["amount_total"], "number"),
        ]
        line_item_fields = [
            _field("item_amount", "Unit Price", ["item_amount"], "number"),
            _field("item_amount_total", "Line Total", ["item_amount_total"], "number"),
        ]
        header_values = {"amount_total": "0"}
        line_items = [
            {"item_amount": "999", "item_amount_total": "150.00"},
            {"item_amount": "999", "item_amount_total": "350.00"},
        ]
        _make_amounts_consistent(header_values, line_items, header_fields, line_item_fields)

        total = float(header_values["amount_total"])
        sum_item_amount = sum(float(item["item_amount"]) for item in line_items)
        assert abs(total - sum_item_amount) < 0.01


class TestLineItemsInternalConsistency:
    """Tests for _make_line_items_internally_consistent."""

    def test_qty_times_rate_equals_total(self) -> None:
        fields = [
            _field("item_quantity", "Qty", ["item_quantity"], "number"),
            _field("item_rate", "Unit Price", ["item_rate"], "number"),
            _field("item_amount_total", "Total", ["item_amount_total"], "number"),
        ]
        line_items = [{"item_quantity": "5", "item_rate": "20.00", "item_amount_total": "999"}]
        _make_line_items_internally_consistent(line_items, fields)
        assert float(line_items[0]["item_amount_total"]) == 100.0

    def test_total_base_derived_from_total(self) -> None:
        fields = [
            _field("item_amount_total", "Total", ["item_amount_total"], "number"),
            _field("item_amount_total_base", "Total Base", ["item_amount_total_base"], "number"),
        ]
        line_items = [{"item_amount_total": "121.00", "item_amount_total_base": "999"}]
        _make_line_items_internally_consistent(line_items, fields)
        assert abs(float(line_items[0]["item_amount_total_base"]) - round(121.0 / 1.21, 2)) < 0.01

    def test_total_base_uses_qty_times_rate_total(self) -> None:
        """When all three fields present, total_base is derived from qty*rate total."""
        fields = [
            _field("item_quantity", "Qty", ["item_quantity"], "number"),
            _field("item_rate", "Unit Price", ["item_rate"], "number"),
            _field("item_amount_total", "Total", ["item_amount_total"], "number"),
            _field("item_amount_total_base", "Total Base", ["item_amount_total_base"], "number"),
        ]
        line_items = [
            {"item_quantity": "4", "item_rate": "121.00", "item_amount_total": "999", "item_amount_total_base": "999"}
        ]
        _make_line_items_internally_consistent(line_items, fields)
        assert float(line_items[0]["item_amount_total"]) == 484.0
        assert abs(float(line_items[0]["item_amount_total_base"]) - round(484.0 / 1.21, 2)) < 0.01

    def test_explicit_total_override_is_preserved(self) -> None:
        fields = [
            _field("item_quantity", "Qty", ["item_quantity"], "number"),
            _field("item_rate", "Unit Price", ["item_rate"], "number"),
            _field("item_amount_total", "Total", ["item_amount_total"], "number"),
        ]
        line_items = [{"item_quantity": "4", "item_rate": "121.00", "item_amount_total": "999"}]
        _make_line_items_internally_consistent(line_items, fields, [{"item_amount_total"}])
        assert float(line_items[0]["item_amount_total"]) == 999.0

    def test_item_total_base_schema_variant(self) -> None:
        fields = [
            _field("item_amount_total", "Total", ["item_amount_total"], "number"),
            _field("item_total_base", "Total Base", ["item_total_base"], "number"),
        ]
        line_items = [{"item_amount_total": "121.00", "item_total_base": "999"}]
        _make_line_items_internally_consistent(line_items, fields)
        assert abs(float(line_items[0]["item_total_base"]) - round(121.0 / 1.21, 2)) < 0.01

    def test_no_change_when_no_rate_col(self) -> None:
        fields = [
            _field("item_quantity", "Qty", ["item_quantity"], "number"),
            _field("item_amount_total", "Total", ["item_amount_total"], "number"),
        ]
        line_items = [{"item_quantity": "5", "item_amount_total": "100.00"}]
        _make_line_items_internally_consistent(line_items, fields)
        assert line_items[0]["item_amount_total"] == "100.00"

    def test_empty_items(self) -> None:
        _make_line_items_internally_consistent([], [])  # no error

    def test_via_rir_field_names(self) -> None:
        """Column resolution works via rir_field_names even when field id differs."""
        fields = [
            _field("qty", "Qty", ["item_quantity"], "number"),
            _field("price", "Price", ["item_rate"], "number"),
            _field("total", "Total", ["item_amount_total"], "number"),
        ]
        line_items = [{"qty": "3", "price": "10.00", "total": "999"}]
        _make_line_items_internally_consistent(line_items, fields)
        assert float(line_items[0]["total"]) == 30.0

    def test_no_qty_col_sets_total_equal_to_rate(self) -> None:
        """When schema has no quantity column, implicit qty=1 so total = unit price."""
        fields = [
            _field("item_rate", "Unit Price", ["item_rate"], "number"),
            _field("item_amount_total", "Total", ["item_amount_total"], "number"),
        ]
        line_items = [{"item_rate": "75.50", "item_amount_total": "999"}]
        _make_line_items_internally_consistent(line_items, fields)
        assert line_items[0]["item_amount_total"] == "75.50"

    def test_no_qty_col_with_total_base(self) -> None:
        """No quantity column → total = rate, and total_base derived from that total."""
        fields = [
            _field("item_rate", "Unit Price", ["item_rate"], "number"),
            _field("item_amount_total", "Total", ["item_amount_total"], "number"),
            _field("item_amount_total_base", "Total Base", ["item_amount_total_base"], "number"),
        ]
        line_items = [{"item_rate": "121.00", "item_amount_total": "999", "item_amount_total_base": "999"}]
        _make_line_items_internally_consistent(line_items, fields)
        assert line_items[0]["item_amount_total"] == "121.00"
        assert abs(float(line_items[0]["item_amount_total_base"]) - round(121.0 / 1.21, 2)) < 0.01

    def test_no_qty_col_explicit_total_override_preserved(self) -> None:
        """Explicit total override is preserved even when qty column is absent."""
        fields = [
            _field("item_rate", "Unit Price", ["item_rate"], "number"),
            _field("item_amount_total", "Total", ["item_amount_total"], "number"),
        ]
        line_items = [{"item_rate": "75.50", "item_amount_total": "200.00"}]
        _make_line_items_internally_consistent(line_items, fields, [{"item_amount_total"}])
        assert line_items[0]["item_amount_total"] == "200.00"


class TestPdfRenderingExtended:
    """Additional rendering path coverage."""

    def test_with_buyer_section(self) -> None:
        header_values = {
            "invoice_id": "INV-2024-00001",
            "recipient_name": "Buyer Corp",
            "recipient_address": "123 Main St, NYC",
            "recipient_vat_id": "DE12345678",
        }
        header_fields = [
            _field("invoice_id", "Invoice"),
            _field("recipient_name", "Buyer", ["recipient_name"]),
            _field("recipient_address", "Address", ["recipient_address"]),
            _field("recipient_vat_id", "VAT", ["recipient_vat_id"]),
        ]
        pdf_bytes = _render_pdf("invoice", header_values, [], header_fields, [])
        assert pdf_bytes[:5] == b"%PDF-"

    def test_with_payment_section(self) -> None:
        header_values = {
            "invoice_id": "INV-2024-00001",
            "iban": "CZ65 0800 0000 1920 0014 5399",
            "bic": "KOMBCZPP",
            "var_sym": "1234567890",
        }
        header_fields = [
            _field("invoice_id", "Invoice"),
            _field("iban", "IBAN", ["iban"]),
            _field("bic", "BIC", ["bic"]),
            _field("var_sym", "Variable Symbol", ["var_sym"]),
        ]
        pdf_bytes = _render_pdf("invoice", header_values, [], header_fields, [])
        assert pdf_bytes[:5] == b"%PDF-"

    def test_with_notes(self) -> None:
        header_values = {
            "invoice_id": "INV-2024-00001",
            "notes": "Payment due within 30 days.",
        }
        header_fields = [
            _field("invoice_id", "Invoice"),
            _field("notes", "Notes", ["notes"]),
        ]
        pdf_bytes = _render_pdf("invoice", header_values, [], header_fields, [])
        assert pdf_bytes[:5] == b"%PDF-"

    def test_with_remaining_fields(self) -> None:
        """Fields not in any known section are rendered at the bottom."""
        header_values = {
            "invoice_id": "INV-2024-00001",
            "custom_ref": "REF-XYZ-123",
        }
        header_fields = [
            _field("invoice_id", "Invoice"),
            _field("custom_ref", "Custom Reference"),
        ]
        pdf_bytes = _render_pdf("invoice", header_values, [], header_fields, [])
        assert pdf_bytes[:5] == b"%PDF-"

    def test_buyer_section_skipped_when_no_buyer_fields(self) -> None:
        """No buyer fields present → buyer section not rendered (no crash)."""
        header_values = {"invoice_id": "INV-2024-00001"}
        header_fields = [_field("invoice_id", "Invoice")]
        pdf_bytes = _render_pdf("invoice", header_values, [], header_fields, [])
        assert pdf_bytes[:5] == b"%PDF-"


class TestNumericOverrides:
    """Tests for numeric override values and per-row line item overrides."""

    def test_numeric_overrides_in_header(self, tmp_path: Path) -> None:
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(
                fields=INVOICE_FIELDS,
                overrides={"amount_total": 1500.50, "amount_total_base": 1240.08, "amount_total_tax": 260.42},
                consistent_amounts=False,
            )
            result = json.loads(result_json)
            assert result["status"] == "success"
            assert result["expected_values"]["amount_total"] == "1500.5"
            assert result["expected_values"]["amount_total_base"] == "1240.08"
            assert result["expected_values"]["amount_total_tax"] == "260.42"
        finally:
            set_context(AgentContext())

    def test_int_overrides(self, tmp_path: Path) -> None:
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(
                fields=INVOICE_FIELDS,
                overrides={"item_quantity": 10},
                line_item_count=2,
            )
            result = json.loads(result_json)
            assert result["status"] == "success"
            for item in result["line_items"]:
                assert item["item_quantity"] == "10"
        finally:
            set_context(AgentContext())

    def test_line_item_overrides_per_row(self, tmp_path: Path) -> None:
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(
                fields=INVOICE_FIELDS,
                line_item_overrides=[
                    {"item_quantity": 5, "item_amount_total": 500.00},
                    {"item_quantity": 3, "item_amount_total": 150.00},
                    {"item_quantity": 1, "item_amount_total": 50.00},
                ],
            )
            result = json.loads(result_json)
            assert result["status"] == "success"
            items = result["line_items"]
            assert len(items) == 3
            assert items[0]["item_quantity"] == "5"
            assert items[0]["item_amount_total"] == "500.0"
            assert items[1]["item_quantity"] == "3"
            assert items[1]["item_amount_total"] == "150.0"
            assert items[2]["item_quantity"] == "1"
            assert items[2]["item_amount_total"] == "50.0"
        finally:
            set_context(AgentContext())

    def test_line_item_overrides_determines_row_count(self, tmp_path: Path) -> None:
        """line_item_overrides length overrides line_item_count."""
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(
                fields=INVOICE_FIELDS,
                line_item_count=10,
                line_item_overrides=[
                    {"item_quantity": 1},
                    {"item_quantity": 2},
                ],
            )
            result = json.loads(result_json)
            assert result["status"] == "success"
            assert len(result["line_items"]) == 2
        finally:
            set_context(AgentContext())

    def test_line_item_overrides_with_global_fallback(self, tmp_path: Path) -> None:
        """Per-row overrides take priority over global overrides."""
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(
                fields=INVOICE_FIELDS,
                overrides={"item_description": "Default Item"},
                line_item_overrides=[
                    {"item_description": "Special Item", "item_quantity": 99},
                    {},
                ],
            )
            result = json.loads(result_json)
            assert result["status"] == "success"
            items = result["line_items"]
            assert items[0]["item_description"] == "Special Item"
            assert items[0]["item_quantity"] == "99"
            # Second row falls back to global override for description
            assert items[1]["item_description"] == "Default Item"
        finally:
            set_context(AgentContext())

    def test_consistent_amounts_false_preserves_mismatch(self, tmp_path: Path) -> None:
        """With consistent_amounts=False, overridden totals are NOT recalculated."""
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(
                fields=INVOICE_FIELDS,
                overrides={"amount_total": 9999.99},
                line_item_overrides=[
                    {"item_amount_total": 100.00},
                    {"item_amount_total": 200.00},
                ],
                consistent_amounts=False,
            )
            result = json.loads(result_json)
            assert result["status"] == "success"
            # Total is the overridden value, NOT the sum of items (300)
            assert result["expected_values"]["amount_total"] == "9999.99"
            assert float(result["line_items"][0]["item_amount_total"]) == 100.00
            assert float(result["line_items"][1]["item_amount_total"]) == 200.00
        finally:
            set_context(AgentContext())

    def test_consistent_amounts_true_recalculates(self, tmp_path: Path) -> None:
        """With consistent_amounts=True (default), totals are recalculated from items."""
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(
                fields=INVOICE_FIELDS,
                overrides={"amount_total": 9999.99},
                line_item_overrides=[
                    {"item_amount_total": 100.00},
                    {"item_amount_total": 200.00},
                ],
                consistent_amounts=True,
            )
            result = json.loads(result_json)
            assert result["status"] == "success"
            # Total IS recalculated to sum of items
            assert float(result["expected_values"]["amount_total"]) == 300.00
        finally:
            set_context(AgentContext())

    def test_consistent_amounts_with_item_total_field(self, tmp_path: Path) -> None:
        """Schemas using 'item_total' (not 'item_amount_total') get consistent amounts."""
        fields = [
            _field("sender_name", "Vendor", ["sender_name"]),
            _field("invoice_id", "Invoice Number", ["invoice_id"]),
            _field("total_amount", "Total Amount", ["amount_total"], "number"),
            _field("item_description", "Description", ["item_description"]),
            _field("item_total", "Line Total", ["item_amount_total"], "number"),
        ]
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(
                fields=fields,
                line_item_overrides=[
                    {"item_total": 120.50},
                    {"item_total": 230.00},
                    {"item_total": 49.50},
                ],
            )
            result = json.loads(result_json)
            assert result["status"] == "success"
            total = float(result["expected_values"]["total_amount"])
            item_sum = sum(float(item["item_total"]) for item in result["line_items"])
            assert abs(total - item_sum) < 0.01
            assert total == 400.00
        finally:
            set_context(AgentContext())

    def test_consistent_line_items_false_preserves_raw_values(self, tmp_path: Path) -> None:
        """With consistent_line_items=False, qty * rate != total is preserved as-is."""
        fields = [
            _field("invoice_id", "Invoice #", ["invoice_id"]),
            _field("amount_total", "Total", ["amount_total"], "number"),
            _field("item_quantity", "Qty", ["item_quantity"], "number"),
            _field("item_rate", "Unit Price", ["item_rate"], "number"),
            _field("item_amount_total", "Line Total", ["item_amount_total"], "number"),
        ]
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(
                fields=fields,
                line_item_overrides=[{"item_quantity": 2, "item_rate": 50.0, "item_amount_total": 999.0}],
                consistent_line_items=False,
            )
            result = json.loads(result_json)
            assert result["status"] == "success"
            # item_amount_total NOT recomputed from qty * rate
            assert float(result["line_items"][0]["item_amount_total"]) == 999.0
        finally:
            set_context(AgentContext())

    def test_consistent_line_items_true_recalculates(self, tmp_path: Path) -> None:
        """With consistent_line_items=True (default), unset item_amount_total = qty * rate."""
        fields = [
            _field("invoice_id", "Invoice #", ["invoice_id"]),
            _field("item_quantity", "Qty", ["item_quantity"], "number"),
            _field("item_rate", "Unit Price", ["item_rate"], "number"),
            _field("item_amount_total", "Line Total", ["item_amount_total"], "number"),
        ]
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(
                fields=fields,
                line_item_overrides=[{"item_quantity": 3, "item_rate": 40.0}],
                consistent_line_items=True,
            )
            result = json.loads(result_json)
            assert result["status"] == "success"
            # item_amount_total IS recomputed: 3 * 40 = 120
            assert float(result["line_items"][0]["item_amount_total"]) == 120.0
        finally:
            set_context(AgentContext())

    def test_consistent_line_items_true_preserves_explicit_overrides(self, tmp_path: Path) -> None:
        fields = [
            _field("invoice_id", "Invoice #", ["invoice_id"]),
            _field("amount_total", "Total", ["amount_total"], "number"),
            _field("item_quantity", "Qty", ["item_quantity"], "number"),
            _field("item_rate", "Unit Price", ["item_rate"], "number"),
            _field("item_amount_total", "Line Total", ["item_amount_total"], "number"),
        ]
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(
                fields=fields,
                line_item_overrides=[{"item_quantity": 3, "item_rate": 40.0, "item_amount_total": 999.0}],
                consistent_line_items=True,
            )
            result = json.loads(result_json)
            assert result["status"] == "success"
            assert float(result["line_items"][0]["item_amount_total"]) == 999.0
        finally:
            set_context(AgentContext())

    def test_consistent_line_items_rounding_matches_header_base_total(self, tmp_path: Path) -> None:
        fields = [
            _field("amount_total", "Total", ["amount_total"], "number"),
            _field("amount_total_base", "Base", ["amount_total_base"], "number"),
            _field("amount_total_tax", "Tax", ["amount_total_tax"], "number"),
            _field("item_quantity", "Qty", ["item_quantity"], "number"),
            _field("item_rate", "Unit Price", ["item_rate"], "number"),
            _field("item_amount_total", "Line Total", ["item_amount_total"], "number"),
            _field("item_amount_total_base", "Line Base Total", ["item_amount_total_base"], "number"),
        ]
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(
                fields=fields,
                line_item_overrides=[
                    {"item_quantity": 1, "item_rate": 0.03},
                    {"item_quantity": 1, "item_rate": 0.03},
                    {"item_quantity": 1, "item_rate": 0.03},
                ],
            )
            result = json.loads(result_json)
            assert result["status"] == "success"
            total_base = float(result["expected_values"]["amount_total_base"])
            sum_item_base = sum(float(item["item_amount_total_base"]) for item in result["line_items"])
            assert abs(total_base - sum_item_base) < 0.01
        finally:
            set_context(AgentContext())


class TestIsHidden:
    """Tests for _is_hidden."""

    def test_hidden_true(self) -> None:
        assert _is_hidden({"hidden": True}) is True

    def test_hidden_false(self) -> None:
        assert _is_hidden({"hidden": False}) is False

    def test_hidden_missing(self) -> None:
        assert _is_hidden({}) is False

    def test_hidden_truthy_non_bool(self) -> None:
        assert _is_hidden({"hidden": 1}) is True


class TestHiddenFieldHandling:
    """Hidden fields are excluded from PDF and output; required non-hidden fields are included."""

    def test_hidden_line_item_fields_not_in_output(self, tmp_path: Path) -> None:
        fields = [
            _field("sender_name", "Vendor", ["sender_name"]),
            _field("item_code", "Code", ["item_code"]),
            _field("item_quantity", "Qty", ["item_quantity"], "number"),
            _field("item_amount_total", "Total", ["item_amount_total"], "number"),
            _field("item_amount_base", "Base", ["item_amount_base"], "number", hidden=True),
        ]
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(fields=fields, line_item_count=2)
            result = json.loads(result_json)
            assert result["status"] == "success"
            for item in result["line_items"]:
                assert "item_amount_base" not in item
                assert "item_code" in item
                assert "item_quantity" in item
                assert "item_amount_total" in item
        finally:
            set_context(AgentContext())

    def test_hidden_header_fields_not_in_expected_values(self, tmp_path: Path) -> None:
        fields = [
            _field("sender_name", "Vendor", ["sender_name"]),
            _field("invoice_id", "Invoice", ["invoice_id"]),
            _field("internal_ref", "Internal Ref", [], hidden=True),
        ]
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(fields=fields)
            result = json.loads(result_json)
            assert result["status"] == "success"
            assert "internal_ref" not in result["expected_values"]
            assert "sender_name" in result["expected_values"]
            assert "invoice_id" in result["expected_values"]
        finally:
            set_context(AgentContext())

    def test_required_non_hidden_field_always_in_output(self, tmp_path: Path) -> None:
        """Visible line item fields appear in output even when marked required."""
        fields = [
            _field("sender_name", "Vendor", ["sender_name"]),
            _field("item_code", "Code", ["item_code"]),
            _field("item_amount_total", "Total", ["item_amount_total"], "number"),
            _field("item_amount_total_base", "Total Base", ["item_amount_total_base"], "number", required=True),
        ]
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(fields=fields, line_item_count=2)
            result = json.loads(result_json)
            assert result["status"] == "success"
            for item in result["line_items"]:
                assert "item_amount_total" in item
                assert "item_amount_total_base" in item
        finally:
            set_context(AgentContext())

    def test_amounts_consistent_with_hidden_fields(self, tmp_path: Path) -> None:
        """Consistency calculation uses all fields; output only shows visible ones."""
        fields = [
            _field("amount_total", "Total", ["amount_total"], "number"),
            _field("amount_total_base", "Base", ["amount_total_base"], "number"),
            _field("amount_total_tax", "Tax", ["amount_total_tax"], "number"),
            _field("item_amount_total", "Total", ["item_amount_total"], "number"),
            _field("item_amount_base", "Base", ["item_amount_base"], "number", hidden=True),
        ]
        set_context(AgentContext(output_dir=tmp_path))
        try:
            result_json = generate_mock_pdf(fields=fields, line_item_count=3)
            result = json.loads(result_json)
            assert result["status"] == "success"
            total = float(result["expected_values"]["amount_total"])
            item_sum = sum(float(item["item_amount_total"]) for item in result["line_items"])
            assert abs(total - item_sum) < 0.01
            # Hidden field not in output
            for item in result["line_items"]:
                assert "item_amount_base" not in item
        finally:
            set_context(AgentContext())
