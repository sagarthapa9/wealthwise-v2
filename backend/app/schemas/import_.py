"""
Pydantic schemas for the CSV import workflow.

- ``ImportRowData`` — one parsed CSV row (preview/import payload)
- ``ImportPreviewResponse`` — returned by the preview endpoint
- ``ImportResponse`` — returned by the import endpoint
- ``ImportRowError`` — per-row error detail
"""

from pydantic import BaseModel, Field


# ── Row data ──────────────────────────────────────────────────────────────

class ImportRowData(BaseModel):
    """A single CSV row after parsing — sent in the preview response and import request."""
    row_number: int
    ticker: str | None = None
    name: str | None = None
    quantity: float | None = None
    cost_basis_per_share: float | None = None
    current_price: float | None = None
    currency: str | None = None
    isin: str | None = None
    # Validation
    valid: bool = True
    errors: list[str] = []
    # Enrichment status
    enriched: bool = False
    enrichment_error: str | None = None
    type: str | None = None
    asset_class: str | None = None
    sector: str | None = None
    geography: str | None = None
    ocf_pct: float | None = None
    dividend_yield_pct: float | None = None


# ── Preview response ──────────────────────────────────────────────────────

class ImportPreviewResponse(BaseModel):
    """Returned by POST /portfolio/import/preview — no DB writes."""
    total_rows: int
    valid_rows: int
    invalid_rows: int
    rows: list[ImportRowData]
    mapped_columns: dict[str, str]   # {canonical: csv_header}  e.g. {"ticker": "Symbol"}
    unmapped_columns: list[str]      # Headers we couldn't match


# ── Import request ────────────────────────────────────────────────────────

class ImportRequest(BaseModel):
    """Request body for POST /portfolio/import."""
    account_id: int = Field(..., description="Target account for all imported holdings")
    rows: list[ImportRowData] = Field(..., min_length=1, description="Rows to import")


# ── Import response ───────────────────────────────────────────────────────

class ImportRowError(BaseModel):
    """Error detail for a single row that could not be imported."""
    row: int
    ticker: str | None = None
    reason: str


class ImportResponse(BaseModel):
    """Returned by POST /portfolio/import after successful bulk insert."""
    imported: int
    skipped: int
    enriched_count: int
    errors: list[ImportRowError]
