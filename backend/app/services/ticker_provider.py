"""
Abstract ticker data provider interface + YFinance and EODHD implementations.

Usage::

    provider = get_ticker_provider()
    data = await provider.lookup("VWRL")
    # => TickerData(ticker="VWRL", name="...", price=137.58, ...)

To add a new provider (Alpha Vantage, Morningstar, etc.):
1. Subclass ``TickerProvider``
2. Implement ``async lookup(symbol) -> TickerData``
3. Add it to ``get_ticker_provider()``

Switching providers is a config/env change — no endpoint code touches providers directly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx
import yfinance as yf

from app.services.classification import (
    DEFAULT_ASSET_CLASS,
    DEFAULT_GEOGRAPHY,
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


# ── EODHD implementation ───────────────────────────────────────────────

class EODHDProvider(TickerProvider):
    """Ticker provider backed by the EODHD Fundamentals API.

    Tries the symbol with ``.LSE`` suffix first (London Stock Exchange),
    then ``.US`` as a fallback.
    """

    BASE_URL = "https://eodhd.com/api"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def lookup(self, symbol: str) -> TickerData:
        symbol = symbol.upper().strip()
        clean = symbol.replace(".LSE", "").replace(".L", "").replace(".IL", "").replace(".US", "")

        candidates = [clean, f"{clean}.L", f"{clean}.LSE", f"{clean}.US"]

        async with httpx.AsyncClient(timeout=15) as client:
            for candidate in candidates:
                data = await self._fetch_fundamentals(client, candidate)
                if data is None:
                    continue

                general = data.get("General") or {}
                highlights = data.get("Highlights") or {}
                etf_data = data.get("ETFData") or {}

                name = general.get("Name") or ""
                if not name:
                    continue

                raw_type = (general.get("Type") or "").strip()
                sector_raw = (general.get("Sector") or "").strip()
                industry_raw = (general.get("Industry") or "").strip()
                country_iso = (general.get("CountryISO") or "").strip()
                currency = (general.get("CurrencyCode") or "GBP").strip()
                isin = (general.get("ISIN") or "").strip()

                price = highlights.get("PreviousClose") or 0.0
                if isinstance(price, str):
                    try:
                        price = float(price)
                    except (ValueError, TypeError):
                        price = 0.0

                # Map to spec values
                mapped_type = map_type(raw_type)
                mapped_geography = self._map_geography(country_iso)

                # Use sector from EODHD as the primary sector signal
                sector_for_map = sector_raw or industry_raw
                mapped_sector = map_sector(sector_for_map)

                # Infer asset class from type + sector context
                mapped_asset_class = self._infer_asset_class(raw_type, sector_raw, industry_raw)

                # OCF: ETFData first, then Highlights
                ocf_raw = (
                    etf_data.get("TotalExpenseRatio")
                    or etf_data.get("ExpenseRatio")
                    or highlights.get("ExpenseRatio")
                )
                try:
                    ocf_pct = round(float(ocf_raw) * 100, 4) if ocf_raw else None
                except (ValueError, TypeError):
                    ocf_pct = None

                # Dividend yield (EODHD stores as decimal, e.g. 0.0152)
                div_raw = highlights.get("DividendYield")
                try:
                    dividend_yield_pct = round(float(div_raw) * 100, 2) if div_raw else None
                except (ValueError, TypeError):
                    dividend_yield_pct = None

                return TickerData(
                    ticker=clean,
                    name=name,
                    price=price,
                    currency=currency or "GBP",
                    type=mapped_type,
                    asset_class=mapped_asset_class,
                    sector=mapped_sector,
                    geography=mapped_geography,
                    ocf_pct=ocf_pct,
                    dividend_yield_pct=dividend_yield_pct,
                    isin=isin or None,
                )

        raise TickerNotFoundError(f"Could not fetch data for ticker '{symbol}'")

    async def _fetch_fundamentals(self, client: httpx.AsyncClient, candidate: str) -> dict | None:
        """Call the EODHD Fundamentals endpoint and return the JSON body, or None."""
        try:
            resp = await client.get(
                f"{self.BASE_URL}/fundamentals/{candidate}",
                params={"api_token": self.api_key},
            )
            if resp.status_code == 404:
                return None
            # Rate limit / auth errors
            if resp.status_code != 200:
                return None
            data = resp.json()
            # EODHD returns empty dict or error JSON on miss
            if not data or not isinstance(data, dict):
                return None
            # The "General" key is the primary signal — missing means invalid ticker
            if "General" not in data:
                return None
            return data
        except httpx.TimeoutException:
            return None
        except httpx.RequestError:
            return None
        except ValueError:  # JSON decode error
            return None
        except Exception:
            return None

    @staticmethod
    def _map_geography(country_iso: str) -> str:
        """Map EODHD CountryISO code to a spec geography value."""
        if not country_iso:
            return DEFAULT_GEOGRAPHY
        return map_geography(country_iso)

    @staticmethod
    def _infer_asset_class(raw_type: str, sector: str, industry: str) -> str:
        """Infer asset class from EODHD type + sector + industry context."""
        t = raw_type.upper().strip()

        # Direct type-based classification
        if t == "BOND" or t == "GOVERNMENT BOND" or t == "CORPORATE BOND" or t == "CONVERTIBLE BOND" or t == "MONEY MARKET":
            if t == "MONEY MARKET":
                return "cash"
            return "fixed_income"
        if t == "REIT":
            return "property"

        context = (sector + " " + industry).lower()

        if any(kw in context for kw in ("bond", "fixed income", "gilt", "treasury")):
            return "fixed_income"
        if any(kw in context for kw in ("money market", "cash")) and "cash flow" not in context:
            return "cash"
        if any(kw in context for kw in ("real estate", "property", "reit")) and t != "COMMON STOCK":
            return "property"
        if any(kw in context for kw in ("commodity", "commodities", "precious metal")):
            return "alternative"
        if any(kw in context for kw in ("infrastructure", "private equity", "hedge fund")):
            return "alternative"

        # Stocks default to equity
        if t in ("COMMON STOCK", "ORDINARY SHARES"):
            return "equity"

        # For ETFs / funds, check if sector context suggests equity
        if any(kw in context for kw in ("equity", "equities", "global", "diversified")):
            return "equity"

        return DEFAULT_ASSET_CLASS


# ── Factory ──────────────────────────────────────────────────────────────

_PROVIDER_INSTANCE: TickerProvider | None = None


def get_ticker_provider() -> TickerProvider:
    """Return the configured ticker data provider.

    Uses ``EODHDProvider`` when ``settings.eodhd_api_key`` is set,
    otherwise falls back to ``YFinanceProvider``.
    """
    global _PROVIDER_INSTANCE
    if _PROVIDER_INSTANCE is None:
        from app.core.config import settings

        if settings.eodhd_api_key:
            _PROVIDER_INSTANCE = EODHDProvider(api_key=settings.eodhd_api_key)
        else:
            _PROVIDER_INSTANCE = YFinanceProvider()
    return _PROVIDER_INSTANCE
