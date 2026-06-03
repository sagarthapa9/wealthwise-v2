"""AI hook template selection logic.

Given the active tab, computed allocations, and personal context,
selects the right insight card template with real portfolio values interpolated.
"""

from dataclasses import dataclass
from typing import Literal

from app.services.portfolio_data import PersonalContext, PortfolioData, Holding, AllocationRow


@dataclass
class HookTemplate:
    insight: str
    prompt: str
    ai_question: str
    severity: Literal["info", "warning", "action"]


def select_hook_template(
    tab: Literal["asset_class", "sector", "geographic"],
    allocations: list[AllocationRow],
    data: PortfolioData,
) -> HookTemplate:
    personal = data.personal

    if tab == "asset_class":
        return _asset_class_hook(allocations, personal)
    elif tab == "sector":
        return _sector_hook(allocations, data)
    elif tab == "geographic":
        return _geography_hook(allocations, personal)
    else:
        return _generic_hook(personal)


# ── Asset class hooks ────────────────────────────────────────────────

def _asset_class_hook(allocations: list[AllocationRow], p: PersonalContext) -> HookTemplate:
    equity_row = next((r for r in allocations if r.label.lower() == "equity"), None)
    equity_pct = equity_row.percentage if equity_row else 0

    fixed_row = next((r for r in allocations if r.label.lower() == "fixed income"), None)
    fixed_pct = fixed_row.percentage if fixed_row else 0

    if equity_pct > 70:
        delta = round(equity_pct - 60)
        return HookTemplate(
            insight=f"Your equities are at {equity_pct}% — {delta}% more than a standard {p.risk_tolerance} profile.",
            prompt="Ask: Is my risk level right for my age?",
            ai_question=f"I'm {p.age} with a {p.risk_tolerance} risk tolerance and a {p.investment_horizon} horizon. My portfolio is {equity_pct}% equities. Is this appropriate for my situation? What should I consider changing?",
            severity="warning",
        )
    elif equity_pct < 30:
        return HookTemplate(
            insight=f"Your equities are only {equity_pct}% — conservative for a {p.age}-year-old with {p.investment_horizon} to retirement.",
            prompt="Ask: Am I too conservative?",
            ai_question=f"I'm {p.age} with a {p.investment_horizon} timeline and only {equity_pct}% in equities. Am I being too conservative? What's the growth risk I'm taking?",
            severity="info",
        )
    else:
        return HookTemplate(
            insight=f"Your {equity_pct}% equity allocation looks aligned with your {p.risk_tolerance} profile.",
            prompt="Ask: How should I rebalance?",
            ai_question=f"My portfolio is {equity_pct}% equities, {fixed_pct}% fixed income. How should I think about rebalancing? What's a good target allocation for someone my age?",
            severity="info",
        )


# ── Sector hooks ─────────────────────────────────────────────────────

def _sector_hook(allocations: list[AllocationRow], data: PortfolioData) -> HookTemplate:
    top = allocations[0] if allocations else None

    # Check for any sector > 30%
    if top and top.percentage > 30:
        return HookTemplate(
            insight=f"{top.label} makes up {top.percentage}% of your portfolio — a concentrated position.",
            prompt="Ask: Stress-test this concentration",
            ai_question=f"What happens to my portfolio if {top.label} drops 30%? I have {top.percentage}% of my portfolio in this sector.",
            severity="warning",
        )

    # Check for any single holding > 15%
    for h in data.all_holdings():
        h_pct = (h.value_gbp / data.total_value * 100) if data.total_value > 0 else 0
        if h_pct > 15:
            return HookTemplate(
                insight=f"{h.name} is {round(h_pct, 1)}% of your portfolio — that's a single-name concentration.",
                prompt="Ask: Analyse this holding",
                ai_question=f"Tell me about {h.name} — what are the key risks of having {round(h_pct, 1)}% of my portfolio in a single holding?",
                severity="action",
            )

    # Otherwise: diversified
    top_sector = top.label if top else "N/A"
    top_pct = top.percentage if top else 0
    return HookTemplate(
        insight=f"Your sector exposure is well-diversified. The largest sector is {top_sector} at {top_pct}%.",
        prompt="Ask: Any sector gaps?",
        ai_question="Looking at my sector allocation, what sectors am I underweight in? Are there any gaps I should consider?",
        severity="info",
    )


# ── Geography hooks ──────────────────────────────────────────────────

def _geography_hook(allocations: list[AllocationRow], p: PersonalContext) -> HookTemplate:
    top = allocations[0] if allocations else None

    # Any single geo > 50%
    if top and top.percentage > 50:
        return HookTemplate(
            insight=f"{top.label} exposure is {top.percentage}% — you're heavily weighted toward this market.",
            prompt="Ask: Geographic risk check",
            ai_question=f"I'm {top.percentage}% exposed to {top.label}. What are the single-market risks I should be aware of? Should I diversify geographically?",
            severity="warning",
        )

    # UK < 20% for UK investor
    uk_row = next((r for r in allocations if r.label.lower() == "uk"), None)
    uk_pct = uk_row.percentage if uk_row else 0
    if uk_pct < 20:
        return HookTemplate(
            insight=f"Only {uk_pct}% UK exposure — typical for a globally-diversified portfolio, but worth reviewing home bias.",
            prompt="Ask: UK exposure check",
            ai_question=f"I have only {uk_pct}% in UK assets. Is this too low for a UK-based investor? What are the pros and cons of more home bias?",
            severity="info",
        )

    # Otherwise
    top_geo = top.label if top else "N/A"
    top_pct = top.percentage if top else 0
    geo_count = len(allocations)
    return HookTemplate(
        insight=f"Your geographic spread is {geo_count} regions. Largest: {top_geo} at {top_pct}%.",
        prompt="Ask: Optimal geographic mix?",
        ai_question=f"What's an optimal geographic allocation for a UK-based investor with a {p.investment_horizon} horizon? How does my current mix compare?",
        severity="info",
    )


def _generic_hook(p: PersonalContext) -> HookTemplate:
    return HookTemplate(
        insight="Your portfolio overview is ready. Tap any tab to see detailed breakdowns.",
        prompt="Ask: Review my portfolio",
        ai_question=f"I'm {p.age} years old with a {p.risk_tolerance} risk tolerance. Can you review my overall portfolio allocation and suggest improvements?",
        severity="info",
    )
