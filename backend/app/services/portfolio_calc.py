"""Portfolio calculation utilities.

All functions take ``PortfolioData`` and return allocation lists.
Percentages are relative to total portfolio value including cash.
"""

from app.services.portfolio_data import (
    PortfolioData,
    AllocationRow,
    AllocationSummary,
    ASSET_CLASS_COLORS,
    GEOGRAPHY_COLORS,
    SECTOR_COLORS,
)


def filter_to_account(data: PortfolioData, account_index: int | None) -> PortfolioData:
    """Return *data* filtered to a single account, or all accounts if *account_index* is None."""
    if account_index is None or account_index < 0:
        return data
    return PortfolioData(
        personal=data.personal,
        accounts=[data.accounts[account_index]],
    )


def compute_allocation_summary(data: PortfolioData) -> AllocationSummary:
    return AllocationSummary(
        total_value=data.total_value,
        total_cost=data.total_cost,
        total_gain_loss=data.total_gain_loss,
        total_gain_loss_pct=data.total_gain_loss_pct,
    )


def compute_asset_class_allocation(data: PortfolioData) -> list[AllocationRow]:
    groups: dict[str, float] = {}
    for h in data.all_holdings():
        key = h.asset_class
        groups[key] = groups.get(key, 0) + h.value_gbp

    # Add cash from all accounts
    total_cash = sum(a.cash_balance for a in data.accounts)
    if total_cash > 0:
        groups["cash"] = groups.get("cash", 0) + total_cash

    total = data.total_value
    result: list[AllocationRow] = []
    for label, value in groups.items():
        pct = (value / total * 100) if total > 0 else 0
        color = ASSET_CLASS_COLORS.get(label, "#64748B")
        result.append(AllocationRow(
            label=_format_asset_class_label(label),
            value_gbp=round(value, 2),
            percentage=round(pct, 1),
            color=color,
        ))
    result.sort(key=lambda r: r.percentage, reverse=True)
    return result


def compute_sector_allocation(data: PortfolioData) -> list[AllocationRow]:
    groups: dict[str, float] = {}
    for h in data.all_holdings():
        key = h.sector
        groups[key] = groups.get(key, 0) + h.value_gbp

    total = data.total_value
    result: list[AllocationRow] = []
    for i, (label, value) in enumerate(sorted(groups.items(), key=lambda x: x[1], reverse=True)):
        pct = (value / total * 100) if total > 0 else 0
        color = SECTOR_COLORS[i % len(SECTOR_COLORS)]
        result.append(AllocationRow(
            label=_format_label(label),
            value_gbp=round(value, 2),
            percentage=round(pct, 1),
            color=color,
        ))
    return result


def compute_geographic_allocation(data: PortfolioData) -> list[AllocationRow]:
    groups: dict[str, float] = {}
    for h in data.all_holdings():
        key = h.geography
        groups[key] = groups.get(key, 0) + h.value_gbp

    total = data.total_value
    result: list[AllocationRow] = []
    for label, value in sorted(groups.items(), key=lambda x: x[1], reverse=True):
        pct = (value / total * 100) if total > 0 else 0
        color = GEOGRAPHY_COLORS.get(label, "#64748B")
        result.append(AllocationRow(
            label=_format_label(label),
            value_gbp=round(value, 2),
            percentage=round(pct, 1),
            color=color,
        ))
    return result


def _format_asset_class_label(key: str) -> str:
    return key.replace("_", " ").title()


def _format_label(key: str) -> str:
    return key.replace("_", " ").title()
