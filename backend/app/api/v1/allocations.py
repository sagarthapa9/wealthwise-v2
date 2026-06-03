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

    Fields like asset_class, sector, geography are inferred from the ticker
    since the manual entry form doesn't capture them yet.
    """
    ticker = h.ticker.upper()
    name = h.name

    # Infer asset class, sector, geography from ticker
    asset_class = _infer_asset_class(ticker, name)
    sector = _infer_sector(ticker, asset_class)
    geography = _infer_geography(ticker)

    return DataHolding(
        ticker=ticker,
        name=name,
        type="ETF",  # Manual entry assumes ETFs for now
        asset_class=asset_class,
        sector=sector,
        geography=geography,
        quantity=int(h.quantity),
        cost_basis_pence=int(h.cost_basis_per_share * 100),
        current_price_pence=int(h.current_price * 100),
        currency="GBP",
    )


def _infer_asset_class(ticker: str, name: str) -> str:
    """Guess asset class from ticker prefix or fund name."""
    name_lower = name.lower()

    if any(k in name_lower for k in ["bond", "gilt", "fixed income", "corporate bond"]):
        return "fixed_income"
    if any(k in name_lower for k in ["cash", "money market"]):
        return "cash"
    if any(k in name_lower for k in ["property", "real estate"]):
        return "property"

    # Vanguard ticker conventions
    bond_prefixes = ["VAGP", "VAFG", "IGLT", "IGET"]
    if any(ticker.startswith(p) for p in bond_prefixes):
        return "fixed_income"

    # Default — most ETFs are equity
    return "equity"


def _infer_sector(ticker: str, asset_class: str) -> str:
    """Guess sector from ticker and asset class."""
    if asset_class == "fixed_income":
        return "government_bonds" if ticker.startswith("IGLT") else "corporate_bonds"
    if ticker.startswith("VUAG") or ticker.startswith("VUSA") or ticker.startswith("VOO"):
        return "us_large_cap"
    if ticker.startswith("VWRL") or ticker.startswith("VWRP") or ticker.startswith("HMWO"):
        return "global_diversified"
    if ticker.startswith("VHYG"):
        return "global_equity"
    if ticker.startswith("VAPX"):
        return "asia_pacific"
    return "global_diversified"


def _infer_geography(ticker: str) -> str:
    """Guess geography from ticker."""
    if ticker.startswith("VUAG") or ticker.startswith("VUSA") or ticker.startswith("VOO"):
        return "us"
    if ticker.startswith("VERX"):
        return "europe"
    if ticker.startswith("IGLT") or ticker.startswith("VUKG"):
        return "uk"
    if ticker.startswith("VAPX"):
        return "asia_pacific"
    if ticker.startswith("VDEM"):
        return "emerging_markets"
    return "global"


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
