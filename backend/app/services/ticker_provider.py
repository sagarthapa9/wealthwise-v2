"""
Abstract ticker data provider interface + YFinance implementation.

Usage::

    provider = get_ticker_provider()
    data = await provider.lookup("VWRL")
    # => TickerData(ticker="VWRL", name="...", price=137.58, ...)

To add a new provider (Alpha Vantage, Morningstar, etc.):
1. Subclass ``TickerProvider``
2. Implement ``async lookup(symbol) -> TickerData``
3. Add it to ``get_ticker_provider()``

Switching providers is a config/env change — no endpoint code touches yfinance directly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

import yfinance as yf

from app.services.classification import (
    map_asset_class,
    map_geography,
    map_sector,
    map_type,
)


# ── Data contract ────────────────────────────────────────────────────────

@dataclass
class TickerData:
    """Normalised response from any ticker data provider."""
    ticker: str
    name: str
    price: float
    currency: str
    # Classification fields (mapped to spec enums)
    type: str                                  # ETF, fund, stock, bond
    asset_class: str                           # equity, fixed_income, cash, …
    sector: str                                # global_diversified, tech, …
    geography: str                             # global, uk, us, …
    # Financial metadata
    ocf_pct: float | None = None               # Ongoing Charges Figure %
    dividend_yield_pct: float | None = None    # Dividend yield %
    isin: str | None = None                    # ISIN identifier


# ── ABC ──────────────────────────────────────────────────────────────────

class TickerProvider(ABC):
    """Abstract ticker data provider.

    Every implementation must implement ``lookup(symbol)`` and return a
    ``TickerData`` with all fields populated (nullable fields may be None).
    """

    @abstractmethod
    async def lookup(self, symbol: str) -> TickerData:
        """Fetch ticker data for *symbol*.

        Args:
            symbol: Ticker symbol (e.g. "VWRL", "AAPL", "VWRL.L").

        Returns:
            A fully populated ``TickerData`` instance.

        Raises:
            TickerNotFoundError: If the symbol cannot be resolved.
        """
        ...


# ── Exceptions ───────────────────────────────────────────────────────────

class TickerNotFoundError(LookupError):
    """Raised when a ticker symbol cannot be resolved by the provider."""


# ── YFinance implementation ──────────────────────────────────────────────

class YFinanceProvider(TickerProvider):
    """Ticker provider backed by the ``yfinance`` library.

    Tries the plain symbol first, then appends ``.L`` (London Stock Exchange)
    if the first attempt returns no price data.
    """

    async def lookup(self, symbol: str) -> TickerData:
        symbol = symbol.upper().strip()
        clean = symbol.replace(".L", "").replace(".IL", "")

        candidates = [clean, f"{clean}.L"]

        for candidate in candidates:
            ticker_obj = yf.Ticker(candidate)
            try:
                info = ticker_obj.info
            except Exception:
                continue

            if not info:
                continue

            name = info.get("longName") or info.get("shortName") or ""
            price = (
                info.get("regularMarketPrice")
                or info.get("currentPrice")
                or info.get("previousClose")
                or 0.0
            )
            currency: str = info.get("currency", "GBP") or "GBP"
            quote_type = info.get("quoteType")
            category = info.get("category")
            sector = info.get("sector")
            region = (
                info.get("morningStarRegion")
                or info.get("market")
            )

            # Map raw yfinance values to spec enums
            mapped_type = map_type(quote_type)
            mapped_asset_class = map_asset_class(category)
            mapped_sector = map_sector(sector)
            mapped_geography = map_geography(region)

            # OCF: yfinance stores as decimal (e.g. 0.0022 = 0.22%)
            ocf_raw = info.get("annualReportExpenseRatio")
            ocf_pct = round(ocf_raw * 100, 4) if isinstance(ocf_raw, (int, float)) else None

            # Dividend yield: yfinance stores as decimal (e.g. 0.015 = 1.5%)
            div_raw = info.get("dividendYield")
            dividend_yield_pct = round(div_raw * 100, 2) if isinstance(div_raw, (int, float)) else None

            isin = info.get("isin")

            # If we have a name, return — even without price (better than nothing)
            if name:
                return TickerData(
                    ticker=clean,
                    name=name,
                    price=price,
                    currency=currency,
                    type=mapped_type,
                    asset_class=mapped_asset_class,
                    sector=mapped_sector,
                    geography=mapped_geography,
                    ocf_pct=ocf_pct,
                    dividend_yield_pct=dividend_yield_pct,
                    isin=isin,
                )

        raise TickerNotFoundError(f"Could not fetch data for ticker '{symbol}'")


# ── Factory ──────────────────────────────────────────────────────────────

_PROVIDER_INSTANCE: TickerProvider | None = None


def get_ticker_provider() -> TickerProvider:
    """Return the configured ticker data provider.

    Currently only ``YFinanceProvider`` is implemented. When a second provider
    is added, read the provider name from ``settings.TICKER_PROVIDER`` and
    return the appropriate implementation.
    """
    global _PROVIDER_INSTANCE
    if _PROVIDER_INSTANCE is None:
        _PROVIDER_INSTANCE = YFinanceProvider()
    return _PROVIDER_INSTANCE
