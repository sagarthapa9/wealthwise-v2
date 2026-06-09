"""
Allocations endpoint — computes asset class, sector, and geographic breakdowns
for the portfolio, plus the tab-specific insight hook template.

Reuses the existing ``services/portfolio_calc.py`` and ``services/hook_templates.py``.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.holding import Holding as ORMHolding
from app.models.profile import Profile
from app.models.account import Account as AccountModel

from app.services.portfolio_data import (
    PortfolioData,
    Account,
    Holding as DataHolding,
    PersonalContext,
)
from app.services.portfolio_calc import (
    compute_asset_class_allocation,
    compute_sector_allocation,
    compute_geographic_allocation,
)
from app.services.hook_templates import select_hook_template

router = APIRouter(tags=["allocations"])


def _orm_to_dataclass(h: ORMHolding) -> DataHolding:
    """Convert a DB Holding ORM row into a PortfolioData Holding dataclass.

    Uses the classification fields stored on the holding from the ticker
    provider lookup (type, asset_class, sector, geography, currency, etc.).
    These were auto-populated when the holding was added via TickerSearch.
    """
    return DataHolding(
        ticker=h.ticker.upper(),
        name=h.name,
        type=h.type or "ETF",
        asset_class=h.asset_class or "equity",
        sector=h.sector or "global_diversified",
        geography=h.geography or "global",
        quantity=int(h.quantity),
        cost_basis_pence=int(h.cost_basis_per_share * 100),
        current_price_pence=int(h.current_price * 100),
        currency=h.currency or "GBP",
        ocf_pct=h.ocf_pct,
        dividend_yield_pct=h.dividend_yield_pct,
    )


@router.get("/portfolio/allocations")
async def get_allocations(
    tab: Literal["asset_class", "sector", "geographic"] = "asset_class",
    db: AsyncSession = Depends(get_db),
):
    """Return allocation breakdowns for all three dimensions plus the insight hook.

    The ``tab`` query param selects which tab's hook template to return.
    """
    # 1. Fetch holdings from DB
    result = await db.execute(select(ORMHolding))
    orm_holdings = result.scalars().all()

    if not orm_holdings:
        return {
            "asset_class": [],
            "sector": [],
            "geographic": [],
            "hook": {
                "insight": "Add holdings to see your allocation breakdown",
                "prompt": "Ask: Analyse my portfolio",
                "ai_question": "I haven't added any holdings yet. Can you help me understand how to build a diversified portfolio?",
                "severity": "info",
                "tooltip": "Your portfolio is empty. Add holdings using the search bar above, then revisit this section for a detailed allocation breakdown.",
            },
        }

    # 2. Fetch profile from DB (or use defaults)
    profile_result = await db.execute(select(Profile).limit(1))
    db_profile = profile_result.scalar_one_or_none()
    if db_profile:
        personal = PersonalContext(
            age=db_profile.age,
            risk_tolerance=db_profile.risk_tolerance,  # type: ignore
            investment_horizon=db_profile.investment_horizon,
            primary_goal=db_profile.primary_goal,
            income_band=db_profile.income_band,
            tax_band=db_profile.tax_band,  # type: ignore
            pension_contributions_monthly=db_profile.pension_contributions_monthly,
            isa_contributions_monthly=db_profile.isa_contributions_monthly,
        )
    else:
        personal = PersonalContext(
            age=30, risk_tolerance="moderate",
            investment_horizon="5+ years", primary_goal="wealth accumulation",
            income_band="£50k-£100k", tax_band="basic_rate",
            pension_contributions_monthly=0, isa_contributions_monthly=0,
        )

    # 3. Group holdings by account (or put all in a single default account)
    acct_result = await db.execute(select(AccountModel).order_by(AccountModel.created_at))
    db_accounts = acct_result.scalars().all()

    if db_accounts:
        # Build a lookup: account_id -> list of dataclass holdings
        holdings_by_account: dict[int | None, list[DataHolding]] = {}
        for h in orm_holdings:
            key = h.account_id
            if key not in holdings_by_account:
                holdings_by_account[key] = []
            holdings_by_account[key].append(_orm_to_dataclass(h))

        accounts: list[Account] = []
        for acc in db_accounts:
            acc_holdings = holdings_by_account.get(acc.id, [])
            accounts.append(Account(
                provider=acc.provider,
                account_type=acc.account_type,  # type: ignore
                currency=acc.currency,  # type: ignore
                cash_balance=acc.cash_balance,
                holdings=acc_holdings,
            ))
        # Ungrouped holdings (account_id is None) go into a catch-all
        ungrouped = holdings_by_account.get(None, [])
        if ungrouped:
            accounts.append(Account(
                provider="Ungrouped", account_type="ISA",
                cash_balance=0.0, holdings=ungrouped,
            ))
    else:
        # No accounts table yet — all holdings go into one default account
        dataclass_holdings = [_orm_to_dataclass(h) for h in orm_holdings]
        accounts = [
            Account(
                provider="Manual Entry", account_type="ISA",
                cash_balance=0.0, holdings=dataclass_holdings,
            )
        ]

    data = PortfolioData(personal=personal, accounts=accounts)

    # 3. Compute all three allocation dimensions
    asset_class = compute_asset_class_allocation(data)
    sector = compute_sector_allocation(data)
    geographic = compute_geographic_allocation(data)

    # 4. Build the hook template for the active tab
    # select_hook_template needs the specific allocation list for the current tab
    tab_allocations = {
        "asset_class": asset_class,
        "sector": sector,
        "geographic": geographic,
    }[tab]
    hook = select_hook_template(tab, tab_allocations, data)

    # 5. Return as JSON
    return {
        "asset_class": [_row_to_dict(r) for r in asset_class],
        "sector": [_row_to_dict(r) for r in sector],
        "geographic": [_row_to_dict(r) for r in geographic],
        "hook": {
            "insight": hook.insight,
            "prompt": hook.prompt,
            "ai_question": hook.ai_question,
            "severity": hook.severity,
            "tooltip": hook.tooltip,
        },
    }


def _row_to_dict(r) -> dict:
    """Convert AllocationRow dataclass to a plain dict for JSON serialisation."""
    return {
        "label": r.label,
        "value_gbp": r.value_gbp,
        "percentage": r.percentage,
        "color": r.color,
    }
