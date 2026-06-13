"""
Portfolio CRUD endpoints — create, read, update, delete holdings + summary + CSV import.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.holding import Holding
from app.schemas.holding import (
    HoldingCreate,
    HoldingResponse,
    HoldingUpdate,
    PortfolioSummary,
)
from app.schemas.import_ import (
    ImportPreviewResponse,
    ImportRequest,
    ImportResponse,
    ImportRowData,
    ImportRowError,
)
from app.services.csv_parser import apply_enrichment, parse_csv, ParsedRow
from app.services.ticker_provider import TickerNotFoundError, get_ticker_provider

logger = logging.getLogger(__name__)

router = APIRouter(tags=["portfolio"])


# ── Helpers ────────────────────────────────────────────────────────────

def _holding_to_response(h: Holding) -> HoldingResponse:
    """Convert an ORM Holding to a response with computed fields."""
    total_cost = h.quantity * h.cost_basis_per_share
    current_value = h.quantity * h.current_price
    gain_loss = current_value - total_cost
    pct = (gain_loss / total_cost * 100) if total_cost > 0 else 0.0

    return HoldingResponse(
        id=h.id,
        ticker=h.ticker,
        name=h.name,
        quantity=h.quantity,
        cost_basis_per_share=h.cost_basis_per_share,
        current_price=h.current_price,
        account_id=h.account_id,
        # Classification and financial metadata
        type=h.type,
        asset_class=h.asset_class,
        sector=h.sector,
        geography=h.geography,
        currency=h.currency,
        ocf_pct=h.ocf_pct,
        dividend_yield_pct=h.dividend_yield_pct,
        isin=h.isin,
        created_at=h.created_at,
        updated_at=h.updated_at,
        total_cost=round(total_cost, 2),
        current_value=round(current_value, 2),
        gain_loss=round(gain_loss, 2),
        gain_loss_pct=round(pct, 2),
    )


# ── CRUD Endpoints ─────────────────────────────────────────────────────


@router.post("/portfolio/holdings", response_model=HoldingResponse, status_code=201)
async def create_holding(data: HoldingCreate, db: AsyncSession = Depends(get_db)):
    """Add a new holding to the portfolio."""
    holding = Holding(
        ticker=data.ticker.upper(),
        name=data.name,
        quantity=data.quantity,
        cost_basis_per_share=data.cost_basis_per_share,
        current_price=data.current_price,
        account_id=data.account_id,
        # Store classification and financial metadata (auto-populated from ticker lookup)
        type=data.type,
        asset_class=data.asset_class,
        sector=data.sector,
        geography=data.geography,
        currency=data.currency,
        ocf_pct=data.ocf_pct,
        dividend_yield_pct=data.dividend_yield_pct,
        isin=data.isin,
    )
    db.add(holding)
    await db.commit()
    await db.refresh(holding)  # Load the auto-generated id and timestamps
    return _holding_to_response(holding)


@router.get("/portfolio/holdings", response_model=list[HoldingResponse])
async def list_holdings(db: AsyncSession = Depends(get_db)):
    """Get all holdings in the portfolio, newest first."""
    result = await db.execute(
        select(Holding).order_by(Holding.created_at.desc())
    )
    holdings = result.scalars().all()
    return [_holding_to_response(h) for h in holdings]


@router.put("/portfolio/holdings/{holding_id}", response_model=HoldingResponse)
async def update_holding(
    holding_id: int, data: HoldingUpdate, db: AsyncSession = Depends(get_db)
):
    """Update quantity, cost, price, or name of an existing holding."""
    result = await db.execute(select(Holding).where(Holding.id == holding_id))
    holding = result.scalar_one_or_none()

    if holding is None:
        raise HTTPException(status_code=404, detail="Holding not found")

    # Only update fields that were provided (partial update)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "ticker" and value is not None:
            value = value.upper()
        setattr(holding, key, value)

    await db.commit()
    await db.refresh(holding)
    return _holding_to_response(holding)


@router.delete("/portfolio/holdings/{holding_id}", status_code=204)
async def delete_holding(holding_id: int, db: AsyncSession = Depends(get_db)):
    """Remove a holding from the portfolio."""
    result = await db.execute(select(Holding).where(Holding.id == holding_id))
    holding = result.scalar_one_or_none()

    if holding is None:
        raise HTTPException(status_code=404, detail="Holding not found")

    await db.delete(holding)
    await db.commit()
    return None  # 204 No Content


@router.get("/portfolio/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(db: AsyncSession = Depends(get_db)):
    """Get portfolio totals — value, cost, gain/loss across all holdings."""
    result = await db.execute(select(Holding))
    holdings = result.scalars().all()

    if not holdings:
        return PortfolioSummary()

    total_cost = sum(h.quantity * h.cost_basis_per_share for h in holdings)
    total_value = sum(h.quantity * h.current_price for h in holdings)
    gain_loss = total_value - total_cost
    pct = (gain_loss / total_cost * 100) if total_cost > 0 else 0.0

    return PortfolioSummary(
        total_cost=round(total_cost, 2),
        total_value=round(total_value, 2),
        total_gain_loss=round(gain_loss, 2),
        total_gain_loss_pct=round(pct, 2),
        holding_count=len(holdings),
    )


# ── CSV Import ────────────────────────────────────────────────────────────


def _parsed_to_import_row(parsed: ParsedRow) -> ImportRowData:
    """Convert internal ParsedRow to API-facing ImportRowData."""
    return ImportRowData(
        row_number=parsed.row_number,
        ticker=parsed.ticker,
        name=parsed.name,
        quantity=parsed.quantity,
        cost_basis_per_share=parsed.cost_basis_per_share,
        current_price=parsed.current_price,
        currency=parsed.currency,
        isin=parsed.isin,
        valid=parsed.valid,
        errors=parsed.errors,
        enriched=parsed.enriched,
        enrichment_error=parsed.enrichment_error,
        type=parsed.type,
        asset_class=parsed.asset_class,
        sector=parsed.sector,
        geography=parsed.geography,
        ocf_pct=parsed.ocf_pct,
        dividend_yield_pct=parsed.dividend_yield_pct,
    )


async def _enrich_rows(rows: list[ParsedRow]) -> list[ParsedRow]:
    """Concurrently enrich parsed rows via the ticker provider (max 5 at a time)."""
    provider = get_ticker_provider()
    sem = asyncio.Semaphore(5)

    async def enrich_one(row: ParsedRow) -> ParsedRow:
        if not row.ticker or not row.valid:
            return row
        async with sem:
            try:
                data = await provider.lookup(row.ticker)
                row = apply_enrichment(row, data)
            except TickerNotFoundError:
                row.enriched = False
                row.enrichment_error = "Ticker not found"
            except Exception:
                row.enriched = False
                row.enrichment_error = "Ticker lookup failed"
        return row

    return list(await asyncio.gather(*[enrich_one(r) for r in rows]))


@router.post("/portfolio/import/preview", response_model=ImportPreviewResponse)
async def import_preview(file: UploadFile):
    """Parse a CSV file and return enriched rows for preview.  No DB writes.

    Accepts multipart/form-data: ``file`` = the CSV file.
    Returns mapped columns, row data, and enrichment status.
    """
    # ── Validate file ──────────────────────────────────────────────────
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5 MB
        raise HTTPException(status_code=413, detail="CSV file too large (max 5 MB)")

    # ── Parse ──────────────────────────────────────────────────────────
    try:
        rows, column_map, unmapped = parse_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not rows:
        raise HTTPException(status_code=400, detail="CSV file has no data rows")

    if len(rows) > 10_000:
        raise HTTPException(status_code=413, detail="Too many rows (max 10 000 per import)")

    # ── Enrich ─────────────────────────────────────────────────────────
    rows = await _enrich_rows(rows)

    valid = [r for r in rows if r.valid]
    invalid = [r for r in rows if not r.valid]

    return ImportPreviewResponse(
        total_rows=len(rows),
        valid_rows=len(valid),
        invalid_rows=len(invalid),
        rows=[_parsed_to_import_row(r) for r in rows],
        mapped_columns=column_map,
        unmapped_columns=unmapped,
    )


@router.post("/portfolio/import", response_model=ImportResponse, status_code=201)
async def import_holdings(body: ImportRequest, db: AsyncSession = Depends(get_db)):
    """Bulk-import holdings from the preview payload.  All rows are assigned to the
    given account and inserted in a single transaction.
    """
    valid_rows = [r for r in body.rows if r.valid]
    if not valid_rows:
        raise HTTPException(status_code=400, detail="No valid rows to import")

    errors: list[ImportRowError] = []
    holdings: list[Holding] = []
    enriched_count = 0

    for row in valid_rows:
        try:
            holdings.append(Holding(
                ticker=(row.ticker or "").upper(),
                name=row.name or "",
                quantity=row.quantity or 0,
                cost_basis_per_share=row.cost_basis_per_share or 0,
                current_price=row.current_price or 0,
                account_id=body.account_id,
                type=row.type,
                asset_class=row.asset_class,
                sector=row.sector,
                geography=row.geography,
                currency=row.currency,
                ocf_pct=row.ocf_pct,
                dividend_yield_pct=row.dividend_yield_pct,
                isin=row.isin,
            ))
            if row.enriched:
                enriched_count += 1
        except Exception:
            errors.append(ImportRowError(
                row=row.row_number,
                ticker=row.ticker,
                reason="Failed to create holding",
            ))

    if not holdings:
        raise HTTPException(status_code=400, detail="No rows could be converted to holdings")

    db.add_all(holdings)
    await db.commit()

    return ImportResponse(
        imported=len(holdings),
        skipped=len(body.rows) - len(holdings),
        enriched_count=enriched_count,
        errors=errors,
    )
