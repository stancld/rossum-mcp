"""Tests for the generate_mock_pdf tool."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from rossum_agent.tools.core import AgentContext, set_context
from rossum_agent.tools.mock_pdf import (
    _apply_base_tax_split,
    _build_header_rir_resolver,
    _find_item_total_key,
    _generate_value_for_field,
    _is_line_item_field,
    _make_amounts_consistent,
    _render_pdf,
    generate_mock_pdf,
)

if TYPE_CHECKING:
    from pathlib import Path


# -- Sample field fixtures --


def _field(field_id: str, label: str, rir: list[str] | None = None, field_type: str = "string") -> dict:
    return {"id": field_id, "label": label, "type": field_type, "rir_field_names": rir or []}


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


class TestAmountConsistencyExtended:
    """Additional amount consistency edge cases."""

    def test_items_without_amount_key(self) -> None:
        """Line items with no amount-like key → no changes."""
        header_fields = [_field("amount_total", "Total", ["amount_total"], "number")]
        header_values = {"amount_total": "999.99"}
        line_items = [{"item_description": "Widget", "item_quantity": "5"}]
        _make_amounts_consistent(header_values, line_items, header_fields)
        assert header_values["amount_total"] == "999.99"


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
