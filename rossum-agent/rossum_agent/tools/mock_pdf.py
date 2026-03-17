"""Mock PDF generation tool for document testing.

Generates schema-aware PDF documents with realistic field values
for end-to-end extraction testing.
"""

from __future__ import annotations

import json
import logging
import random
import string
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from anthropic import beta_tool
from fpdf import FPDF

from rossum_agent.tools.core import get_context

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# Override values can be str, int, or float — converted to str before use
OverrideValue = str | int | float

# Document type titles
_DOCUMENT_TITLES: dict[str, str] = {
    "invoice": "INVOICE",
    "purchase_order": "PURCHASE ORDER",
    "receipt": "RECEIPT",
    "delivery_note": "DELIVERY NOTE",
    "credit_note": "CREDIT NOTE",
}

# Vendor/buyer data pools
_VENDOR_NAMES = [
    "Acme Corporation",
    "Global Supplies Ltd.",
    "TechParts Inc.",
    "Summit Industries",
    "NorthStar Logistics",
]
_BUYER_NAMES = ["Pinnacle Enterprises", "Horizon Manufacturing", "Vertex Solutions", "Atlas Group", "Meridian Corp."]
_CITIES = ["New York, NY 10001", "London EC2A 1NT", "Berlin 10115", "Prague 11000", "San Francisco, CA 94105"]
_STREETS = ["123 Commerce St", "45 Industrial Ave", "789 Business Blvd", "12 Trade Lane", "567 Market Rd"]
_ITEM_DESCRIPTIONS = [
    "Office supplies - premium paper A4",
    "Wireless keyboard and mouse set",
    "LED monitor 27-inch 4K",
    "Ergonomic office chair",
    "USB-C docking station",
    "External SSD 1TB",
    "Noise-cancelling headphones",
    "Webcam HD 1080p",
    "Standing desk converter",
    "Cable management kit",
]
_CURRENCIES = ["USD", "EUR", "GBP", "CZK"]


def _random_date(days_back: int = 30) -> date:
    """Generate a random recent date."""
    return date.today() - timedelta(days=random.randint(0, days_back))


def _random_amount(low: float = 10.0, high: float = 500.0) -> float:
    """Generate a random amount rounded to 2 decimals."""
    return round(random.uniform(low, high), 2)


def _random_doc_id(prefix: str = "INV") -> str:
    """Generate a document ID like INV-2024-00142."""
    year = date.today().year
    seq = random.randint(1, 99999)
    return f"{prefix}-{year}-{seq:05d}"


def _random_vat_id(prefix: str = "CZ") -> str:
    """Generate a VAT ID like CZ12345678."""
    digits = "".join(random.choices(string.digits, k=8))
    return f"{prefix}{digits}"


def _random_iban() -> str:
    """Generate a plausible IBAN."""
    digits = "".join(random.choices(string.digits, k=20))
    return f"CZ{digits[:2]} {digits[2:6]} {digits[6:10]} {digits[10:14]} {digits[14:18]} {digits[18:]}"


# rir_field_name → value generator
_RIR_VALUE_GENERATORS: dict[str, Callable[[], str]] = {
    "invoice_id": lambda: _random_doc_id("INV"),
    "order_id": lambda: _random_doc_id("PO"),
    "document_id": lambda: _random_doc_id("DOC"),
    "date_issue": lambda: _random_date(30).isoformat(),
    "date_due": lambda: (_random_date(30) + timedelta(days=30)).isoformat(),
    "date_delivery": lambda: _random_date(15).isoformat(),
    "date_order": lambda: _random_date(45).isoformat(),
    "sender_name": lambda: random.choice(_VENDOR_NAMES),
    "sender_address": lambda: f"{random.choice(_STREETS)}, {random.choice(_CITIES)}",
    "sender_vat_id": lambda: _random_vat_id(),
    "sender_ic": lambda: "".join(random.choices(string.digits, k=8)),
    "recipient_name": lambda: random.choice(_BUYER_NAMES),
    "recipient_address": lambda: f"{random.choice(_STREETS)}, {random.choice(_CITIES)}",
    "recipient_vat_id": lambda: _random_vat_id("DE"),
    "recipient_ic": lambda: "".join(random.choices(string.digits, k=8)),
    "currency": lambda: random.choice(_CURRENCIES),
    "amount_total": lambda: str(_random_amount(500, 5000)),
    "amount_total_base": lambda: str(_random_amount(400, 4000)),
    "amount_total_tax": lambda: str(_random_amount(50, 500)),
    "amount_due": lambda: str(_random_amount(500, 5000)),
    "amount_paid": lambda: "0.00",
    "tax_detail_rate": lambda: random.choice(["21", "19", "20", "15", "10"]),
    "bank_num": lambda: "".join(random.choices(string.digits, k=10)),
    "iban": _random_iban,
    "bic": lambda: "KOMBCZPP",
    "var_sym": lambda: "".join(random.choices(string.digits, k=10)),
    "const_sym": lambda: "0308",
    "notes": lambda: "Payment due within 30 days of invoice date.",
    # Line item generators
    "item_description": lambda: random.choice(_ITEM_DESCRIPTIONS),
    "item_quantity": lambda: str(random.randint(1, 20)),
    "item_uom": lambda: random.choice(["pcs", "kg", "m", "hrs", "box"]),
    "item_amount_base": lambda: str(_random_amount(10, 500)),
    "item_amount_total": lambda: str(_random_amount(10, 500)),
    "item_rate": lambda: str(_random_amount(5, 200)),
    "item_tax": lambda: str(_random_amount(1, 100)),
    "item_code": lambda: "".join(random.choices(string.ascii_uppercase + string.digits, k=6)),
}


def _is_line_item_field(field: dict) -> bool:
    """Determine if a field belongs to line items (table rows)."""
    field_id = field.get("id", "")
    if field_id.startswith("item_"):
        return True
    rir_names = field.get("rir_field_names", [])
    return any(name.startswith("item_") for name in rir_names)


def _generate_value_for_field(field: dict) -> str:
    """Generate a realistic value for a single field."""
    # Check rir_field_names first (most specific)
    for rir_name in field.get("rir_field_names", []):
        if rir_name in _RIR_VALUE_GENERATORS:
            return _RIR_VALUE_GENERATORS[rir_name]()

    # Check field id as fallback
    field_id = field.get("id", "")
    if field_id in _RIR_VALUE_GENERATORS:
        return _RIR_VALUE_GENERATORS[field_id]()

    # Fallback by type
    field_type = field.get("type", "string")
    label = field.get("label", field_id)

    if field_type == "number":
        return str(_random_amount(1, 1000))
    if field_type == "date":
        return _random_date(60).isoformat()
    if field_type == "enum":
        options = field.get("options", [])
        if options:
            option = options[0]
            return option.get("value", option.get("label", "option_1"))
        return "option_1"

    return f"Sample {label}"


def _build_header_rir_resolver(header_fields: list[dict]) -> tuple[set[str], dict[str, str]]:
    """Build lookup structures for resolving rir_field_names to header field IDs."""
    header_field_ids = {f.get("id", "") for f in header_fields}
    header_rir_map: dict[str, str] = {}
    for f in header_fields:
        for rir_name in f.get("rir_field_names", []):
            header_rir_map[rir_name] = f.get("id", "")
    return header_field_ids, header_rir_map


def _find_item_total_key(line_items: list[dict[str, str]]) -> str | None:
    """Find the line item column key that represents amount totals."""
    for item in line_items:
        for key in item:
            if "amount_total" in key or "amount" in key:
                return key
    return None


def _apply_base_tax_split(
    header_values: dict[str, str],
    total: float,
    base_id: str | None,
    tax_id: str | None,
) -> None:
    """Split total into base + tax amounts."""
    if base_id and tax_id:
        tax_rate = 0.21
        base = round(total / (1 + tax_rate), 2)
        tax = round(total - base, 2)
        header_values[base_id] = str(base)
        header_values[tax_id] = str(tax)
    elif base_id:
        header_values[base_id] = str(total)
    elif tax_id:
        header_values[tax_id] = "0.00"


def _make_amounts_consistent(
    header_values: dict[str, str],
    line_items: list[dict[str, str]],
    header_fields: list[dict],
) -> None:
    """Ensure amount fields are mathematically consistent (mutates in place).

    Rules:
    - amount_total = sum of item_amount_total values
    - amount_total = amount_total_base + amount_total_tax
    - amount_due = amount_total (when present)
    """
    header_field_ids, header_rir_map = _build_header_rir_resolver(header_fields)

    def _find_header_id(rir_name: str) -> str | None:
        if rir_name in header_field_ids:
            return rir_name
        return header_rir_map.get(rir_name)

    item_total_key = _find_item_total_key(line_items)
    if not item_total_key or not line_items:
        return

    # Recalculate item totals to clean numbers
    for item in line_items:
        if item_total_key in item:
            item[item_total_key] = str(round(float(item[item_total_key]), 2))

    # Sum of line item totals
    total = round(sum(float(item.get(item_total_key, "0")) for item in line_items), 2)

    # Set amount_total and amount_due
    for rir_name in ("amount_total", "amount_due"):
        fid = _find_header_id(rir_name)
        if fid:
            header_values[fid] = str(total)

    _apply_base_tax_split(
        header_values,
        total,
        _find_header_id("amount_total_base"),
        _find_header_id("amount_total_tax"),
    )


def _build_label_map(header_fields: list[dict], line_item_fields: list[dict]) -> dict[str, str]:
    """Build field ID → label mapping."""
    label_map: dict[str, str] = {}
    for f in header_fields + line_item_fields:
        label_map[f.get("id", "")] = f.get("label", f.get("id", ""))
    return label_map


def _render_field_list(
    pdf: FPDF,
    field_ids: list[str],
    header_values: dict[str, str],
    label_map: dict[str, str],
    x: float | None = None,
) -> None:
    """Render a list of field values. Skips fields not in header_values."""
    for fid in field_ids:
        if fid in header_values:
            lbl = label_map.get(fid, fid)
            if x is not None:
                pdf.set_x(x)
            pdf.cell(0, 5, f"{lbl}: {header_values[fid]}", new_x="LMARGIN", new_y="NEXT")


def _render_header_section(
    pdf: FPDF,
    header_values: dict[str, str],
    label_map: dict[str, str],
) -> None:
    """Render vendor info (left) and document details (right) in two columns."""
    left_col_x = 10
    right_col_x = 120
    y_start = pdf.get_y()

    # Left column: vendor info
    vendor_fields = ["sender_name", "sender_address", "sender_vat_id", "sender_ic"]
    pdf.set_xy(left_col_x, y_start)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(100, 6, "From:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    _render_field_list(pdf, vendor_fields, header_values, label_map, x=left_col_x)
    left_end_y = pdf.get_y()

    # Right column: document ID, dates
    doc_fields = ["invoice_id", "order_id", "document_id", "date_issue", "date_due", "date_delivery", "currency"]
    pdf.set_xy(right_col_x, y_start)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(80, 6, "Details:")
    pdf.set_font("Helvetica", "", 10)
    right_y = y_start + 6
    for df in doc_fields:
        if df in header_values:
            lbl = label_map.get(df, df)
            pdf.set_xy(right_col_x, right_y)
            pdf.cell(80, 5, f"{lbl}: {header_values[df]}")
            right_y += 5

    pdf.set_y(max(left_end_y, right_y) + 4)


def _render_buyer_section(
    pdf: FPDF,
    header_values: dict[str, str],
    label_map: dict[str, str],
) -> None:
    """Render buyer/recipient info block."""
    buyer_fields = ["recipient_name", "recipient_address", "recipient_vat_id", "recipient_ic"]
    if not any(bf in header_values for bf in buyer_fields):
        return
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Bill To:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    _render_field_list(pdf, buyer_fields, header_values, label_map)
    pdf.ln(4)


def _render_line_items_table(
    pdf: FPDF,
    line_items: list[dict[str, str]],
    line_item_fields: list[dict],
) -> None:
    """Render the line items table with header and data rows."""
    if not line_items or not line_item_fields:
        return

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 8, "Line Items", new_x="LMARGIN", new_y="NEXT")

    n_cols = len(line_item_fields)
    col_width = 190 / max(n_cols, 1)

    # Header row
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    for f in line_item_fields:
        lbl = f.get("label", f.get("id", ""))
        pdf.cell(col_width, 7, lbl[:20], border=1, fill=True)
    pdf.ln()

    # Data rows
    pdf.set_font("Helvetica", "", 9)
    for item in line_items:
        for f in line_item_fields:
            fid = f.get("id", "")
            val = item.get(fid, "")
            pdf.cell(col_width, 6, str(val)[:25], border=1)
        pdf.ln()

    pdf.ln(4)


def _render_totals_section(
    pdf: FPDF,
    header_values: dict[str, str],
    label_map: dict[str, str],
) -> None:
    """Render totals block with bold emphasis on total/due amounts."""
    total_fields = ["amount_total_base", "amount_total_tax", "amount_total", "amount_due", "amount_paid"]
    if not any(tf in header_values for tf in total_fields):
        return

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Totals", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for tf in total_fields:
        if tf in header_values:
            lbl = label_map.get(tf, tf)
            is_total = tf in ("amount_total", "amount_due")
            if is_total:
                pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 6, f"{lbl}: {header_values[tf]}", new_x="LMARGIN", new_y="NEXT")
            if is_total:
                pdf.set_font("Helvetica", "", 10)
    pdf.ln(4)


def _render_payment_section(
    pdf: FPDF,
    header_values: dict[str, str],
    label_map: dict[str, str],
) -> None:
    """Render payment details block."""
    payment_fields = ["bank_num", "iban", "bic", "var_sym", "const_sym"]
    if not any(pf in header_values for pf in payment_fields):
        return
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Payment Details", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    _render_field_list(pdf, payment_fields, header_values, label_map)
    pdf.ln(4)


# All known section field IDs — used to find "remaining" fields
_KNOWN_SECTION_FIELDS = frozenset(
    [
        *["sender_name", "sender_address", "sender_vat_id", "sender_ic"],
        *["invoice_id", "order_id", "document_id", "date_issue", "date_due", "date_delivery", "currency"],
        *["recipient_name", "recipient_address", "recipient_vat_id", "recipient_ic"],
        *["amount_total_base", "amount_total_tax", "amount_total", "amount_due", "amount_paid"],
        *["bank_num", "iban", "bic", "var_sym", "const_sym"],
        "notes",
    ]
)


def _render_pdf(
    document_type: str,
    header_values: dict[str, str],
    line_items: list[dict[str, str]],
    header_fields: list[dict],
    line_item_fields: list[dict],
) -> bytes:
    """Render a PDF with header info and line items table."""
    title = _DOCUMENT_TITLES.get(document_type, "INVOICE")
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    label_map = _build_label_map(header_fields, line_item_fields)
    pdf.set_font("Helvetica", "", 10)

    _render_header_section(pdf, header_values, label_map)
    _render_buyer_section(pdf, header_values, label_map)
    _render_line_items_table(pdf, line_items, line_item_fields)
    _render_totals_section(pdf, header_values, label_map)
    _render_payment_section(pdf, header_values, label_map)

    # Notes
    if "notes" in header_values:
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(0, 5, header_values["notes"])

    # Remaining header fields not covered by known sections
    remaining = {fid: val for fid, val in header_values.items() if fid not in _KNOWN_SECTION_FIELDS}
    if remaining:
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 9)
        for fid, val in remaining.items():
            lbl = label_map.get(fid, fid)
            pdf.cell(0, 5, f"{lbl}: {val}", new_x="LMARGIN", new_y="NEXT")

    output = pdf.output()
    if output is None:
        return b""
    return bytes(output)


def _generate_line_items(
    line_item_fields: list[dict],
    line_item_count: int,
    overrides: dict[str, OverrideValue],
    line_item_overrides: list[dict[str, OverrideValue]] | None,
) -> list[dict[str, str]]:
    if not line_item_fields:
        return []
    row_count = len(line_item_overrides) if line_item_overrides else line_item_count
    line_items: list[dict[str, str]] = []
    for i in range(row_count):
        row: dict[str, str] = {}
        row_overrides = line_item_overrides[i] if line_item_overrides and i < len(line_item_overrides) else {}
        for f in line_item_fields:
            fid = f.get("id", "")
            if fid in row_overrides:
                row[fid] = str(row_overrides[fid])
            elif fid in overrides:
                row[fid] = str(overrides[fid])
            else:
                row[fid] = _generate_value_for_field(f)
        line_items.append(row)
    return line_items


@beta_tool
def generate_mock_pdf(
    fields: list[dict],
    document_type: str = "invoice",
    line_item_count: int = 3,
    overrides: dict[str, OverrideValue] | None = None,
    line_item_overrides: list[dict[str, OverrideValue]] | None = None,
    consistent_amounts: bool = True,
    filename: str | None = None,
) -> str:
    """Generate a mock PDF document with realistic values matching schema fields.

    Use for end-to-end extraction testing: generate PDF → upload → verify extracted values match expected.

    Args:
        fields: Schema field descriptors: [{id, label, type, rir_field_names?, options?}].
            Extract from schema content (sections → datapoints, multivalues → tuples).
        document_type: Document type: invoice, purchase_order, receipt, delivery_note, credit_note.
        line_item_count: Number of line item rows to generate (default 3). Ignored when line_item_overrides is provided.
        overrides: Optional {field_id: value} to force specific field values. Accepts str, int, or float.
            Applied to header fields and as fallback for line item fields not covered by line_item_overrides.
        line_item_overrides: Optional list of per-row override dicts. Length determines row count.
            Each dict maps field_id to value for that row. Missing fields use overrides fallback or random values.
        consistent_amounts: When True (default), recalculate header amounts to match line item sums.
            Set to False to keep overridden amounts as-is — useful for testing mismatch/validation rules.
        filename: Output filename (auto-generated if omitted).

    Returns:
        JSON with status, file_path, expected_values (header fields), and line_items (table rows).
    """
    if not fields:
        return json.dumps({"status": "error", "message": "fields list is required and cannot be empty"})

    if document_type not in _DOCUMENT_TITLES:
        return json.dumps(
            {
                "status": "error",
                "message": f"Unknown document_type '{document_type}'. Use: {', '.join(_DOCUMENT_TITLES)}",
            }
        )

    overrides = overrides or {}

    try:
        # Classify fields
        header_fields = [f for f in fields if not _is_line_item_field(f)]
        line_item_fields = [f for f in fields if _is_line_item_field(f)]

        # Generate header values
        header_values: dict[str, str] = {}
        for f in header_fields:
            fid = f.get("id", "")
            if fid in overrides:
                header_values[fid] = str(overrides[fid])
            else:
                header_values[fid] = _generate_value_for_field(f)

        # Generate line items (only when line item fields exist)
        line_items = _generate_line_items(line_item_fields, line_item_count, overrides, line_item_overrides)

        # Make amounts consistent (unless explicitly disabled for mismatch testing)
        if consistent_amounts:
            _make_amounts_consistent(header_values, line_items, header_fields)

        # Render PDF
        pdf_bytes = _render_pdf(document_type, header_values, line_items, header_fields, line_item_fields)

        # Write to output directory
        output_dir = get_context().get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        if not filename:
            doc_id = header_values.get("invoice_id") or header_values.get("order_id") or "mock"
            filename = f"{doc_id.lower().replace(' ', '_')}.pdf"

        safe_filename = Path(filename).name
        file_path = output_dir / safe_filename
        file_path.write_bytes(pdf_bytes)

        logger.info(f"generate_mock_pdf: wrote {len(pdf_bytes)} bytes to {file_path}")

        return json.dumps(
            {
                "status": "success",
                "file_path": str(file_path),
                "expected_values": header_values,
                "line_items": line_items,
            }
        )

    except Exception as e:
        logger.exception("Error in generate_mock_pdf")
        return json.dumps({"status": "error", "message": str(e)})
