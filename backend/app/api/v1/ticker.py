"""
Ticker lookup endpoint — fetches instrument name and live price via yfinance.
"""

import yfinance as yf
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["ticker"])


@router.get("/ticker/{symbol}")
async def lookup_ticker(symbol: str):
    """Look up a ticker symbol and return its name and current price.

    Tries the plain symbol first, then appends ``.L`` (London Stock Exchange)
    if the first attempt returns no price. UK ETFs like VWRL, VUSA, VUAG
    trade in GBP on the LSE.

    Example: ``GET /api/v1/ticker/VWRL`` returns::

        {
            "ticker": "VWRL",
            "name": "Vanguard FTSE All-World UCITS ETF",
            "price": 137.58,
            "currency": "GBP"
        }
    """
    symbol = symbol.upper().strip()

    # Remove any suffix the user may have typed
    clean_symbol = symbol.replace(".L", "").replace(".IL", "")

    # Try suffixes: plain symbol first, then .L for LSE
    candidates = [clean_symbol, f"{clean_symbol}.L"]

    best_name = None
    best_price = 0.0
    best_currency = "GBP"

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
            info.get("regularMarketPrice")   # Best for LSE
            or info.get("currentPrice")       # Works for US stocks
            or info.get("previousClose")      # Fallback
            or 0.0
        )
        currency = info.get("currency", "GBP")

        if name and not best_name:
            best_name = name
            best_currency = currency

        if price > 0:
            best_price = price
            best_name = name or best_name
            best_currency = currency
            break  # Found live price — done

    if best_name:
        return {
            "ticker": clean_symbol,
            "name": best_name,
            "price": best_price,
            "currency": best_currency,
        }

    raise HTTPException(
        status_code=404, detail=f"Could not fetch data for ticker '{symbol}'"
    )
