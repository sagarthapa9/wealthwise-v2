"""LLMPortfolioContext builder — assembles the structured portfolio context payload.

This is the single most important piece of the LLM Analysis Engine. It reads
the user's portfolio data from the database, runs it through the existing
analysis services (health_score, insight_engine, portfolio_calc), and returns
the exact ``LLMPortfolioContext`` dict defined in the v1 spec.

Usage::

    context = await build_llm_context(db)
    system_prompt = build_system_prompt(context)
    # → feed to DeepSeek
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    compute_allocation_summary,
)
from app.services.health_score import compute_health_score, build_health_context
from app.services.insight_engine import generate_raw_insights, rank_insights, pick_top
from app.services.prompt_builder import build_prompt_payload


# ── Helpers ──────────────────────────────────────────────────────────────

def _orm_to_dataclass(h: ORMHolding) -> DataHolding:
    """Convert ORM Holding → PortfolioData Holding dataclass."""
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


# ── Main builder ─────────────────────────────────────────────────────────

async def build_llm_context(db: AsyncSession) -> dict:
    """Assemble the full LLMPortfolioContext payload.

    Returns a dict with all sections defined in the v1 spec:
      - personal         — user profile data
      - portfolio_snapshot — aggregated totals + asset class splits
      - accounts         — per-account breakdown with holdings
      - health_scores    — 5-dimension health scoring (overall + per dimension)
      - insights         — top 4 detected insights with prompts
      - tax_summary      — ISA/SIPP/GIA totals + allowance estimates
      - generated_at     — ISO timestamp
    """
    # ── 1. Load profile ──────────────────────────────────────────────
    profile_result = await db.execute(select(Profile).limit(1))
    db_profile = profile_result.scalar_one_or_none()

    if db_profile:
        personal = PersonalContext(
            age=db_profile.age,
            risk_tolerance=db_profile.risk_tolerance,
            investment_horizon=db_profile.investment_horizon,
            primary_goal=db_profile.primary_goal,
            income_band=db_profile.income_band,
            tax_band=db_profile.tax_band,
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

    # ── 2. Load holdings + accounts ──────────────────────────────────
    holdings_result = await db.execute(select(ORMHolding))
    orm_holdings = list(holdings_result.scalars().all())

    acct_result = await db.execute(
        select(AccountModel).order_by(AccountModel.created_at)
    )
    db_accounts = list(acct_result.scalars().all())

    # ── 3. Build PortfolioData ───────────────────────────────────────
    if db_accounts:
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
                account_type=acc.account_type,
                currency=acc.currency,
                cash_balance=acc.cash_balance,
                holdings=acc_holdings,
            ))
        # Ungrouped holdings go into a catch-all
        ungrouped = holdings_by_account.get(None, [])
        if ungrouped:
            accounts.append(Account(
                provider="Ungrouped", account_type="ISA",
                cash_balance=0.0, holdings=ungrouped,
            ))
    else:
        dataclass_holdings = [_orm_to_dataclass(h) for h in orm_holdings]
        accounts = [
            Account(
                provider="Manual Entry", account_type="ISA",
                cash_balance=0.0, holdings=dataclass_holdings,
            )
        ]

    data = PortfolioData(personal=personal, accounts=accounts)

    # ── 4. Portfolio snapshot ────────────────────────────────────────
    total_value = data.total_value
    total_cost = data.total_cost
    gain_loss = data.total_gain_loss
    gain_loss_pct = data.total_gain_loss_pct

    all_holdings_list = data.all_holdings()
    num_holdings = len(all_holdings_list)
    num_accounts = len(accounts)

    # Asset class splits
    asset_alloc = compute_asset_class_allocation(data)
    asset_map = {r.label: r.percentage for r in asset_alloc}

    # Weighted OCF (value-weighted average of all holdings)
    weighted_ocf = 0.0
    if total_value > 0 and all_holdings_list:
        total_ocf_value = sum(
            (h.ocf_pct or 0) * h.value_gbp
            for h in all_holdings_list
        )
        weighted_ocf = round(total_ocf_value / total_value, 4)

    portfolio_snapshot = {
        "total_value_gbp": round(total_value, 2),
        "total_cost_gbp": round(total_cost, 2),
        "total_gain_gbp": round(gain_loss, 2),
        "total_gain_pct": round(gain_loss_pct, 2),
        "equity_pct": round(asset_map.get("equity", 0), 1),
        "fixed_income_pct": round(asset_map.get("fixed_income", 0), 1),
        "cash_pct": round(asset_map.get("cash", 0), 1),
        "property_pct": round(asset_map.get("property", 0), 1),
        "commodity_pct": round(asset_map.get("commodity", 0), 1),
        "multi_asset_pct": round(asset_map.get("multi_asset", 0), 1),
        "unclassified_pct": round(asset_map.get("unclassified", 0), 1),
        "weighted_ocf": weighted_ocf,
        "num_holdings": num_holdings,
        "num_accounts": num_accounts,
    }

    # ── 5. Per-account breakdown ─────────────────────────────────────
    accounts_list = []
    for a in accounts:
        acct_holdings = []
        for h in a.holdings:
            pct_of_portfolio = (
                round(h.value_gbp / total_value * 100, 2)
                if total_value > 0 else 0
            )
            acct_holdings.append({
                "ticker": h.ticker,
                "name": h.name,
                "type": h.type,
                "asset_class": h.asset_class,
                "sector": h.sector,
                "geography": h.geography,
                "quantity": h.quantity,
                "cost_basis_pence": h.cost_basis_pence,
                "current_price_pence": h.current_price_pence,
                "value_gbp": round(h.value_gbp, 2),
                "pct_of_portfolio": pct_of_portfolio,
                "gain_gbp": round(h.gain_loss_gbp, 2),
                "gain_pct": round(h.gain_loss_pct, 2),
                "ocf_pct": getattr(h, 'ocf_pct', None),
                "dividend_yield_pct": None,  # not on dataclass
                "currency": h.currency,
                "isin": None,  # not on dataclass
            })

        accounts_list.append({
            "provider": a.provider,
            "account_type": a.account_type,
            "value_gbp": round(a.total_value, 2),
            "pct_of_total": round(a.total_value / total_value * 100, 1) if total_value > 0 else 0,
            "holdings": acct_holdings,
        })

    # ── 6. Health scores ─────────────────────────────────────────────
    health = compute_health_score(data)
    health_scores = {
        "overall": {
            "score": health["overall"],
            "grade": health["grade"],
        },
        "dimensions": [
            {
                "name": d["dimension"],
                "score": d["score"],
                "weight": 0,  # caller can look up from HEATH_WEIGHTS
                "detail": d["summary"],
            }
            for d in health["dimensions"]
        ],
    }

    # ── 7. Insights (top 4, ranked) ──────────────────────────────────
    raw_insights = generate_raw_insights(data)
    ranked = rank_insights(raw_insights)
    top = pick_top(ranked, 4)

    insights_list = []
    for ins in top:
        prompt_text, _ = build_prompt_payload(ins)
        insights_list.append({
            "severity": _severity_map(ins.type),
            "type": ins.id,
            "title": ins.label,
            "detail": str(ins.detector_data),
            "prompt": prompt_text,
        })

    # ── 8. Tax summary — computed from account types ────────────────
    isa_value = sum(
        a.total_value for a in accounts
        if a.account_type in ("ISA", "LISA")
    )
    sipp_value = sum(
        a.total_value for a in accounts
        if a.account_type == "SIPP"
    )
    gia_value = sum(
        a.total_value for a in accounts
        if a.account_type == "GIA"
    )

    isa_annual = personal.isa_contributions_monthly * 12
    pension_annual = personal.pension_contributions_monthly * 12

    # Estimate CGT exposure: sum of gains in GIA
    gia_gains = sum(
        h.gain_loss_gbp for a in accounts if a.account_type == "GIA"
        for h in a.holdings if h.gain_loss_gbp > 0
    )

    tax_summary = {
        "isa_total_gbp": round(isa_value, 2),
        "isa_allowance_remaining": max(0, 20000 - isa_annual),
        "sipp_total_gbp": round(sipp_value, 2),
        "sipp_annual_allowance_remaining": max(0, 60000 - pension_annual),
        "gia_total_gbp": round(gia_value, 2),
        "gia_estimated_cgt_exposure": round(gia_gains, 2),
        "gia_dividend_income_estimate": 0,  # requires yield data per holding
        "pension_lta_concern": "none",
    }

    # ── 9. Return ────────────────────────────────────────────────────
    from datetime import datetime, timezone

    return {
        "personal": {
            "country": "UK",
            "age": personal.age,
            "risk_tolerance": personal.risk_tolerance,
            "investment_horizon_years": personal.investment_horizon,
            "monthly_savings": personal.pension_contributions_monthly + personal.isa_contributions_monthly,
            "goal": personal.primary_goal,
            "tax_band": personal.tax_band,
            "pension_contributions_monthly": personal.pension_contributions_monthly,
            "isa_contributions_monthly": personal.isa_contributions_monthly,
            "retirement_age_target": None,
            "employment_status": None,
            "dependents": None,
            "mortgage_remaining": None,
            "annual_income": None,
        },
        "portfolio_snapshot": portfolio_snapshot,
        "accounts": accounts_list,
        "health_scores": health_scores,
        "insights": insights_list,
        "tax_summary": tax_summary,
        "benchmark": None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Utilities ────────────────────────────────────────────────────────────

def _severity_map(insight_type: str) -> str:
    """Map insight type to severity for the LLM context."""
    mapping = {
        "risk": "warning",
        "alert": "critical",
        "opportunity": "info",
        "behavioural": "info",
    }
    return mapping.get(insight_type, "info")
