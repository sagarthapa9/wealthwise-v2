"""Prompt Builder — converts RawInsight → (visible_prompt, context_payload).

Each insight type has its own builder. A registry dict dispatches by insight.id.
"""

from app.services.insight_engine import RawInsight


def build_prompt_payload(insight: RawInsight) -> tuple[str, dict]:
    """Return (visible_prompt, context_payload) for an insight."""
    builder = _BUILDERS.get(insight.id)
    if builder is None:
        return _generic_prompt(insight)
    return builder(insight)


# ═══════════════════════════════════════════════════════════════════════════
#  Per-type builders
# ═══════════════════════════════════════════════════════════════════════════

def _sector_concentration(insight: RawInsight) -> tuple[str, dict]:
    d = insight.detector_data
    sector = _fmt_sector(d["sector"])
    pct = d["current_pct"]
    visible = (
        f"Can you explain why having {pct:.0f}% of my portfolio in {sector} is risky? "
        f"What's the recommended max allocation and how would you suggest I diversify?"
    )
    context = {
        "insight_type": "sector_concentration",
        "sector": d["sector"],
        "current_allocation_pct": pct,
        "holdings": d["holdings"],
    }
    return visible, context


def _top_performer(insight: RawInsight) -> tuple[str, dict]:
    d = insight.detector_data
    name = d["ticker"] or d["name"]
    visible = (
        f"{name} is my best performer at +{d['return_pct']:.0f}%. "
        f"Should I take some profit now or let it keep running? "
        f"What's the right approach for a long-term portfolio?"
    )
    context = {
        "insight_type": "top_performer",
        "ticker": d["ticker"],
        "name": d["name"],
        "return_pct": d["return_pct"],
        "position_pct_of_portfolio": d["position_pct"],
        "cost_basis": d.get("cost_basis"),
        "current_price": d.get("current_price"),
    }
    return visible, context


def _bottom_performer(insight: RawInsight) -> tuple[str, dict]:
    d = insight.detector_data
    name = d["ticker"] or d["name"]
    visible = (
        f"{name} is down {d['return_pct']:.0f}%. "
        f"Should I be concerned? What's the right move — hold, sell, or buy more?"
    )
    context = {
        "insight_type": "bottom_performer",
        "ticker": d["ticker"],
        "name": d["name"],
        "return_pct": d["return_pct"],
        "position_pct_of_portfolio": d["position_pct"],
    }
    return visible, context


def _tax_loss_harvesting(insight: RawInsight) -> tuple[str, dict]:
    d = insight.detector_data
    visible = (
        f"I have {len(d['holdings'])} holding(s) down in my GIA with about "
        f"£{d['total_unrealised_loss']:,.0f} in unrealised losses. "
        f"Can you walk me through which ones to sell for tax-loss harvesting "
        f"and what the tax implications would be?"
    )
    context = {
        "insight_type": "tax_loss_harvesting",
        "total_unrealised_loss": d["total_unrealised_loss"],
        "holdings": d["holdings"],
        "account_type": d["account_type"],
    }
    return visible, context


def _portfolio_drift(insight: RawInsight) -> tuple[str, dict]:
    d = insight.detector_data
    direction = d["direction"]
    visible = (
        f"My equity allocation is {d['current_equity_pct']:.0f}% vs a "
        f"{d['target_equity_pct']:.0f}% target — that's {d['drift_pct']:.0f}% "
        f"{direction} target. Can you show me what I'd need to buy or sell "
        f"to get back on track?"
    )
    context = {
        "insight_type": "portfolio_drift",
        "current_equity_pct": d["current_equity_pct"],
        "target_equity_pct": d["target_equity_pct"],
        "drift_pct": d["drift_pct"],
        "direction": direction,
        "risk_tolerance": d["risk_tolerance"],
    }
    return visible, context


def _cash_drag(insight: RawInsight) -> tuple[str, dict]:
    d = insight.detector_data
    account_label = f"{d.get('account_provider', '')} {d['account_type']}".strip()
    visible = (
        f"I've got £{d['cash_gbp']:,.0f} sitting in my {account_label} "
        f"({d['cash_pct']:.0f}% of portfolio) earning nothing. "
        f"Should I invest it or keep it as a cash buffer? What would you recommend?"
    )
    context = {
        "insight_type": "cash_drag",
        "cash_gbp": d["cash_gbp"],
        "cash_pct": d["cash_pct"],
        "account_type": d["account_type"],
        "cash_by_account": d.get("cash_by_account", []),
    }
    return visible, context


def _generic_prompt(insight: RawInsight) -> tuple[str, dict]:
    visible = f"Tell me more about: {insight.label}"
    context = {"insight_type": insight.id, "label": insight.label}
    return visible, context


def _fmt_sector(key: str) -> str:
    return key.replace("_", " ").title()


def _tax_efficiency(insight: RawInsight) -> tuple[str, dict]:
    d = insight.detector_data
    visible = (
        f"I'm only using £{d['isa_annual_contribution']:,} of my "
        f"£{d['isa_allowance']:,} ISA allowance ({d['pct_used']:.0f}%). "
        f"Should I increase my ISA contributions? What's the best way to "
        f"make use of the remaining £{d['unused_allowance']:,}?"
    )
    context = {
        "insight_type": "tax_efficiency",
        "isa_annual_contribution": d["isa_annual_contribution"],
        "isa_allowance": d["isa_allowance"],
        "unused_allowance": d["unused_allowance"],
        "pct_used": d["pct_used"],
        "isa_monthly": d["isa_monthly"],
    }
    return visible, context


def _cost_efficiency(insight: RawInsight) -> tuple[str, dict]:
    d = insight.detector_data
    visible = (
        f"{d['active_pct']:.0f}% of my holdings (£{d['active_value_gbp']:,.0f}) "
        f"are in active funds vs {d['passive_pct']:.0f}% in passive ETFs. "
        f"Am I paying too much in fees? What lower-cost alternatives should I consider?"
    )
    context = {
        "insight_type": "cost_efficiency",
        "active_pct": d["active_pct"],
        "active_value_gbp": d["active_value_gbp"],
        "passive_pct": d["passive_pct"],
        "active_holdings": d["active_holdings"],
    }
    return visible, context


_BUILDERS = {
    "sector_concentration": _sector_concentration,
    "top_performer": _top_performer,
    "bottom_performer": _bottom_performer,
    "tax_loss_harvesting": _tax_loss_harvesting,
    "portfolio_drift": _portfolio_drift,
    "cash_drag": _cash_drag,
    "tax_efficiency": _tax_efficiency,
    "cost_efficiency": _cost_efficiency,
}
