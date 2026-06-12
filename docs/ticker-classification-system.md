# Ticker Provider & Classification System

> How WealthWise fetches and normalises ticker data from external sources.

---

## Architecture Overview

There are **two endpoints** — the UI uses both, in sequence:

```
User types in search box
         │
         ▼
┌──────────────────────────────────┐
│  STEP 1: Autocomplete Search     │
│  GET /api/v1/ticker/search?q=VWR │
│                                  │
│  Source: EODHD search API only   │
│  Returns: lightweight results    │
│  [                               │
│    {code:"VWRL.LSE",             │
│     name:"Vanguard FTSE...",     │
│     type:"ETF", exchange:"LSE"}, │
│  ]                               │
│                                  │
│  Purpose: type-ahead dropdown    │
│  (no classification, no price)   │
└──────────────┬───────────────────┘
               │
     User picks "VWRL" from dropdown
               │
               ▼
┌──────────────────────────────────────┐
│  STEP 2: Full Ticker Lookup          │
│  GET /api/v1/ticker/VWRL             │
│                                      │
│  ticker.py → get_ticker_provider()   │
└──────────────────┬───────────────────┘
                   │
          ┌────────▼────────────┐
          │ TickerProvider.lookup()│  ◄── ABC (any provider)
          │  (abstract method)   │
          └────────┬────────────┘
                   │
   ┌───────────────┼───────────────┐
   │               │               │
┌──▼───┐     ┌────▼─────┐    (future providers)
│YFinance│    │  EODHD   │
│Provider│    │ Provider │
└──┬───┘     └────┬─────┘
   │              │
   └───────┬──────┘
           │
  ┌────────▼────────┐
  │ classification.py │  ◄── normalisation layer
  │  (mapping dicts)  │
  └────────┬────────┘
           │
  ┌────────▼────────┐
  │   TickerData     │  ◄── clean, uniform output
  │  (dataclass)     │
  └────────┬────────┘
           │
           ▼
  Returns full TickerResponse
  (price + 8 classification fields)
  → populates the "Add Holding" form
```

---

## 1. `ticker_provider.py` — The Provider Layer

**Role:** Fetch raw data from external sources and return it in a uniform format.

### The Data Contract

`TickerData` is the single output shape every provider must produce:

```python
@dataclass
class TickerData:
    ticker: str           # "VWRL"
    name: str             # "Vanguard FTSE All-World UCITS ETF"
    price: float          # 137.58
    currency: str         # "GBP"
    type: str             # "ETF"
    asset_class: str      # "equity"
    sector: str           # "global_diversified"
    geography: str        # "global"
    ocf_pct: float | None # 0.22  (= 0.22%)
    dividend_yield_pct    # 1.50  (= 1.5%)
    isin: str | None      # "IE00B3RBWM25"
```

Every endpoint, service, and component downstream only ever sees `TickerData` — they never touch yfinance or EODHD directly.

### The ABC Pattern

```python
class TickerProvider(ABC):
    @abstractmethod
    async def lookup(self, symbol: str) -> TickerData:
        ...
```

This means:

- You **cannot** instantiate `TickerProvider` directly
- Every subclass **must** implement `lookup()`
- The route code just calls `provider.lookup("VWRL")` — doesn't care which provider

### Two Implementations

| Provider | Data source | When used | Classification quality |
|----------|------------|-----------|----------------------|
| `YFinanceProvider` | `yfinance` library (free, no API key) | Default fallback | **Full** — type, asset_class, sector, geography, OCF, dividend yield, ISIN all populated |
| `EODHDProvider` | EODHD REST API (`/search` + `/eod`, free tier) | When `EODHD_API_KEY` is set in `.env` | **Partial** — only type + geography populated; rest gets defaults |

### Provider Selection (Factory)

```python
# In ticker_provider.py, line 279
def get_ticker_provider() -> TickerProvider:
    if settings.eodhd_api_key:
        return EODHDProvider(api_key=settings.eodhd_api_key)
    else:
        return YFinanceProvider()  # default
```

Singleton — created once, reused for all requests.

### How YFinanceProvider Works (detailed)

```
lookup("VWRL.L")
    │
    ├─ Tries "VWRL" → yf.Ticker("VWRL").info
    │    If fails/no name → retries "VWRL.L"
    │
    └─ Extracts from yfinance info dict:
         ├─ name:     info["longName"] or info["shortName"]
         ├─ price:    info["regularMarketPrice"] or info["currentPrice"]
         ├─ currency: info["currency"]
         ├─ quote_type → classification.map_type()
         ├─ category   → classification.map_asset_class()
         ├─ sector     → classification.map_sector()
         ├─ region     → classification.map_geography()
         ├─ ocf:       info["annualReportExpenseRatio"] × 100
         ├─ div_yield: info["dividendYield"] × 100
         └─ isin:      info["isin"]
```

### How EODHDProvider Works

```
lookup("VWRL.L")
    │
    ├─ Tries candidates: "VWRL.L", "VWRL", "VWRL.LSE", "VWRL.US"
    │
    ├─ For each candidate:
    │    ├─ GET /api/search/{candidate}?api_token=...&limit=1
    │    │    Returns: [{Code, Name, Exchange, Type, Country, ...}]
    │    │
    │    └─ GET /api/eod/{candidate}?api_token=...&limit=1
    │         Returns: [{date, close, ...}]
    │
    └─ Assembles TickerData:
         ├─ name:     meta["Name"]
         ├─ price:    latest close from eod endpoint
         ├─ type:     classification.map_type(meta["Type"])
         ├─ geography: _exchange_to_geography(meta["Exchange"])
         └─ rest:     defaults (can't infer from free tier)
```

---

## 2. `classification.py` — The Normalisation Layer

**Role:** Takes messy, provider-specific strings and maps them to canonical WealthWise enum values.

### Why it exists

yfinance returns `"EQUITY"` for quoteType. EODHD returns `"COMMON STOCK"`. Both mean the same thing: a stock. `classification.py` normalises both to `"stock"`.

Without this layer, every downstream service would need its own `if / elif` trees for every provider.

### The Four Mapping Dimensions

Every ticker gets classified into 4 categories:

| Dimension | Example values | Used by |
|-----------|---------------|---------|
| `type` | `ETF`, `stock`, `fund`, `bond`, `investment_trust`, `cash` | `insight_engine.py` (cost efficiency detector), allocation grouping |
| `asset_class` | `equity`, `fixed_income`, `cash`, `property`, `alternative`, `multi_asset` | Allocation tab breakdown, portfolio drift detector |
| `sector` | `technology`, `healthcare`, `financial_services`, `global_diversified`, `energy` | Sector tab breakdown, concentration detector |
| `geography` | `global`, `uk`, `us`, `europe`, `asia_pacific`, `emerging_markets` | Geography tab breakdown, geographic concentration hook |

### How the mapping works (general pattern)

Each mapper function does the same 3-step dance:

```python
def map_type(quote_type: str | None) -> str:
    if not quote_type:
        return "ETF"                         # Step 1: use global default

    key = quote_type.upper().strip()         # Step 2: normalise the raw string
    return TYPE_MAP.get(key, "ETF")          # Step 3: lookup or fallback
```

Concrete trace for `"COMMON STOCK"` from EODHD:

```
Input:  "COMMON STOCK"
  → upper → "COMMON STOCK"
  → strip → "COMMON STOCK"
  → TYPE_MAP lookup → "stock"
  → returns "stock" ✅
```

### Default Fallbacks

When a provider can't determine a value (e.g. EODHD free tier has no sector data), sensible defaults are used:

```python
DEFAULT_TYPE        = "ETF"
DEFAULT_ASSET_CLASS = "equity"
DEFAULT_SECTOR      = "global_diversified"
DEFAULT_GEOGRAPHY   = "global"
```

These are conservative — `"global_diversified"` is the right label for an ETF like VWRL that you haven't classified yet.

### Map sizes

| Map | Entries | Sources covered |
|-----|---------|----------------|
| `TYPE_MAP` | ~25 | yfinance `quoteType` + EODHD `General.Type` |
| `ASSET_CLASS_MAP` | ~50 | yfinance `category` values (equity, bond, property, alternatives, multi-asset) |
| `SECTOR_MAP` | ~60 | yfinance `sector`/`industry` + EODHD sector strings |
| `GEOGRAPHY_MAP` | ~40 | yfinance `morningStarRegion`/`market` + EODHD country ISO codes + exchange codes |

---

## 3. How They Depend on Each Other

```
ticker_provider.py  ──(imports)──►  classification.py
      │                                   │
      │  map_type()                       │ TYPE_MAP
      │  map_asset_class()                │ ASSET_CLASS_MAP
      │  map_sector()                     │ SECTOR_MAP
      │  map_geography()                  │ GEOGRAPHY_MAP
      │  DEFAULT_* constants              │ SECTOR_MAP
      │                                   │
      ▼                                   │
  TickerData                              
 (clean output)                            
```

`ticker_provider.py` **imports from** `classification.py` — the dependency is one-way. `classification.py` has no knowledge of any provider; it's a pure mapping utility.

Specifically (from `ticker_provider.py` lines 24-32):

```python
from app.services.classification import (
    DEFAULT_ASSET_CLASS,
    DEFAULT_GEOGRAPHY,
    DEFAULT_SECTOR,
    map_asset_class,
    map_geography,
    map_sector,
    map_type,
)
```

Each provider calls these during `lookup()`. For YFinance:

```python
mapped_type        = map_type(quote_type)       # "EQUITY" → "stock"
mapped_asset_class = map_asset_class(category)   # "equity_large_cap" → "equity"
mapped_sector      = map_sector(sector)          # "Technology" → "technology"
mapped_geography   = map_geography(region)       # "united_states" → "us"
```

For EODHD:

```python
mapped_type      = map_type(raw_type)                    # "COMMON STOCK" → "stock"
mapped_geography = self._exchange_to_geography(exchange)  # "LSE" → "uk"
# asset_class, sector → use DEFAULT_* constants (no data on free tier)
```

---

## 4. End-to-End Examples

### Case 1: YFinanceProvider looking up "VWRL"

```
1. User types "VWRL" in the search bar
   ↓
2. API calls provider.lookup("VWRL")
   ↓
3. YFinanceProvider:
   a) yf.Ticker("VWRL").info returns:
      {
        "longName": "Vanguard FTSE All-World UCITS ETF",
        "regularMarketPrice": 137.58,
        "currency": "GBP",
        "quoteType": "ETF",
        "category": "global_equity",
        "sector": "Diversified",
        "morningStarRegion": "global",
        "annualReportExpenseRatio": 0.0022,
        "dividendYield": 0.015,
        "isin": "IE00B3RBWM25",
      }
   ↓
4. Classification layer:
   map_type("ETF")          → "ETF"
   map_asset_class("global_equity")
     → key = "global_equity"
     → ASSET_CLASS_MAP["global_equity"] → "equity"
   map_sector("Diversified")
     → key = "diversified"
     → SECTOR_MAP["diversified"] → "global_diversified"
   map_geography("global")
     → key = "global"
     → GEOGRAPHY_MAP["global"] → "global"
   ↓
5. Returns TickerData(
     ticker="VWRL",
     name="Vanguard FTSE All-World UCITS ETF",
     price=137.58,
     currency="GBP",
     type="ETF",
     asset_class="equity",
     sector="global_diversified",
     geography="global",
     ocf_pct=0.22,           # 0.0022 × 100
     dividend_yield_pct=1.5, # 0.015  × 100
     isin="IE00B3RBWM25",
   )
```

### Case 2: EODHDProvider looking up "VWRL"

```
1. User types "VWRL" in search bar
   ↓
2. API calls provider.lookup("VWRL")  (EODHD_API_KEY is set)
   ↓
3. EODHDProvider:
   a) GET /api/search/VWRL?token=...&limit=1
      → [{"Code": "VWRL.LSE", "Name": "Vanguard FTSE All-World UCITS ETF",
          "Exchange": "LSE", "Type": "ETF", "Country": "IE"}]
   
   b) GET /api/eod/VWRL?token=...&limit=1
      → [{"date": "2026-06-04", "close": 137.58}]
   ↓
4. Classification layer:
   map_type("ETF")               → "ETF"
   _exchange_to_geography("LSE") → "uk"
   asset_class → DEFAULT_ASSET_CLASS → "equity"              (no data)
   sector      → DEFAULT_SECTOR      → "global_diversified"  (no data)
   ↓
5. Returns TickerData(
     ticker="VWRL",
     name="Vanguard FTSE All-World UCITS ETF",
     price=137.58,
     currency="GBP",          # hardcoded guess
     type="ETF",
     asset_class="equity",
     sector="global_diversified",
     geography="uk",           # from exchange, but actually a global fund!
     ocf_pct=None,             # not on free tier
     dividend_yield_pct=None,
     isin=None,
   )
```

> **Note:** The EODHD geography is **wrong** ("uk" for a global fund) because it's inferring from exchange (LSE) instead of the fund's actual holdings. YFinance gets this right from `morningStarRegion: "global"`. This is a known limitation of the EODHD free tier.

---

## 5. EODHD Fundamentals API — Filling the Gaps

The current `EODHDProvider` uses only two free-tier endpoints: **Search** (name, type, exchange) and **EOD** (price). EODHD also offers a `/api/v1.1/fundamentals` endpoint that provides rich ETF/fund metadata — solving every gap in the current implementation.

### 5.1 What the Fundamentals API Returns

```
GET https://eodhd.com/api/v1.1/fundamentals/{ticker}.{exchange}?api_token=KEY&fmt=json
```

For an ETF like **VWRL.LSE**, the response contains:

```json
{
  "General": {
    "Code": "VWRL",
    "Type": "ETF",
    "Name": "Vanguard FTSE All-World UCITS ETF",
    "Currency": "GBP",
    "ISIN": "IE00B3RBWM25",
    "CategoryName": "Global Large-Cap Blend Equity",
    "CountryISO": "IE",
    "CountryName": "Ireland",
    "Exchange": "LSE"
  },
  "ETF_Data": {
    "ISIN": "IE00B3RBWM25",
    "Ongoing_Charge": 0.22,
    "NetExpenseRatio": 0.0022,
    "Max_Annual_Mgmt_Charge": 0.22,
    "Yield": 1.5,
    "Dividend_Paying_Frequency": "Quarterly",
    "TotalAssets": 12500000000,
    "Sector_Weights": {
      "Technology":          {"Equity_%": 24.5},
      "Financial Services": {"Equity_%": 16.2},
      "Healthcare":         {"Equity_%": 12.8},
      "Consumer Cyclical":  {"Equity_%": 11.3},
      "Industrials":        {"Equity_%": 10.1},
      "Consumer Defensive": {"Equity_%": 7.4},
      "Communication Svcs": {"Equity_%": 6.9},
      "Energy":             {"Equity_%": 4.2},
      "Basic Materials":    {"Equity_%": 3.5},
      "Utilities":          {"Equity_%": 2.1},
      "Real Estate":        {"Equity_%": 1.0}
    }
  }
}
```

### 5.2 Field-by-Field Gap Analysis

| `TickerData` field | Current (search+EOD only) | Gap | With Fundamentals API | Source in response |
|---|---|---|---|---|
| `currency` | Hardcoded `"GBP"` | ❌ Wrong for USD/EUR funds | ✅ Real | `General.Currency` |
| `asset_class` | `DEFAULT_ASSET_CLASS` → `"equity"` | ❌ Always guesses equity | ✅ Derived | `General.CategoryName` → `ASSET_CLASS_MAP` |
| `sector` | `DEFAULT_SECTOR` → `"global_diversified"` | ❓ Usually right for broad ETFs, wrong for sector ETFs | ✅ Dominant sector from weights | `ETF_Data.Sector_Weights` → pick highest `Equity_%` |
| `geography` | Exchange guess (LSE → `"uk"`) | ❌ Wrong for global funds listed on LSE | ✅ Real | `General.CountryISO` → `GEOGRAPHY_MAP` or derived from `CategoryName` |
| `ocf_pct` | `None` | ❌ No cost data | ✅ Real | `ETF_Data.Ongoing_Charge` or `NetExpenseRatio × 100` |
| `dividend_yield_pct` | `None` | ❌ No yield data | ✅ Real | `ETF_Data.Yield` |
| `isin` | `None` | ❌ No ISIN | ✅ Real | `ETF_Data.ISIN` or `General.ISIN` |

### 5.3 How Each Field Would Be Extracted

#### Currency

```python
# Direct from fundamentals — no mapping needed
currency = fundamentals["General"]["Currency"]  # "GBP"
```

#### Asset Class — from CategoryName

```python
category = fundamentals["General"]["CategoryName"]
# → "Global Large-Cap Blend Equity"

asset_class = map_asset_class(category)
# key = "global_large-cap_blend_equity"
# → ASSET_CLASS_MAP lookup
#    Falls through to DEFAULT → "equity"
#
# Note: Would benefit from adding a few entries to ASSET_CLASS_MAP:
#   "global_large-cap_blend_equity" → "equity"
#   "global_emerging_markets_equity" → "equity"
#   "uk_gilt" → "fixed_income"
#   etc.
```

#### Sector — from Sector Weights (two strategies)

**Strategy A — Dominant sector (broad ETFs):**

```python
weights = fundamentals["ETF_Data"]["Sector_Weights"]
# Find the sector with the highest Equity_%
dominant = max(weights, key=lambda s: weights[s]["Equity_%"])
# → "Technology" at 24.5%

# If no sector exceeds 30%, it's well-diversified
if weights[dominant]["Equity_%"] < 30:
    sector = "global_diversified"
else:
    sector = map_sector(dominant)
```

This handles the VWRL case correctly — 24.5% tech is not a concentration, so `"global_diversified"` is the right label.

**Strategy B — For sector ETFs (single-sector concentration):**

```python
# A tech ETF like XLK.US would have Technology at 95%+
if weights[dominant]["Equity_%"] >= 50:
    sector = map_sector(dominant)  # → "technology"
```

#### Geography — from CountryISO

```python
country = fundamentals["General"]["CountryISO"]  # "IE" (Ireland domiciled)
geography = map_geography(country)
# GEOGRAPHY_MAP["ie"] → "global"
# Ireland-domiciled ETFs are almost always global funds — correct!
```

The existing `GEOGRAPHY_MAP` already handles this (line 125: `"ie": "global"`).

#### OCF — from three possible fields

```python
ocf = (
    fundamentals["ETF_Data"].get("Ongoing_Charge")         # European/UCITS: 0.22
    or fundamentals["ETF_Data"].get("Max_Annual_Mgmt_Charge")  # also 0.22
)
if ocf is None:
    net = fundamentals["ETF_Data"].get("NetExpenseRatio")  # US: 0.0022
    if net is not None:
        ocf = round(net * 100, 2)  # Convert decimal to percentage
# ocf_pct = 0.22
```

#### Dividend Yield

```python
yield_pct = fundamentals["ETF_Data"].get("Yield")  # 1.5
# Yield is already in percentage form in the fundamentals response
```

#### ISIN

```python
isin = fundamentals["ETF_Data"].get("ISIN") or fundamentals["General"].get("ISIN")
# → "IE00B3RBWM25"
```

### 5.4 What the Updated `lookup()` Looks Like

```python
async def lookup(self, symbol: str) -> TickerData:
    # ... search + EOD price fetch (same as today) ...
    
    # NEW: Fetch fundamentals for rich classification data
    fundamentals = await self._fetch_fundamentals(client, candidate)
    
    if fundamentals:
        general = fundamentals.get("General", {})
        etf = fundamentals.get("ETF_Data", {})
        
        currency = general.get("Currency", "GBP")
        asset_class = map_asset_class(general.get("CategoryName"))
        sector = self._derive_sector(etf.get("Sector_Weights", {}))
        geography = map_geography(general.get("CountryISO"))
        ocf_pct = self._extract_ocf(etf)
        dividend_yield_pct = etf.get("Yield")
        isin = etf.get("ISIN") or general.get("ISIN")
    else:
        # Fallback to free-tier defaults (today's behaviour)
        currency = "GBP"
        asset_class = DEFAULT_ASSET_CLASS
        sector = DEFAULT_SECTOR
        geography = self._exchange_to_geography(exchange)
        ocf_pct = None
        dividend_yield_pct = None
        isin = None

    return TickerData(
        ticker=clean,
        name=name,
        price=price,
        currency=currency,        # ✅ from fundamentals
        type=mapped_type,
        asset_class=asset_class,   # ✅ from fundamentals
        sector=sector,             # ✅ from fundamentals
        geography=geography,       # ✅ from fundamentals
        ocf_pct=ocf_pct,           # ✅ from fundamentals
        dividend_yield_pct=dividend_yield_pct,  # ✅ from fundamentals
        isin=isin,                 # ✅ from fundamentals
    )
```

### 5.5 Side-by-Side: Before vs After

**Before (free tier only):**

```
                      EODHDProvider.lookup("VWRL")
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               │
          Search API      EOD API        (no more data)
          name, type      price                │
          exchange                             │
              │               │               │
              ▼               ▼               ▼
         TickerData with 7 out of 13 fields guessed or None
```

**After (with fundamentals):**

```
                      EODHDProvider.lookup("VWRL")
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
          Search API      EOD API      Fundamentals API
          name, type      price        currency, category,
          exchange                     sector weights, OCF,
                                       yield, ISIN, country
              │               │               │
              └───────────────┴───────────────┘
                              │
                              ▼
                    TickerData — ALL 13 fields populated from real data
```

### 5.6 Availability

| Plan | Fundamentals Access | Classification Quality |
|------|-------------------|----------------------|
| Free tier | ❌ Not available | Partial — 7 fields guessed/missing |
| All-Access (paid) | ✅ Available | Full — matches or exceeds yfinance |

The implementation can gracefully degrade: if the fundamentals call fails (free tier returns 402/403), fall back to the current free-tier defaults. No breaking change — just richer data when the API key has access.

---

## 7. Why This Architecture?

| Design choice | Why |
|--------------|-----|
| **ABC pattern** | Swap providers without touching endpoint code — just change config |
| **Pure mapping functions in classification.py** | Testable in isolation, no IO, no async |
| **TickerData is a flat dataclass** | JSON-serializable directly, no ORM dependency |
| **Provider singleton** | yfinance has startup cost; EODHD would otherwise re-auth per request |
| **Classification separate from providers** | Add a new provider (Alpha Vantage, Twelve Data, etc.) — just call the same `map_*()` functions |
| **Defaults are conservative** | `"global_diversified"` is never wrong for an ETF — better than crashing or showing blank |

---

## 8. Adding a New Provider

To add a third provider (e.g. Alpha Vantage):

1. **Subclass `TickerProvider`:**
   ```python
   class AlphaVantageProvider(TickerProvider):
       async def lookup(self, symbol: str) -> TickerData:
           # fetch from Alpha Vantage API
           # call map_type(), map_sector(), etc.
           return TickerData(...)
   ```

2. **Register it in `get_ticker_provider()`:**
   ```python
   def get_ticker_provider() -> TickerProvider:
       if settings.alphavantage_api_key:
           return AlphaVantageProvider(...)
       elif settings.eodhd_api_key:
           return EODHDProvider(...)
       else:
           return YFinanceProvider()
   ```

3. **Done** — no endpoint or model changes needed.

---

## 9. Files

| File | Role |
|------|------|
| `backend/app/services/ticker_provider.py` | ABC + YFinance + EODHD implementations + factory |
| `backend/app/services/classification.py` | Mapping dictionaries + `map_*()` normalisation functions |
| `backend/app/api/v1/ticker.py` | `GET /api/v1/ticker/{symbol}` — calls `get_ticker_provider()` |