"""Portfolio Insight Engine — pure detectors that surface data-driven observations.

Each detector is a standalone function (PortfolioData) -> RawInsight | None.
Detectors are wrapped in try/except by generate_raw_insights() so a single
failure does not crash the UI.
"""

from dataclasses import dataclass, field
from app.services.portfolio_data import PortfolioData


@dataclass
class RawInsight:
    """Intermediate detection result — before prompt building."""
    id: str
    type: str            # "risk" | "opportunity" | "alert" | "behavioural"
    emoji: str
    label: str
    priority: int        # 1-100, higher = more important
    detector_data: dict  # raw numbers used by PromptBuilder


@dataclass
class Insight:
    """Fully built insight ready for rendering."""
    id: str
    type: str
    emoji: str
    label: str
    priority: int
    visible_prompt: str
    context_payload: dict


# ═══════════════════════════════════════════════════════════════════════════
#  Detectors
# ═══════════════════════════════════════════════════════════════════════════

def detect_sector_concentration(data: PortfolioData) -> RawInsight | None:
    """Fire when any single sector exceeds 50% of holdings value."""
    holdings = data.all_holdings()
    if not holdings:
        return None

    sector_values: dict[str, float] = {}
    for h in holdings:
        sector_values[h.sector] = sector_values.get(h.sector, 0) + h.value_gbp

    total_holdings = sum(sector_values.values())
    if total_holdings <= 0:
        return None

    max_sector = max(sector_values, key=sector_values.get)
    max_pct = sector_values[max_sector] / total_holdings * 100

    if max_pct <= 50:
        return None

    priority = min(70 + int(max_pct - 50), 100)
    sector_holdings = [
        {"name": h.name, "ticker": h.ticker, "value_gbp": h.value_gbp,
         "pct": h.value_gbp / total_holdings * 100}
        for h in holdings if h.sector == max_sector
    ]

    return RawInsight(
        id="sector_concentration",
        type="risk",
        emoji="\U0001f44e",  # thumbs down
        label=f"{_format_sector(max_sector)} is {max_pct:.0f}% of your portfolio",
        priority=priority,
        detector_data={
            "sector": max_sector,
            "current_pct": round(max_pct, 1),
            "holdings": sector_holdings,
        },
    )


def detect_top_bottom_performer(data: PortfolioData) -> RawInsight | None:
    """Fire for best gain >+20% or worst loss >-20%."""
    holdings = data.all_holdings()
    if not holdings:
        return None

    best = max(holdings, key=lambda h: h.gain_loss_pct)
    worst = min(holdings, key=lambda h: h.gain_loss_pct)

    # Check worst performer first (alerts are more actionable)
    if worst.gain_loss_pct <= -20:
        name = worst.name if not worst.ticker else f"{worst.ticker} ({worst.name})"
        return RawInsight(
            id="bottom_performer",
            type="alert",
            emoji="\U0001f44e",  # thumbs down
            label=f"{worst.ticker or worst.name} is down {worst.gain_loss_pct:+.0f}%",
            priority=80,
            detector_data={
                "ticker": worst.ticker,
                "name": worst.name,
                "return_pct": round(worst.gain_loss_pct, 1),
                "position_pct": round(worst.value_gbp / data.total_value * 100, 1) if data.total_value > 0 else 0,
                "value_gbp": worst.value_gbp,
            },
        )

    if best.gain_loss_pct >= 20:
        display = best.ticker or best.name
        return RawInsight(
            id="top_performer",
            type="opportunity",
            emoji="\U0001f44d",  # thumbs up
            label=f"{display} up {best.gain_loss_pct:+.0f}%",
            priority=70,
            detector_data={
                "ticker": best.ticker,
                "name": best.name,
                "return_pct": round(best.gain_loss_pct, 1),
                "position_pct": round(best.value_gbp / data.total_value * 100, 1) if data.total_value > 0 else 0,
                "value_gbp": best.value_gbp,
                "cost_basis": best.cost_gbp,
                "current_price": best.current_price_pence / 100,
            },
        )

    return None


def detect_tax_loss_harvesting(data: PortfolioData) -> RawInsight | None:
    """Fire when unrealised losses in GIA accounts exceed £1,000."""
    gia_accounts = [a for a in data.accounts if a.account_type == "GIA"]
    if not gia_accounts:
        return None

    losing: list[dict] = []
    total_loss = 0.0
    for acc in gia_accounts:
        for h in acc.holdings:
            if h.gain_loss_gbp < 0:
                loss = abs(h.gain_loss_gbp)
                total_loss += loss
                losing.append({
                    "ticker": h.ticker,
                    "name": h.name,
                    "loss_pct": round(h.gain_loss_pct, 1),
                    "loss_gbp": round(loss, 2),
                })

    if total_loss < 1000:
        return None

    return RawInsight(
        id="tax_loss_harvesting",
        type="alert",
        emoji="\U0001f44e",  # thumbs down
        label=f"{len(losing)} holding{'s' if len(losing)!=1 else ''} down ~£{total_loss:,.0f} in losses",
        priority=85,
        detector_data={
            "total_unrealised_loss": round(total_loss, 2),
            "holdings": losing,
            "account_type": "GIA",
        },
    )


def detect_portfolio_drift(data: PortfolioData) -> RawInsight | None:
    """Fire when equity % deviates >5% from risk-tolerance target."""
    if data.total_value <= 0:
        return None

    equity_value = sum(
        h.value_gbp for a in data.accounts for h in a.holdings
        if h.asset_class == "equity"
    )
    equity_pct = equity_value / data.total_value * 100

    target_map = {"low": 30, "moderate": 60, "high": 85}
    target = target_map.get(data.personal.risk_tolerance, 60)
    drift = abs(equity_pct - target)

    if drift <= 5:
        return None

    direction = "above" if equity_pct > target else "below"
    priority = min(50 + int(drift * 2), 75)

    return RawInsight(
        id="portfolio_drift",
        type="behavioural",
        emoji="\U0001f44e",  # thumbs down
        label=f"Equity allocation {equity_pct:.0f}% vs {target}% target ({drift:.0f}% {direction})",
        priority=priority,
        detector_data={
            "current_equity_pct": round(equity_pct, 1),
            "target_equity_pct": target,
            "drift_pct": round(drift, 1),
            "direction": direction,
            "risk_tolerance": data.personal.risk_tolerance,
        },
    )


def detect_cash_drag(data: PortfolioData) -> RawInsight | None:
    """Fire when cash exceeds 15% of portfolio or £10,000."""
    if data.total_value <= 0:
        return None

    total_cash = sum(a.cash_balance for a in data.accounts)
    cash_pct = total_cash / data.total_value * 100

    if cash_pct <= 15 and total_cash <= 10000:
        return None

    # Find the account with the most cash
    cash_accounts = sorted(data.accounts, key=lambda a: a.cash_balance, reverse=True)
    primary = cash_accounts[0]

    priority = min(40 + int(cash_pct * 2), 70)

    return RawInsight(
        id="cash_drag",
        type="alert",
        emoji="\U0001f44e",  # thumbs down
        label=f"£{total_cash:,.0f} cash ({cash_pct:.0f}% of portfolio) across {len([a for a in data.accounts if a.cash_balance > 0])} account(s)",
        priority=priority,
        detector_data={
            "cash_gbp": round(total_cash, 2),
            "cash_pct": round(cash_pct, 1),
            "account_type": primary.account_type,
            "account_provider": primary.provider,
            "cash_by_account": [
                {"provider": a.provider, "type": a.account_type,
                 "cash": a.cash_balance}
                for a in cash_accounts if a.cash_balance > 0
            ],
        },
    )


def detect_tax_efficiency(data: PortfolioData) -> RawInsight | None:
    """Fire when ISA contributions are well below the annual £20k allowance."""
    isa_monthly = data.personal.isa_contributions_monthly
    isa_annual = isa_monthly * 12
    allowance = 20_000
    unused = allowance - isa_annual

    # Only fire if at least £5k of allowance is unused
    if unused < 5000:
        return None

    pct_used = isa_annual / allowance * 100

    return RawInsight(
        id="tax_efficiency",
        type="opportunity",
        emoji="\U0001f44d",  # thumbs up
        label=f"Using £{isa_annual:,}/yr of your £{allowance:,} ISA allowance ({pct_used:.0f}%)",
        priority=65,
        detector_data={
            "isa_annual_contribution": isa_annual,
            "isa_allowance": allowance,
            "unused_allowance": unused,
            "pct_used": round(pct_used, 1),
            "isa_monthly": isa_monthly,
        },
    )


def detect_cost_efficiency(data: PortfolioData) -> RawInsight | None:
    """Fire when active funds make up >20% of holdings value vs passive ETFs."""
    holdings = data.all_holdings()
    if not holdings:
        return None

    active_value = sum(
        h.value_gbp for h in holdings
        if h.type in ("fund", "investment_trust")
    )
    total_holdings = sum(h.value_gbp for h in holdings)

    if total_holdings <= 0:
        return None

    active_pct = active_value / total_holdings * 100

    if active_pct <= 20:
        return None

    active_names = [
        {"name": h.name, "type": h.type, "value_gbp": h.value_gbp}
        for h in holdings if h.type in ("fund", "investment_trust")
    ]

    return RawInsight(
        id="cost_efficiency",
        type="alert",
        emoji="\U0001f44e",  # thumbs down
        label=f"{active_pct:.0f}% of holdings in active funds — consider lower-cost ETFs",
        priority=60,
        detector_data={
            "active_pct": round(active_pct, 1),
            "active_value_gbp": round(active_value, 2),
            "total_holdings_gbp": round(total_holdings, 2),
            "active_holdings": active_names,
            "passive_pct": round(100 - active_pct, 1),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════════════

DETECTORS = [
    detect_sector_concentration,
    detect_top_bottom_performer,
    detect_tax_loss_harvesting,
    detect_portfolio_drift,
    detect_cash_drag,
    detect_tax_efficiency,
    detect_cost_efficiency,
]


def generate_raw_insights(data: PortfolioData) -> list[RawInsight]:
    """Run all detectors. Each is wrapped so one failure doesn't crash the UI."""
    results: list[RawInsight] = []
    for detector in DETECTORS:
        try:
            result = detector(data)
            if result is not None:
                results.append(result)
        except Exception:
            pass
    return results


def rank_insights(raws: list[RawInsight]) -> list[RawInsight]:
    """Sort by priority descending."""
    return sorted(raws, key=lambda r: r.priority, reverse=True)


def pick_top(raws: list[RawInsight], count: int = 4) -> list[RawInsight]:
    """Return top N insights."""
    return raws[:count]


def _format_sector(key: str) -> str:
    return key.replace("_", " ").title()
