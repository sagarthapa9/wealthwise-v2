"""
Ticker lookup endpoint — fetches instrument data via an abstract ticker provider.

The provider is injected via ``get_ticker_provider()`` (currently ``YFinanceProvider``).
To switch to a different data source, change the provider — not this endpoint.
"""

from fastapi import APIRouter, HTTPException

from app.schemas.holding import TickerResponse
from app.services.ticker_provider import TickerNotFoundError, get_ticker_provider

router = APIRouter(tags=["ticker"])


@router.get("/ticker/{symbol}", response_model=TickerResponse)
async def lookup_ticker(symbol: str):
    """Look up a ticker symbol and return its name, price, and classification data.

    Delegates to the configured ``TickerProvider`` (currently yfinance).
    The provider tries the plain symbol first, then appends ``.L`` (London
    Stock Exchange) for UK-traded instruments.

    Example: ``GET /api/v1/ticker/VWRL`` returns::

        {
            "ticker": "VWRL",
            "name": "Vanguard FTSE All-World UCITS ETF",
            "price": 137.58,
            "currency": "GBP",
            "type": "ETF",
            "asset_class": "equity",
            "sector": "global_diversified",
            "geography": "global",
            "ocf_pct": 0.22,
            "dividend_yield_pct": 1.5,
            "isin": "IE00BK5BQT80"
        }
    """
    provider = get_ticker_provider()
    try:
        data = await provider.lookup(symbol)
    except TickerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return TickerResponse(
        ticker=data.ticker,
        name=data.name,
        price=data.price,
        currency=data.currency,
        type=data.type,
        asset_class=data.asset_class,
        sector=data.sector,
        geography=data.geography,
        ocf_pct=data.ocf_pct,
        dividend_yield_pct=data.dividend_yield_pct,
        isin=data.isin,
    )
