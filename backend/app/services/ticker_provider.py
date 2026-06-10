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
    """Ticker provider backed by EODHD search + EOD price APIs.

    Free-tier compatible: uses ``/api/search`` for metadata (name, type)
    and ``/api/eod`` for the latest closing price.
    """

    BASE = "https://eodhd.com/api"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def lookup(self, symbol: str) -> TickerData:
        symbol = symbol.upper().strip()
        clean = symbol.replace(".LSE", "").replace(".L", "").replace(".IL", "").replace(".US", "")
        candidates = [symbol, clean, f"{clean}.L", f"{clean}.LSE", f"{clean}.US"]
        # Deduplicate while preserving order
        seen: set[str] = set()
        candidates = [c for c in candidates if not (c in seen or seen.add(c))]

        async with httpx.AsyncClient(timeout=15) as client:
            for candidate in candidates:
                meta = await self._fetch_meta(client, candidate)
                if meta is None:
                    continue
                name = meta.get("Name") or ""
                raw_type = (meta.get("Type") or "").strip()
                exchange = (meta.get("Exchange") or "").strip()
                if not name:
                    continue

                # Fetch price from EOD endpoint
                price = await self._fetch_price(client, candidate)

                # Map to spec values
                mapped_type = map_type(raw_type)

                # Infer geography from exchange
                mapped_geography = self._exchange_to_geography(exchange)

                return TickerData(
                    ticker=clean,
                    name=name,
                    price=price,
                    currency="GBP",                  # best guess without fundamentals
                    type=mapped_type,
                    asset_class=DEFAULT_ASSET_CLASS,  # can't infer without sector/industry
                    sector=DEFAULT_SECTOR,
                    geography=mapped_geography,
                    ocf_pct=None,                    # not available on free tier
                    dividend_yield_pct=None,
                    isin=None,
                )
        raise TickerNotFoundError(f"Could not fetch data for ticker '{symbol}'")

    async def _fetch_meta(self, client: httpx.AsyncClient, candidate: str) -> dict | None:
        """Search EODHD for a symbol and return the first match's metadata."""
        try:
            resp = await client.get(
                f"{self.BASE}/search/{candidate}",
                params={"api_token": self.api_key, "fmt": "json", "limit": 1},
            )
            if resp.status_code != 200:
                print(f"[EODHD] search {candidate} → {resp.status_code}")
                return None
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            return None
        except Exception:
            return None

    async def _fetch_price(self, client: httpx.AsyncClient, symbol: str) -> float:
        """Fetch the latest closing price from the EOD endpoint."""
        try:
            resp = await client.get(
                f"{self.BASE}/eod/{symbol}",
                params={"api_token": self.api_key, "fmt": "json", "limit": 1},
            )
            if resp.status_code != 200:
                print(f"[EODHD] eod {symbol} → {resp.status_code}")
                return 0.0
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                close = data[0].get("close", 0.0) or 0.0
                return float(close)
            return 0.0
        except Exception:
            return 0.0

    @staticmethod
    def _exchange_to_geography(exchange: str) -> str:
        """Map an exchange code to a geography value."""
        m = {
            "LSE": "uk",
            "L": "uk",
            "US": "us",
            "NASDAQ": "us",
            "NYSE": "us",
            "HKEX": "asia_pacific",
            "ASX": "asia_pacific",
            "TSE": "asia_pacific",
            "EURONEXT": "europe",
            "XETRA": "europe",
            "SWX": "europe",
        }
        return m.get(exchange.upper().strip(), DEFAULT_GEOGRAPHY)


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
            _PROVIDER_INSTANCE = EODHDProvider(api_key=settings.eodhd_api_key.strip())
        else:
            _PROVIDER_INSTANCE = YFinanceProvider()
    return _PROVIDER_INSTANCE
