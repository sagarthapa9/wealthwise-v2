"""Portfolio data types and sample portfolio for MVP visualization."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class PersonalContext:
    age: int
    risk_tolerance: Literal["low", "moderate", "high"]
    investment_horizon: str
    primary_goal: str
    income_band: str
    tax_band: str
    pension_contributions_monthly: int
    isa_contributions_monthly: int


@dataclass
class Holding:
    ticker: str
    name: str
    type: Literal["ETF", "investment_trust", "fund", "stock", "bond"]
    asset_class: Literal["equity", "fixed_income", "cash", "alternative", "property"]
    sector: str
    geography: str
    quantity: int
    cost_basis_pence: int
    current_price_pence: int
    currency: Literal["GBP"] = "GBP"

    @property
    def value_gbp(self) -> float:
        return self.quantity * self.current_price_pence / 100

    @property
    def cost_gbp(self) -> float:
        return self.quantity * self.cost_basis_pence / 100

    @property
    def gain_loss_gbp(self) -> float:
        return self.value_gbp - self.cost_gbp

    @property
    def gain_loss_pct(self) -> float:
        if self.cost_gbp == 0:
            return 0
        return (self.value_gbp - self.cost_gbp) / self.cost_gbp * 100


@dataclass
class Account:
    provider: str
    account_type: Literal["SIPP", "ISA", "GIA", "LISA"]
    currency: Literal["GBP"] = "GBP"
    cash_balance: float = 0.0
    holdings: list[Holding] = field(default_factory=list)

    @property
    def holdings_value(self) -> float:
        return sum(h.value_gbp for h in self.holdings)

    @property
    def total_value(self) -> float:
        return self.holdings_value + self.cash_balance


@dataclass
class PortfolioData:
    personal: PersonalContext
    accounts: list[Account]

    @property
    def total_value(self) -> float:
        return sum(a.total_value for a in self.accounts)

    @property
    def total_cost(self) -> float:
        return sum(
            h.cost_gbp for a in self.accounts for h in a.holdings
        ) + sum(a.cash_balance for a in self.accounts)

    @property
    def total_gain_loss(self) -> float:
        return self.total_value - self.total_cost

    @property
    def total_gain_loss_pct(self) -> float:
        if self.total_cost == 0:
            return 0
        return (self.total_value - self.total_cost) / self.total_cost * 100

    def all_holdings(self) -> list[Holding]:
        return [h for a in self.accounts for h in a.holdings]


@dataclass
class AllocationSummary:
    total_value: float
    total_cost: float
    total_gain_loss: float
    total_gain_loss_pct: float


@dataclass
class AllocationRow:
    label: str
    value_gbp: float
    percentage: float
    color: str


# ── Color palette from spec ──────────────────────────────────────────

ASSET_CLASS_COLORS: dict[str, str] = {
    "equity": "#2563EB",
    "fixed_income": "#059669",
    "cash": "#D97706",
    "alternative": "#7C3AED",
    "property": "#DC2626",
}

GEOGRAPHY_COLORS: dict[str, str] = {
    "global": "#2563EB",
    "uk": "#DC2626",
    "us": "#7C3AED",
    "europe": "#059669",
    "emerging_markets": "#D97706",
    "asia_pacific": "#F59E0B",
}

SECTOR_COLORS: list[str] = [
    "#2563EB", "#059669", "#D97706", "#7C3AED", "#DC2626",
    "#F59E0B", "#10B981", "#3B82F6", "#EF4444", "#8B5CF6",
]
