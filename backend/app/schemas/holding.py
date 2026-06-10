"""
Pydantic schemas for request/response validation.

- ``HoldingCreate`` — data the frontend sends when adding a row
- ``HoldingUpdate`` — data sent when editing (all fields optional)
- ``HoldingResponse`` — what the API sends back (includes id and timestamps)
- ``PortfolioSummary`` — computed totals for the summary card
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ── Request schemas (what the frontend sends) ──────────────────────────

class HoldingCreate(BaseModel):
    """Schema for creating a new holding."""
    ticker: str = Field(..., min_length=1, max_length=10, examples=["VWRL"])
    name: str = Field(..., min_length=1, max_length=200)
    quantity: float = Field(..., ge=0, examples=[150.0])
    cost_basis_per_share: float = Field(..., ge=0, examples=[85.50])
    current_price: float = Field(default=0.0, ge=0, examples=[98.76])
    account_id: int | None = Field(default=None, examples=[1])

    # Classification fields (auto-populated from ticker lookup, optional for API)
    type: str | None = Field(default=None, max_length=20)
    asset_class: str | None = Field(default=None, max_length=30)
    sector: str | None = Field(default=None, max_length=40)
    geography: str | None = Field(default=None, max_length=30)
    currency: str | None = Field(default=None, max_length=3)
    ocf_pct: float | None = Field(default=None, ge=0)
    dividend_yield_pct: float | None = Field(default=None, ge=0)
    isin: str | None = Field(default=None, max_length=12)


class HoldingUpdate(BaseModel):
    """Schema for updating an existing holding. All fields optional."""
    ticker: str | None = Field(default=None, min_length=1, max_length=10)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    quantity: float | None = Field(default=None, ge=0)
    cost_basis_per_share: float | None = Field(default=None, ge=0)
    current_price: float | None = Field(default=None, ge=0)
    account_id: int | None = None


# ── Response schemas (what the API sends back) ─────────────────────────

class HoldingResponse(BaseModel):
    """Schema returned after create/read/update."""
    id: int
    ticker: str
    name: str
    quantity: float
    cost_basis_per_share: float
    current_price: float
    account_id: int | None = None

    # Classification fields
    type: str | None = None
    asset_class: str | None = None
    sector: str | None = None
    geography: str | None = None
    currency: str | None = None
    ocf_pct: float | None = None
    dividend_yield_pct: float | None = None
    isin: str | None = None

    created_at: datetime
    updated_at: datetime

    # Computed fields — calculated server-side
    total_cost: float = 0.0       # quantity × cost_basis_per_share
    current_value: float = 0.0    # quantity × current_price
    gain_loss: float = 0.0        # current_value - total_cost
    gain_loss_pct: float = 0.0    # (gain_loss / total_cost) × 100

    model_config = {"from_attributes": True}


class PortfolioSummary(BaseModel):
    """Computed portfolio totals."""
    total_cost: float = 0.0
    total_value: float = 0.0
    total_gain_loss: float = 0.0
    total_gain_loss_pct: float = 0.0
    holding_count: int = 0


# ── Ticker lookup schema ─────────────────────────────────────────────────

class TickerResponse(BaseModel):
    """Response from the ticker lookup endpoint."""
    ticker: str
    name: str
    price: float
    currency: str
    type: str
    asset_class: str
    sector: str
    geography: str
    ocf_pct: float | None = None
    dividend_yield_pct: float | None = None
    isin: str | None = None


class TickerSearchResult(BaseModel):
    """Lightweight search result from EODHD search endpoint."""
    code: str
    name: str
    type: str | None = None
    exchange: str | None = None
    match_score: float | None = None
