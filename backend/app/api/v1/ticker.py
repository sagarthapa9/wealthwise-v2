"""
Ticker lookup endpoint — fetches instrument data via an abstract ticker provider.

The provider is injected via ``get_ticker_provider()`` (currently ``EODHDProvider``
when the API key is set, otherwise ``YFinanceProvider``).
"""

from typing import List

from fastapi import APIRouter, HTTPException, Query
import httpx

from app.schemas.holding import TickerResponse, TickerSearchResult
from app.services.ticker_provider import TickerNotFoundError, get_ticker_provider
from app.core.config import settings

router = APIRouter(tags=["ticker"])


@router.get("/ticker/search", response_model=List[TickerSearchResult])
async def search_tickers(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, le=20, description="Max results"),
):
    """Search for tickers using the EODHD search API.

    Returns lightweight results (code, name, type, exchange) for autocomplete.
    Requires ``EODHD_API_KEY`` to be configured — returns 501 if not set.
    """
    if not settings.eodhd_api_key:
        raise HTTPException(status_code=501, detail="EODHD_API_KEY not configured")

    params = {
        "api_token": settings.eodhd_api_key,
        "fmt": "json",
        "limit": limit,
        "query": q,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(
                f"https://eodhd.com/api/search/{q}",
                params=params,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            if not isinstance(data, list):
                return []
            results = []
            for item in data:
                results.append(TickerSearchResult(
                    code=item.get("Code", ""),
                    name=item.get("Name", ""),
                    type=item.get("Type"),
                    exchange=item.get("Exchange"),
                    match_score=item.get("MatchScore"),
                ))
            return results[:limit]
        except httpx.RequestError:
            return []


@router.get("/ticker/{symbol}", response_model=TickerResponse)
async def lookup_ticker(symbol: str):
    """Look up a ticker symbol and return its name, price, and classification data.

    Delegates to the configured ``TickerProvider`` (EODHD or yfinance).
    """
    provider = get_ticker_provider()
    try:
        data = await provider.lookup(symbol)
    except TickerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("Ticker lookup failed for %s", symbol)
        raise HTTPException(status_code=502, detail=str(exc))

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
