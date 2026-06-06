"""
Classification mapping utilities — map yfinance / external provider fields
to the WealthWise spec enum values.

Each provider implementation uses these tables to normalise its raw data
into the canonical ``type``, ``asset_class``, ``sector``, and ``geography``
values expected by the rest of the system.
"""

# ── Type mapping ─────────────────────────────────────────────────────────
# yfinance ``quoteType`` → spec ``type`` literal
TYPE_MAP: dict[str, str] = {
    "ETF": "ETF",
    "EQUITY": "stock",
    "MUTUALFUND": "fund",
    "BOND": "bond",
    "TRUST": "investment_trust",
    "UNIT": "fund",
}

# ── Asset class mapping ──────────────────────────────────────────────────
# yfinance ``category`` → spec ``asset_class``
# These are broad category descriptions returned by yfinance for funds.
ASSET_CLASS_MAP: dict[str, str] = {
    # Equity categories
    "equity": "equity",
    "equity_large_cap": "equity",
    "equity_mid_cap": "equity",
    "equity_small_cap": "equity",
    "equity_uk": "equity",
    "equity_us": "equity",
    "equity_global": "equity",
    "equity_emerging_markets": "equity",
    "equity_asia_pacific": "equity",
    "equity_europe": "equity",
    "equity_japan": "equity",
    "equity_income": "equity",
    "equity_growth": "equity",
    "equity_value": "equity",
    "equity_sector": "equity",
    # Fixed income categories
    "fixed_income": "fixed_income",
    "bond": "fixed_income",
    "bond_government": "fixed_income",
    "bond_corporate": "fixed_income",
    "bond_high_yield": "fixed_income",
    "bond_inflation_linked": "fixed_income",
    "bond_global": "fixed_income",
    "bond_uk": "fixed_income",
    "bond_us": "fixed_income",
    "bond_emerging_markets": "fixed_income",
    "money_market": "fixed_income",
    "gilt": "fixed_income",
    # Cash / money market
    "cash": "cash",
    # Property / real estate
    "property": "property",
    "real_estate": "property",
    "realestate": "property",
    # Alternatives
    "alternative": "alternative",
    "commodity": "alternative",
    "commodities": "alternative",
    "precious_metals": "alternative",
    "infrastructure": "alternative",
    "private_equity": "alternative",
    "hedge_fund": "alternative",
    "multi_asset": "multi_asset",
    "balanced": "multi_asset",
    "multi_asset_balanced": "multi_asset",
    "multi_asset_growth": "multi_asset",
    "multi_asset_income": "multi_asset",
    "target_date": "multi_asset",
    "volatility": "alternative",
}

# ── Geography mapping ────────────────────────────────────────────────────
# Maps yfinance fields to spec geography values.
# Lookup order: ``morningStarRegion`` → ``market`` → fallback from ticker suffix.
GEOGRAPHY_MAP: dict[str, str] = {
    "uk": "uk",
    "united_kingdom": "uk",
    "gb": "uk",
    "us": "us",
    "united_states": "us",
    "usa": "us",
    "europe": "europe",
    "euro_zone": "europe",
    "eu": "europe",
    "asia": "asia_pacific",
    "asia_pacific": "asia_pacific",
    "asia_pacific_ex_japan": "asia_pacific",
    "japan": "asia_pacific",
    "china": "asia_pacific",
    "india": "asia_pacific",
    "emerging_markets": "emerging_markets",
    "emerging": "emerging_markets",
    "latin_america": "emerging_markets",
    "global": "global",
    "global_equity": "global",
    "world": "global",
}

# ── Sector mapping (informative — less standardised) ─────────────────────
# yfinance ``sector`` → spec sector string (mostly pass-through)
# This is less critical since sector is often a fund-level category.
SECTOR_MAP: dict[str, str] = {
    "technology": "technology",
    "healthcare": "healthcare",
    "financial_services": "financial_services",
    "financial": "financial_services",
    "consumer_cyclical": "consumer_cyclical",
    "consumer_defensive": "consumer_defensive",
    "industrials": "industrials",
    "energy": "energy",
    "basic_materials": "basic_materials",
    "utilities": "utilities",
    "real_estate": "real_estate",
    "communication_services": "communication_services",
    "diversified": "global_diversified",
}

# ── Fallback defaults ────────────────────────────────────────────────────

DEFAULT_TYPE = "ETF"
DEFAULT_ASSET_CLASS = "equity"
DEFAULT_SECTOR = "global_diversified"
DEFAULT_GEOGRAPHY = "global"


def map_asset_class(category: str | None) -> str:
    """Map a yfinance category string to a canonical asset_class value."""
    if not category:
        return DEFAULT_ASSET_CLASS
    key = category.lower().strip().replace(" ", "_")
    return ASSET_CLASS_MAP.get(key, DEFAULT_ASSET_CLASS)


def map_geography(region: str | None) -> str:
    """Map a yfinance region string to a canonical geography value."""
    if not region:
        return DEFAULT_GEOGRAPHY
    key = region.lower().strip().replace(" ", "_")
    return GEOGRAPHY_MAP.get(key, DEFAULT_GEOGRAPHY)


def map_sector(sector: str | None) -> str:
    """Map a yfinance sector string to a canonical sector value."""
    if not sector:
        return DEFAULT_SECTOR
    key = sector.lower().strip().replace(" ", "_")
    return SECTOR_MAP.get(key, DEFAULT_SECTOR)


def map_type(quote_type: str | None) -> str:
    """Map a yfinance quoteType to a canonical type value."""
    if not quote_type:
        return DEFAULT_TYPE
    key = quote_type.upper().strip()
    return TYPE_MAP.get(key, DEFAULT_TYPE)
