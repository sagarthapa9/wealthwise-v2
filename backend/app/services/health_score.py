"""Portfolio Health Score Engine.

Five weighted dimensions scored 0-10, graded A-E. Works directly with
PortfolioData — no DataFrame dependency.

All dimension scorers are pure functions: they take a PortfolioData and
return a dict with keys ``dimension``, ``score``, and ``summary``.
"""

from dataclasses import dataclass
from typing import Literal

from app.services.portfolio_data import PortfolioData, Holding, Account

# ══════════════════════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════════════════════

WEIGHTS: dict[str, float] = {
    "Risk Alignment": 0.30,
    "Diversification": 0.25,
    "Tax Efficiency": 0.20,
    "Cost Efficiency": 0.15,
    "Cash Management": 0.10,
}

GRADE_THRESHOLDS: list[tuple[float, str]] = [
    (9.0, "A"),
    (7.5, "B"),
    (6.0, "C"),
    (4.0, "D"),
]

EQUITY_TARGETS: dict[str, float] = {
    "low": 30,
    "moderate": 60,
    "high": 85,
}


def _grade(score: float) -> str:
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "E"


# ══════════════════════════════════════════════════════════════════════════
#  Helpers (pure, reusable)
# ══════════════════════════════════════════════════════════════════════════

def _all_holdings(data: PortfolioData) -> list[Holding]:
    return [h for a in data.accounts for h in a.holdings]


def _total_holdings_value(data: PortfolioData) -> float:
    return sum(h.value_gbp for h in _all_holdings(data))


def _total_cash(data: PortfolioData) -> float:
    return sum(a.cash_balance for a in data.accounts)


def _total_portfolio_value(data: PortfolioData) -> float:
    return _total_holdings_value(data) + _total_cash(data)


def _group_by(data: PortfolioData, attr: str) -> dict[str, float]:
    """Sum holding values grouped by *attr* (e.g. 'asset_class', 'sector')."""
    groups: dict[str, float] = {}
    for h in _all_holdings(data):
        key = getattr(h, attr, "unknown")
        groups[key] = groups.get(key, 0) + h.value_gbp
    return groups


# ══════════════════════════════════════════════════════════════════════════
#  Dimension scorers
# ══════════════════════════════════════════════════════════════════════════

def score_risk_alignment(data: PortfolioData) -> dict:
    """Compare equity % against risk-tolerance target."""
    p = data.personal
    equity_value = _group_by(data, "asset_class").get("equity", 0)
    total = _total_holdings_value(data)
    equity_pct = (equity_value / total * 100) if total > 0 else 0

    target = EQUITY_TARGETS.get(p.risk_tolerance, 60)
    gap = abs(equity_pct - target)

    if gap <= 5:
        return {"dimension": "Risk Alignment", "score": 10,
                "summary": f"Allocation matches {p.risk_tolerance} risk profile"}
    if gap <= 10:
        return {"dimension": "Risk Alignment", "score": 8,
                "summary": f"Minor drift: {equity_pct:.0f}% equities vs {target}% target"}
    if gap <= 20:
        return {"dimension": "Risk Alignment", "score": 6,
                "summary": f"Moderate gap: {equity_pct:.0f}% equities vs {target}% target"}
    if gap <= 35:
        return {"dimension": "Risk Alignment", "score": 4,
                "summary": f"Significant gap: {equity_pct:.0f}% equities vs {target}% target"}
    return {"dimension": "Risk Alignment", "score": 2,
            "summary": f"Critical gap: {equity_pct:.0f}% equities vs {target}% target"}


def score_diversification(data: PortfolioData) -> dict:
    """Penalise sector concentration, single-name risk, and limited geo/asset spread."""
    deductions = 0
    details: list[str] = []
    total = _total_holdings_value(data)

    if total == 0:
        return {"dimension": "Diversification", "score": 0, "summary": "No holdings"}

    # Sector concentration
    sectors = _group_by(data, "sector")
    for label, val in sectors.items():
        pct = val / total * 100
        if pct > 30:
            deductions += 3
            details.append(f"{label.replace('_', ' ').title()} concentrated: {pct:.0f}%")
        elif pct > 20:
            deductions += 1

    # Single-holding risk
    for h in _all_holdings(data):
        pct = h.value_gbp / total * 100
        if pct > 15:
            deductions += 2

    # Geographic spread
    geos = _group_by(data, "geography")
    if len(geos) < 3:
        deductions += 2
        details.append(f"Limited geographic spread ({len(geos)} {'region' if len(geos) == 1 else 'regions'})")

    # Asset class spread
    asset_classes = _group_by(data, "asset_class")
    if len(asset_classes) < 3:
        deductions += 1
        details.append(f"Only {len(asset_classes)} asset {'class' if len(asset_classes) == 1 else 'classes'}")

    score = max(10 - deductions, 1)
    summary = details[0] if details else "Well diversified across sectors, geographies, and asset classes"
    return {"dimension": "Diversification", "score": score, "summary": summary}


def score_tax_efficiency(data: PortfolioData) -> dict:
    """Score based on % of portfolio in tax-advantaged wrappers (SIPP, ISA, LISA)."""
    p = data.personal
    total = _total_portfolio_value(data)

    sheltered = sum(
        a.cash_balance + sum(h.value_gbp for h in a.holdings)
        for a in data.accounts
        if a.account_type in ("SIPP", "ISA", "LISA")
    )
    sheltered_pct = (sheltered / total * 100) if total > 0 else 0

    gia_total = sum(
        a.cash_balance + sum(h.value_gbp for h in a.holdings)
        for a in data.accounts
        if a.account_type == "GIA"
    )

    multiplier = 1.0
    detail = f"{sheltered_pct:.0f}% in tax-advantaged wrappers"

    if p.tax_band in ("higher_rate", "additional_rate") and sheltered_pct < 80:
        multiplier = 0.6
        detail = f"£{gia_total:,.0f} in GIA — move to ISA/SIPP to shelter gains"

    if gia_total == 0 and sheltered_pct >= 80:
        detail = f"{sheltered_pct:.0f}% tax-sheltered — well structured"

    raw_score = min(sheltered_pct / 10, 10)
    return {"dimension": "Tax Efficiency", "score": round(raw_score * multiplier, 1),
            "summary": detail}


def score_cost_efficiency(data: PortfolioData) -> dict:
    """Score cost efficiency. Stub until fee data is added to holdings."""
    return {"dimension": "Cost Efficiency", "score": 8,
            "summary": "Cost data pending — add fee_pct to holdings"}


def score_cash_management(data: PortfolioData) -> dict:
    """Penalise excessive cash drag."""
    cash = _total_cash(data)
    total = _total_portfolio_value(data)
    pct = (cash / total * 100) if total > 0 else 0

    if pct <= 2:
        return {"dimension": "Cash Management", "score": 10,
                "summary": "Minimal cash drag"}
    if pct <= 5:
        return {"dimension": "Cash Management", "score": 8,
                "summary": "Low cash position"}
    if pct <= 10:
        return {"dimension": "Cash Management", "score": 6,
                "summary": f"{pct:.0f}% in cash — moderate drag"}
    if pct <= 20:
        return {"dimension": "Cash Management", "score": 4,
                "summary": f"£{cash:,.0f} in cash — significant drag"}
    return {"dimension": "Cash Management", "score": 2,
            "summary": f"£{cash:,.0f} earning 0% — high cash drag"}


# ══════════════════════════════════════════════════════════════════════════
#  Aggregation
# ══════════════════════════════════════════════════════════════════════════

_SCORERS = [
    score_risk_alignment,
    score_diversification,
    score_tax_efficiency,
    score_cost_efficiency,
    score_cash_management,
]


def compute_health_score(data: PortfolioData) -> dict:
    """Return full health report for *data*.

    Returns a dict with keys:
        overall  — weighted score 0-10
        grade    — letter grade A-E
        dimensions — list of {dimension, score, summary} dicts
        top_findings — up to 3 lowest-scoring dimensions (score < 8)
    """
    dimensions = [scorer(data) for scorer in _SCORERS]

    overall = round(sum(
        d["score"] * WEIGHTS[d["dimension"]]
        for d in dimensions
    ), 1)

    return {
        "overall": overall,
        "grade": _grade(overall),
        "dimensions": dimensions,
        "top_findings": _build_findings(dimensions),
    }


def _build_findings(dimensions: list[dict]) -> list[dict]:
    """Return up to 3 lowest-scoring dimensions below 8."""
    sorted_dims = sorted(dimensions, key=lambda d: d["score"])
    return [d for d in sorted_dims if d["score"] < 8][:3]


# ══════════════════════════════════════════════════════════════════════════
#  AI context helper — formats health scores for system-prompt injection
# ══════════════════════════════════════════════════════════════════════════

def build_health_context(data: PortfolioData) -> str:
    """Build a health-score summary string for AI system-prompt injection."""
    report = compute_health_score(data)
    lines = [
        f"Portfolio Health: {report['grade']} ({report['overall']}/10)",
        "",
    ]
    for dim in report["dimensions"]:
        lines.append(f"  {dim['dimension']}: {dim['score']}/10 — {dim['summary']}")
    if report["top_findings"]:
        lines.append("")
        lines.append("Top areas to address:")
        for f in report["top_findings"]:
            lines.append(f"  • {f['dimension']}: {f['summary']}")
    return "\n".join(lines)
