"""
Portfolio CRUD endpoints — create, read, update, delete holdings + summary.
"""

from fastapi import APIRouter, Depends, HTTPException
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
