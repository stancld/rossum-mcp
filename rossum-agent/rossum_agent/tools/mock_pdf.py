"""Mock PDF generation tool for document testing.

Generates schema-aware PDF documents with realistic field values
for end-to-end extraction testing.
"""

from __future__ import annotations

import contextlib
import json
import logging
import random
import string
import unicodedata
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

# Unicode font support — fpdf2's built-in Helvetica only supports Latin-1 (ISO-8859-1).
# Characters like Czech "Č" or "ě" (Latin Extended-A) require a TTF font.
_UNICODE_FONT_CANDIDATES: list[dict[str, str]] = [
    {  # DejaVu Sans — common on Debian/Ubuntu Docker images
        "": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "B": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "I": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    },
    {  # macOS — Arial from Supplemental
        "": "/System/Library/Fonts/Supplemental/Arial.ttf",
        "B": "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "I": "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
    },
]


def _detect_unicode_font() -> tuple[str, dict[str, str]]:
    """Find a Unicode TTF font for PDF rendering. Falls back to Helvetica (Latin-1 only)."""
    for family in _UNICODE_FONT_CANDIDATES:
        regular = family.get("")
        if not regular or not Path(regular).is_file():
            continue
        paths: dict[str, str] = {"": regular}
        for style in ("B", "I"):
            path = family.get(style)
            # Use regular as fallback for missing bold/italic variants
            paths[style] = path if path and Path(path).is_file() else regular
        return "UniFont", paths
    return "Helvetica", {}


_FONT_NAME, _FONT_PATHS = _detect_unicode_font()


def _sanitize_latin1(text: str) -> str:
    """Strip diacritics and replace non-Latin-1 chars for Helvetica compatibility."""
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return stripped.encode("latin-1", errors="replace").decode("latin-1")


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


def _is_hidden(field: dict) -> bool:
    """Return True if a field is marked as hidden."""
    return bool(field.get("hidden", False))


_DEFAULT_TAX_RATE = 0.21

# rir_field_names that represent item-level total amounts
_TOTAL_RIR_NAMES: set[str] = {"item_amount_total", "item_total_amount"}
_TOTAL_BASE_RIR_NAMES: set[str] = {"item_amount_total_base", "item_total_base"}


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


def _find_key_by_pattern(
    line_items: list[dict[str, str]],
    predicate: Callable[[str], bool],
) -> str | None:
    """Return the first dict key across all line items matching predicate."""
    for item in line_items:
        for key in item:
            if predicate(key):
                return key
    return None


def _find_item_column(
    line_items: list[dict[str, str]],
    line_item_fields: list[dict] | None,
    rir_name: str,
) -> str | None:
    """Find the line item column key matching a rir_field_name or field id."""
    if line_item_fields:
        for f in line_item_fields:
            if rir_name in f.get("rir_field_names", []):
                fid = f.get("id", "")
                if any(fid in item for item in line_items):
                    return fid
    if any(rir_name in item for item in line_items):
        return rir_name
    return None


def _find_item_total_key(
    line_items: list[dict[str, str]],
    line_item_fields: list[dict] | None = None,
) -> str | None:
    """Find the line item column key that represents amount totals.

    Resolution order:
    1. rir_field_names containing known total rir names (item_amount_total, item_total_amount)
    2. Dict key containing "amount_total"
    3. Dict key matching "item_total" exactly
    4. Dict key containing "total" (but not "amount" and not "item_total")
    5. Dict key containing "amount" (fallback)
    """
    # Try rir_field_names first (most reliable)
    if line_item_fields:
        for f in line_item_fields:
            rir_names = set(f.get("rir_field_names", []))
            if rir_names & _TOTAL_RIR_NAMES:
                fid = f.get("id", "")
                if any(fid in item for item in line_items):
                    return fid

    # Fallback: scan dict keys by name patterns (most specific first)
    return (
        _find_key_by_pattern(line_items, lambda k: "amount_total" in k)
        or _find_key_by_pattern(line_items, lambda k: k == "item_total")
        or _find_key_by_pattern(
            line_items,
            lambda k: "total" in k and "amount" not in k and k != "item_total",
        )
        or _find_key_by_pattern(line_items, lambda k: "amount" in k)
    )


def _apply_base_tax_split(
    header_values: dict[str, str],
    total: float,
    base_id: str | None,
    tax_id: str | None,
) -> None:
    """Split total into base + tax amounts."""
    if base_id and tax_id:
        base = round(total / (1 + _DEFAULT_TAX_RATE), 2)
        tax = round(total - base, 2)
        header_values[base_id] = str(base)
        header_values[tax_id] = str(tax)
    elif base_id:
        header_values[base_id] = str(total)
    elif tax_id:
        header_values[tax_id] = "0.00"


def _distribute_subtotals(
    header_values: dict[str, str],
    line_items: list[dict[str, str]],
    line_item_fields: list[dict] | None,
    total: float,
    item_total_key: str,
    find_header_id: Callable[[str], str | None],
) -> None:
    """Distribute header sub-totals proportionally across line item columns."""
    _ITEM_HEADER_COLUMN_PAIRS = [
        ("item_amount_base", "amount_total_base"),
        ("item_amount", "amount_total"),
    ]
    item_weights = [float(item.get(item_total_key, "0")) for item in line_items]
    for item_rir, header_rir in _ITEM_HEADER_COLUMN_PAIRS:
        item_col = _find_item_column(line_items, line_item_fields, item_rir)
        if not item_col or item_col == item_total_key:
            continue
        header_id = find_header_id(header_rir)
        if not header_id or header_id not in header_values:
            continue
        target = float(header_values[header_id])
        running = 0.0
        for i, item in enumerate(line_items):
            if i == len(line_items) - 1:
                item[item_col] = str(round(target - running, 2))
            else:
                val = round(item_weights[i] / total * target, 2)
                item[item_col] = str(val)
                running += val


def _make_amounts_consistent(
    header_values: dict[str, str],
    line_items: list[dict[str, str]],
    header_fields: list[dict],
    line_item_fields: list[dict] | None = None,
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

    item_total_key = _find_item_total_key(line_items, line_item_fields)
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

    # Distribute header sub-totals proportionally across line item columns
    # so that e.g. sum(item_amount_base) == amount_total_base
    if total > 0:
        _distribute_subtotals(header_values, line_items, line_item_fields, total, item_total_key, _find_header_id)


def _get_explicit_row_fields(explicit_fields_by_row: list[set[str]], row_index: int) -> set[str]:
    if row_index < len(explicit_fields_by_row):
        return explicit_fields_by_row[row_index]
    return set()


def _collect_row_totals(line_items: list[dict[str, str]], total_col: str) -> list[tuple[int, float]]:
    total_by_row: list[tuple[int, float]] = []
    for i, item in enumerate(line_items):
        with contextlib.suppress(ValueError, KeyError):
            total_by_row.append((i, round(float(item[total_col]), 2)))
    return total_by_row


def _set_fallback_base_totals(
    line_items: list[dict[str, str]], auto_base_rows: list[tuple[int, float]], total_base_col: str
) -> None:
    for i, total in auto_base_rows:
        line_items[i][total_base_col] = str(round(total / (1 + _DEFAULT_TAX_RATE), 2))


def _distribute_row_base_totals(
    line_items: list[dict[str, str]],
    total_base_col: str,
    total_by_row: list[tuple[int, float]],
    explicit_fields_by_row: list[set[str]],
) -> None:
    explicit_base_sum = 0.0
    auto_base_rows: list[tuple[int, float]] = []
    for i, total in total_by_row:
        explicit_fields = _get_explicit_row_fields(explicit_fields_by_row, i)
        if total_base_col in explicit_fields:
            with contextlib.suppress(ValueError, KeyError):
                explicit_base_sum += round(float(line_items[i][total_base_col]), 2)
            continue
        auto_base_rows.append((i, total))

    if not auto_base_rows:
        return

    target_base_total = round(sum(total for _, total in total_by_row) / (1 + _DEFAULT_TAX_RATE), 2)
    remaining_base_total = round(target_base_total - explicit_base_sum, 2)
    auto_total_sum = sum(total for _, total in auto_base_rows)

    if remaining_base_total < 0 or auto_total_sum <= 0:
        _set_fallback_base_totals(line_items, auto_base_rows, total_base_col)
        return

    running_base = 0.0
    for position, (i, total) in enumerate(auto_base_rows):
        if position == len(auto_base_rows) - 1:
            base_value = round(remaining_base_total - running_base, 2)
        else:
            base_value = round(total / auto_total_sum * remaining_base_total, 2)
            running_base += base_value
        line_items[i][total_base_col] = str(base_value)


def _make_line_items_internally_consistent(
    line_items: list[dict[str, str]],
    line_item_fields: list[dict] | None,
    explicit_fields_by_row: list[set[str]] | None = None,
) -> None:
    """Fill derived row values without overwriting explicit overrides."""
    if not line_items:
        return

    explicit_fields_by_row = explicit_fields_by_row or [set() for _ in line_items]

    qty_col = _find_item_column(line_items, line_item_fields, "item_quantity")
    price_col = _find_item_column(line_items, line_item_fields, "item_rate")
    total_col = _find_item_total_key(line_items, line_item_fields)
    total_base_col = next(
        (
            col
            for rir_name in _TOTAL_BASE_RIR_NAMES
            if (col := _find_item_column(line_items, line_item_fields, rir_name)) is not None
        ),
        None,
    )

    for i, item in enumerate(line_items):
        explicit_fields = _get_explicit_row_fields(explicit_fields_by_row, i)
        if total_col and total_col not in explicit_fields:
            with contextlib.suppress(ValueError, KeyError):
                if qty_col and price_col:
                    item[total_col] = str(round(float(item[qty_col]) * float(item[price_col]), 2))
                elif not qty_col and price_col:
                    # No quantity column in schema → implicit qty=1, total = unit price
                    item[total_col] = item[price_col]

    if not total_base_col or not total_col:
        return

    total_by_row = _collect_row_totals(line_items, total_col)
    if not total_by_row:
        return

    _distribute_row_base_totals(line_items, total_base_col, total_by_row, explicit_fields_by_row)


def _build_label_map(header_fields: list[dict], line_item_fields: list[dict]) -> dict[str, str]:
    """Build field ID → label mapping."""
    label_map: dict[str, str] = {}
    for f in header_fields + line_item_fields:
        label_map[f.get("id", "")] = f.get("label", f.get("id", ""))
    return label_map


# Field groups for each rendered section — single source of truth for both rendering and "remaining" detection
_VENDOR_FIELDS = ["sender_name", "sender_address", "sender_vat_id", "sender_ic"]
_DOC_FIELDS = ["invoice_id", "order_id", "document_id", "date_issue", "date_due", "date_delivery", "currency"]
_BUYER_FIELDS = ["recipient_name", "recipient_address", "recipient_vat_id", "recipient_ic"]
_TOTAL_FIELDS = ["amount_total_base", "amount_total_tax", "amount_total", "amount_due", "amount_paid"]
_PAYMENT_FIELDS = ["bank_num", "iban", "bic", "var_sym", "const_sym"]

# All known section field IDs — used to find "remaining" fields not covered by named sections
_KNOWN_SECTION_FIELDS = frozenset(
    {*_VENDOR_FIELDS, *_DOC_FIELDS, *_BUYER_FIELDS, *_TOTAL_FIELDS, *_PAYMENT_FIELDS, "notes"}
)


def _render_field_list(
    pdf: FPDF, field_ids: list[str], header_values: dict[str, str], label_map: dict[str, str], x: float | None = None
) -> None:
    """Render a list of field values. Skips fields not in header_values."""
    for fid in field_ids:
        if fid in header_values:
            lbl = label_map.get(fid, fid)
            if x is not None:
                pdf.set_x(x)
            pdf.cell(0, 5, f"{lbl}: {header_values[fid]}", new_x="LMARGIN", new_y="NEXT")


def _render_header_section(pdf: FPDF, header_values: dict[str, str], label_map: dict[str, str]) -> None:
    """Render vendor info (left) and document details (right) in two columns."""
    left_col_x = 10
    right_col_x = 120
    y_start = pdf.get_y()

    # Left column: vendor info
    pdf.set_xy(left_col_x, y_start)
    pdf.set_font(_FONT_NAME, "B", 11)
    pdf.cell(100, 6, "From:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(_FONT_NAME, "", 10)
    _render_field_list(pdf, _VENDOR_FIELDS, header_values, label_map, x=left_col_x)
    left_end_y = pdf.get_y()

    # Right column: document ID, dates
    pdf.set_xy(right_col_x, y_start)
    pdf.set_font(_FONT_NAME, "B", 11)
    pdf.cell(80, 6, "Details:")
    pdf.set_font(_FONT_NAME, "", 10)
    right_y = y_start + 6
    for df in _DOC_FIELDS:
        if df in header_values:
            lbl = label_map.get(df, df)
            pdf.set_xy(right_col_x, right_y)
            pdf.cell(80, 5, f"{lbl}: {header_values[df]}")
            right_y += 5

    pdf.set_y(max(left_end_y, right_y) + 4)


def _render_buyer_section(pdf: FPDF, header_values: dict[str, str], label_map: dict[str, str]) -> None:
    """Render buyer/recipient info block."""
    if not any(bf in header_values for bf in _BUYER_FIELDS):
        return
    pdf.set_font(_FONT_NAME, "B", 11)
    pdf.cell(0, 6, "Bill To:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(_FONT_NAME, "", 10)
    _render_field_list(pdf, _BUYER_FIELDS, header_values, label_map)
    pdf.ln(4)


def _render_line_items_table(pdf: FPDF, line_items: list[dict[str, str]], line_item_fields: list[dict]) -> None:
    """Render the line items table with header and data rows."""
    if not line_items or not line_item_fields:
        return

    pdf.set_font(_FONT_NAME, "B", 10)
    pdf.cell(0, 8, "Line Items", new_x="LMARGIN", new_y="NEXT")

    n_cols = len(line_item_fields)
    col_width = 190 / max(n_cols, 1)

    # Header row
    pdf.set_font(_FONT_NAME, "B", 9)
    pdf.set_fill_color(230, 230, 230)
    for f in line_item_fields:
        lbl = f.get("label", f.get("id", ""))
        pdf.cell(col_width, 7, lbl[:20], border=1, fill=True)
    pdf.ln()

    # Data rows
    pdf.set_font(_FONT_NAME, "", 9)
    for item in line_items:
        for f in line_item_fields:
            fid = f.get("id", "")
            val = item.get(fid, "")
            pdf.cell(col_width, 6, str(val)[:25], border=1)
        pdf.ln()

    pdf.ln(4)


def _render_totals_section(pdf: FPDF, header_values: dict[str, str], label_map: dict[str, str]) -> None:
    """Render totals block with bold emphasis on total/due amounts."""
    if not any(tf in header_values for tf in _TOTAL_FIELDS):
        return

    pdf.set_font(_FONT_NAME, "B", 11)
    pdf.cell(0, 8, "Totals", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(_FONT_NAME, "", 10)
    for tf in _TOTAL_FIELDS:
        if tf in header_values:
            lbl = label_map.get(tf, tf)
            is_total = tf in ("amount_total", "amount_due")
            if is_total:
                pdf.set_font(_FONT_NAME, "B", 11)
            pdf.cell(0, 6, f"{lbl}: {header_values[tf]}", new_x="LMARGIN", new_y="NEXT")
            if is_total:
                pdf.set_font(_FONT_NAME, "", 10)
    pdf.ln(4)


def _render_payment_section(pdf: FPDF, header_values: dict[str, str], label_map: dict[str, str]) -> None:
    """Render payment details block."""
    if not any(pf in header_values for pf in _PAYMENT_FIELDS):
        return
    pdf.set_font(_FONT_NAME, "B", 11)
    pdf.cell(0, 8, "Payment Details", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(_FONT_NAME, "", 10)
    _render_field_list(pdf, _PAYMENT_FIELDS, header_values, label_map)
    pdf.ln(4)


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

    # Register Unicode TTF font if available
    for style, path in _FONT_PATHS.items():
        pdf.add_font(_FONT_NAME, style, path)

    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title
    pdf.set_font(_FONT_NAME, "B", 20)
    pdf.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    label_map = _build_label_map(header_fields, line_item_fields)
    pdf.set_font(_FONT_NAME, "", 10)

    _render_header_section(pdf, header_values, label_map)
    _render_buyer_section(pdf, header_values, label_map)
    _render_line_items_table(pdf, line_items, line_item_fields)
    _render_totals_section(pdf, header_values, label_map)
    _render_payment_section(pdf, header_values, label_map)

    # Notes
    if "notes" in header_values:
        pdf.set_font(_FONT_NAME, "I", 9)
        pdf.multi_cell(0, 5, header_values["notes"])

    # Remaining header fields not covered by known sections
    remaining = {fid: val for fid, val in header_values.items() if fid not in _KNOWN_SECTION_FIELDS}
    if remaining:
        pdf.ln(2)
        pdf.set_font(_FONT_NAME, "", 9)
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


def _build_explicit_line_item_fields(
    line_item_fields: list[dict],
    row_count: int,
    overrides: dict[str, OverrideValue],
    line_item_overrides: list[dict[str, OverrideValue]] | None,
) -> list[set[str]]:
    """Track which row fields were set explicitly by the caller."""
    explicit_fields_by_row: list[set[str]] = []
    line_item_field_ids = {f.get("id", "") for f in line_item_fields}
    global_override_ids = {field_id for field_id in overrides if field_id in line_item_field_ids}

    for i in range(row_count):
        row_override_ids = (
            set(line_item_overrides[i]) & line_item_field_ids
            if line_item_overrides and i < len(line_item_overrides)
            else set()
        )
        explicit_fields_by_row.append(global_override_ids | row_override_ids)

    return explicit_fields_by_row


@beta_tool
def generate_mock_pdf(
    fields: list[dict],
    document_type: str = "invoice",
    line_item_count: int = 3,
    overrides: dict[str, OverrideValue] | None = None,
    line_item_overrides: list[dict[str, OverrideValue]] | None = None,
    consistent_amounts: bool = True,
    consistent_line_items: bool = True,
    filename: str | None = None,
) -> str:
    """Generate a mock PDF document with realistic values matching schema fields.

    Use for end-to-end extraction testing: generate PDF → upload → verify extracted values match expected.

    Args:
        fields: Schema field descriptors: [{id, label, type, rir_field_names?, options?, required?, hidden?}].
            Extract from schema content (sections → datapoints, multivalues → tuples).
            hidden=True fields are excluded from the PDF rendering and output JSON, but still included in
            internal consistency calculations (e.g., tax/total rounding). Use for internal/formula fields.
        document_type: Document type: invoice, purchase_order, receipt, delivery_note, credit_note.
        line_item_count: Number of line item rows to generate (default 3). Ignored when line_item_overrides is provided.
        overrides: Optional {field_id: value} to force specific field values. Accepts str, int, or float.
            Applied to header fields and as fallback for line item fields not covered by line_item_overrides.
        line_item_overrides: Optional list of per-row override dicts. Length determines row count.
            Each dict maps field_id to value for that row. Missing fields use overrides fallback or random values.
        consistent_amounts: When True (default), recalculate header totals to match sum of line item totals.
            Set to False to keep header amounts as-is — useful for testing header/line-item mismatch.
        consistent_line_items: When True (default), derive unset row-level values: item_amount_total from
            item_quantity * item_rate, and item_amount_total_base or item_total_base from item_amount_total.
            Explicit override values are preserved. Set to False to keep raw generated values.
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
        all_line_item_fields = [f for f in fields if _is_line_item_field(f)]
        # Only visible (non-hidden) fields appear as PDF columns and in the output
        visible_line_item_fields = [f for f in all_line_item_fields if not _is_hidden(f)]

        # Generate header values
        header_values: dict[str, str] = {}
        for f in header_fields:
            fid = f.get("id", "")
            if fid in overrides:
                header_values[fid] = str(overrides[fid])
            else:
                header_values[fid] = _generate_value_for_field(f)

        # Generate line items for all fields (including hidden) — needed for consistency
        line_items = _generate_line_items(all_line_item_fields, line_item_count, overrides, line_item_overrides)
        explicit_line_item_fields = _build_explicit_line_item_fields(
            all_line_item_fields,
            len(line_items),
            overrides,
            line_item_overrides,
        )

        if consistent_line_items:
            _make_line_items_internally_consistent(line_items, all_line_item_fields, explicit_line_item_fields)
        if consistent_amounts:
            _make_amounts_consistent(header_values, line_items, header_fields, all_line_item_fields)

        # Sanitize text for Latin-1 Helvetica when no Unicode font is available
        if not _FONT_PATHS:
            header_values = {k: _sanitize_latin1(v) for k, v in header_values.items()}
            line_items = [{k: _sanitize_latin1(v) for k, v in item.items()} for item in line_items]

        # Render PDF with only visible (non-hidden) line item columns
        pdf_bytes = _render_pdf(document_type, header_values, line_items, header_fields, visible_line_item_fields)

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

        # Output only non-hidden fields — what's visible in the document and extractable
        visible_header_ids = {f.get("id", "") for f in header_fields if not _is_hidden(f)}
        visible_line_item_ids = {f.get("id", "") for f in all_line_item_fields if not _is_hidden(f)}

        return json.dumps(
            {
                "status": "success",
                "file_path": str(file_path),
                "expected_values": {k: v for k, v in header_values.items() if k in visible_header_ids},
                "line_items": [{k: v for k, v in item.items() if k in visible_line_item_ids} for item in line_items],
            }
        )

    except Exception as e:
        logger.exception("Error in generate_mock_pdf")
        return json.dumps({"status": "error", "message": str(e)})
