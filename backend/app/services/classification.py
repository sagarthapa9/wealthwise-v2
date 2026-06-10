"""
Classification mapping utilities — map yfinance / external provider fields
to the WealthWise spec enum values.

Each provider implementation uses these tables to normalise its raw data
into the canonical ``type``, ``asset_class``, ``sector``, and ``geography``
values expected by the rest of the system.
"""

# ── Type mapping ─────────────────────────────────────────────────────────
# Maps provider ``quoteType`` / ``General.Type`` → spec ``type`` literal
TYPE_MAP: dict[str, str] = {
    # yfinance
    "ETF": "ETF",
    "EQUITY": "stock",
    "MUTUALFUND": "fund",
    "BOND": "bond",
    "TRUST": "investment_trust",
    "UNIT": "fund",
    # EODHD
    "ETC": "ETF",
    "ETN": "ETF",
    "COMMON STOCK": "stock",
    "ORDINARY SHARES": "stock",
    "REIT": "stock",
    "CLOSED END FUND": "fund",
    "CLOSED-END FUND": "fund",
    "MUTUAL FUND": "fund",
    "OPEN END FUND": "fund",
    "OPEN-END FUND": "fund",
    "UNIT TRUST": "fund",
    "FUND": "fund",
    "INVESTMENT TRUST": "investment_trust",
    "MONEY MARKET": "cash",
    "GOVERNMENT BOND": "bond",
    "CORPORATE BOND": "bond",
    "CONVERTIBLE BOND": "bond",
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
    # EODHD CountryISO codes
    "gb": "uk",
    "uk": "uk",
    "us": "us",
    "ie": "global",          # Ireland-domiciled (mostly global funds)
    "je": "global",          # Jersey
    "gg": "global",          # Guernsey
    "lu": "europe",          # Luxembourg
    "fr": "europe",
    "de": "europe",
    "nl": "europe",
    "ch": "europe",
    "se": "europe",
    "dk": "europe",
    "no": "europe",
    "fi": "europe",
    "it": "europe",
    "es": "europe",
    "jp": "asia_pacific",
    "hk": "asia_pacific",
    "au": "asia_pacific",
    "sg": "asia_pacific",
    "cn": "asia_pacific",
    "in": "asia_pacific",
    "kr": "asia_pacific",
    "tw": "asia_pacific",
    "br": "emerging_markets",
    "za": "emerging_markets",
    "ru": "emerging_markets",
    "mx": "emerging_markets",
    "id": "emerging_markets",
    "my": "emerging_markets",
    "th": "emerging_markets",
    "tr": "emerging_markets",
}

# ── Sector mapping ─────────────────────────────────────────────────────
# Maps sector/industry strings from any provider to spec values.
# Keys use lower_snake_case (provider fields are normalised before lookup).
SECTOR_MAP: dict[str, str] = {
    # Technology
    "technology": "technology",
    "software": "technology",
    "software_and_services": "technology",
    "semiconductors": "technology",
    "semiconductor": "technology",
    "hardware": "technology",
    "consumer_electronics": "technology",
    "electronics": "technology",
    "information_technology": "technology",
    # Healthcare
    "healthcare": "healthcare",
    "biotechnology": "healthcare",
    "pharmaceuticals": "healthcare",
    "medical_devices": "healthcare",
    "medical_equipment": "healthcare",
    "healthcare_providers": "healthcare",
    "health_services": "healthcare",
    # Financial
    "financial_services": "financial_services",
    "financial": "financial_services",
    "asset_management": "financial_services",
    "banks": "financial_services",
    "banking": "financial_services",
    "insurance": "financial_services",
    "investment_banking": "financial_services",
    "capital_markets": "financial_services",
    "diversified_financial": "financial_services",
    # Consumer
    "consumer_cyclical": "consumer_cyclical",
    "consumer_services": "consumer_cyclical",
    "retail": "consumer_cyclical",
    "automotive": "consumer_cyclical",
    "travel": "consumer_cyclical",
    "luxury_goods": "consumer_cyclical",
    "consumer_defensive": "consumer_defensive",
    "food_and_beverage": "consumer_defensive",
    "food": "consumer_defensive",
    "beverages": "consumer_defensive",
    "consumer_staples": "consumer_defensive",
    "household_products": "consumer_defensive",
    "tobacco": "consumer_defensive",
    # Industrials
    "industrials": "industrials",
    "industrial": "industrials",
    "manufacturing": "industrials",
    "transportation": "industrials",
    "aerospace_and_defense": "industrials",
    "aerospace": "industrials",
    "defense": "industrials",
    "engineering": "industrials",
    "machinery": "industrials",
    "construction": "industrials",
    # Energy
    "energy": "energy",
    "oil_and_gas": "energy",
    "oil": "energy",
    "renewable_energy": "energy",
    "utilities": "utilities",
    "electric_utilities": "utilities",
    # Materials
    "basic_materials": "basic_materials",
    "materials": "basic_materials",
    "mining": "basic_materials",
    "metals": "basic_materials",
    "chemicals": "basic_materials",
    # Real estate
    "real_estate": "real_estate",
    "real_estate_investment": "real_estate",
    "property": "real_estate",
    # Communication
    "communication_services": "communication_services",
    "telecommunications": "communication_services",
    "telecom": "communication_services",
    "media": "communication_services",
    "entertainment": "communication_services",
    # Diversified / catch-all
    "diversified": "global_diversified",
    "exchange_traded_fund": "global_diversified",
    "etf": "global_diversified",
    "global_equities": "global_diversified",
    "global_equity": "global_diversified",
    # Commodities
    "commodity": "commodities",
    "commodities": "commodities",
    "precious_metals": "commodities",
    "precious_metals_gold": "commodities",
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
