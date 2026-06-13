"""
Generic CSV parser for portfolio import — flexible column mapping, validation, and ticker enrichment.

Handles any brokerage CSV format by matching column headers against canonical field aliases.
Parsing is tolerant: strips currency symbols, commas, and whitespace from numeric fields.
"""

import csv
import io
import re
from dataclasses import dataclass, field

from app.services.ticker_provider import TickerData


# ── Column alias table ────────────────────────────────────────────────────
# Each canonical field maps to a list of common brokerage CSV header names.
# Matching is case-insensitive and punctuation-normalised.

COLUMN_ALIASES: dict[str, list[str]] = {
    "ticker": [
        "ticker", "symbol", "code", "instrument", "epic",
        "ticker symbol", "ticker_code", "stock",
    ],
    "name": [
        "name", "description", "investment", "instrument name",
        "stock", "holding", "fund name", "investment name",
        "instrument_name", "security", "security_name",
    ],
    "quantity": [
        "quantity", "shares", "units", "no of shares",
        "no. of shares", "number of shares", "holding",
        "units held", "qty", "holdings", "volume",
    ],
    "cost_basis_per_share": [
        "cost_basis_per_share", "cost basis per share",
        "cost_per_share", "cost per share",
        "price_per_share", "price per share",
        "price / share", "price/share",
        "avg_cost", "average cost", "avg price", "average price",
        "purchase_price", "purchase price", "buy price",
        "price per unit", "price/unit", "unit price",
        "cost basis", "book cost",
    ],
    "current_price": [
        "current_price", "current price",
        "last_price", "last price",
        "market_price", "market price",
        "close_price", "close price", "closing price",
        "current price", "current value",
    ],
    "currency": [
        "currency", "ccy", "cc",
        "currency (price/share)", "currency price/share",
        "currency (withholding tax)",
        "local currency", "trading currency",
    ],
    "isin": [
        "isin", "isin_code", "isin code", "isin number",
    ],
}


def _normalise_header(header: str) -> str:
    """Normalise a CSV header for matching: lowercase, strip, collapse whitespace."""
    return re.sub(r"[^a-z0-9 ]", "", header.lower().strip())


def _build_column_map(headers: list[str]) -> tuple[dict[str, str], list[str]]:
    """Match CSV headers to canonical fields.

    Returns:
        column_map:  {canonical_field: csv_header_name}  e.g. {"ticker": "Symbol"}
        unmapped:    list of CSV headers that matched no canonical field
    """
    # Pre-build normalised alias lookup  {normalised_alias: canonical_field}
    alias_lookup: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            norm = _normalise_header(alias)
            if norm not in alias_lookup:
                alias_lookup[norm] = canonical

    column_map: dict[str, str] = {}
    unmapped: list[str] = []

    for h in headers:
        norm = _normalise_header(h)
        matched = alias_lookup.get(norm)
        if matched and matched not in column_map:
            column_map[matched] = h
        else:
            unmapped.append(h)

    return column_map, unmapped


def _clean_number(value: str) -> str:
    """Strip currency symbols, commas, and whitespace from a numeric string."""
    if not value:
        return ""
    # Remove currency symbols and commas
    cleaned = re.sub(r"[£$€,]", "", value.strip())
    return cleaned.strip()


def _parse_float(value: str | None) -> float | None:
    """Parse a numeric CSV value to float, returning None on failure."""
    if value is None or value.strip() == "":
        return None
    try:
        return float(_clean_number(value))
    except (ValueError, TypeError):
        return None


# ── Row data ───────────────────────────────────────────────────────────────

@dataclass
class ParsedRow:
    """One CSV row after parsing and validation, before enrichment."""
    row_number: int                     # 1-based row in CSV
    ticker: str | None = None
    name: str | None = None
    quantity: float | None = None
    cost_basis_per_share: float | None = None
    current_price: float | None = None
    currency: str | None = None
    isin: str | None = None

    # Validation state
    valid: bool = True
    errors: list[str] = field(default_factory=list)

    # Enrichment state (filled after ticker lookup)
    enriched: bool = False
    enrichment_error: str | None = None
    type: str | None = None
    asset_class: str | None = None
    sector: str | None = None
    geography: str | None = None
    ocf_pct: float | None = None
    dividend_yield_pct: float | None = None


def parse_csv(content: str | bytes) -> tuple[list[ParsedRow], dict[str, str], list[str]]:
    """Parse a CSV string into validated rows with column mapping.

    Args:
        content: Raw CSV text or bytes.

    Returns:
        rows:         Validated ParsedRow objects (one per data row).
        column_map:   {canonical_field: csv_header_name} for display.
        unmapped:     CSV headers that matched no canonical field.
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")  # Handle BOM

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValueError("CSV file is empty or has no headers")

    column_map, unmapped = _build_column_map(list(reader.fieldnames))

    # Convenience: resolve column names from the map
    col_ticker = column_map.get("ticker")
    col_name = column_map.get("name")
    col_qty = column_map.get("quantity")
    col_cost = column_map.get("cost_basis_per_share")
    col_price = column_map.get("current_price")
    col_currency = column_map.get("currency")
    col_isin = column_map.get("isin")

    rows: list[ParsedRow] = []
    for i, raw in enumerate(reader, start=1):
        row = ParsedRow(row_number=i)

        # Extract fields using mapped column names
        row.ticker = raw.get(col_ticker, "").strip().upper() if col_ticker else None
        row.name = raw.get(col_name, "").strip() if col_name else None
        row.currency = raw.get(col_currency, "").strip().upper() if col_currency else None
        row.isin = raw.get(col_isin, "").strip().upper() if col_isin else None

        # Parse numerics
        row.quantity = _parse_float(raw.get(col_qty)) if col_qty else None
        row.cost_basis_per_share = _parse_float(raw.get(col_cost)) if col_cost else None
        row.current_price = _parse_float(raw.get(col_price)) if col_price else None

        # Validate
        if not row.ticker:
            row.valid = False
            row.errors.append("Missing ticker symbol")

        if row.quantity is None or row.quantity <= 0:
            row.valid = False
            row.errors.append("Missing or invalid quantity (must be > 0)")

        if row.cost_basis_per_share is None or row.cost_basis_per_share < 0:
            row.valid = False
            row.errors.append("Missing or invalid cost basis per share (must be >= 0)")

        # Clean up empty strings to None
        if row.ticker == "":
            row.ticker = None
        if row.name == "":
            row.name = None
        if row.currency == "":
            row.currency = None
        if row.isin == "":
            row.isin = None

        rows.append(row)

    return rows, column_map, unmapped


def apply_enrichment(row: ParsedRow, data: TickerData) -> ParsedRow:
    """Merge ticker provider data into a parsed row.

    Rules:
      - Classification fields (type, asset_class, sector, geography, ocf, yield)
        come from the ticker provider ONLY — it's more authoritative than any CSV.
      - User-provided data (name, current_price, currency, isin) — CSV takes
        precedence, provider fills gaps.
    """
    row.enriched = True
    row.enrichment_error = None

    # Provider-only fields (classification is authoritative)
    row.type = data.type
    row.asset_class = data.asset_class
    row.sector = data.sector
    row.geography = data.geography
    if data.ocf_pct is not None:
        row.ocf_pct = data.ocf_pct
    if data.dividend_yield_pct is not None:
        row.dividend_yield_pct = data.dividend_yield_pct

    # Provider beats CSV for current price (always want live price)
    if data.price > 0:
        row.current_price = data.price

    # CSV beats provider for these (user-supplied data)
    if not row.name:
        row.name = data.name
    if not row.currency:
        row.currency = data.currency
    if data.isin and not row.isin:
        row.isin = data.isin

    return row
