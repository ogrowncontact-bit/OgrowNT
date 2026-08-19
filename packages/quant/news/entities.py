"""Entity extraction — Prompt 6 §7.

Deterministic dictionary lookup against a curated list of known entities
(companies, currencies, central banks, commodities, sectors, indices,
economic indicators) — never a full NLP/NER model (none is available in
this environment without external API keys/services), and never an
invented entity: something is only tagged when the headline/body contains
one of its known aliases as a whole-word match. Same "no hallucinated
data" discipline as every other detector in this codebase
(packages/quant/patterns).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

ENTITY_TYPES = (
    "COMPANY", "STOCK", "CRYPTO", "CURRENCY", "COUNTRY", "CENTRAL_BANK",
    "COMMODITY", "INDEX", "SECTOR", "ECONOMIC_INDICATOR",
)


@dataclass(frozen=True)
class Entity:
    type: str
    value: str  # canonical value — an Asset.symbol when the entity IS an asset


# alias (lowercase) -> (type, canonical value). Covers this deployment's
# seeded asset universe (scripts/seed.py) plus common macro/sector drivers —
# extend here as the universe grows, never guess a mapping at match time.
_ENTITY_DICTIONARY: dict[str, tuple[str, str]] = {
    # Companies / stocks
    "apple": ("COMPANY", "AAPL"), "aapl": ("STOCK", "AAPL"),
    "microsoft": ("COMPANY", "MSFT"), "msft": ("STOCK", "MSFT"),
    "nvidia": ("COMPANY", "NVDA"), "nvda": ("STOCK", "NVDA"),
    "amazon": ("COMPANY", "AMZN"), "amzn": ("STOCK", "AMZN"),
    "google": ("COMPANY", "GOOGL"), "alphabet": ("COMPANY", "GOOGL"), "googl": ("STOCK", "GOOGL"),
    "tesla": ("COMPANY", "TSLA"), "tsla": ("STOCK", "TSLA"),
    # Crypto
    "bitcoin": ("CRYPTO", "BTCUSDT"), "btc": ("CRYPTO", "BTCUSDT"),
    "ethereum": ("CRYPTO", "ETHUSDT"), "eth": ("CRYPTO", "ETHUSDT"),
    "solana": ("CRYPTO", "SOLUSDT"), "sol": ("CRYPTO", "SOLUSDT"),
    "binance coin": ("CRYPTO", "BNBUSDT"), "bnb": ("CRYPTO", "BNBUSDT"),
    # Currencies
    "dollar": ("CURRENCY", "USD"), "usd": ("CURRENCY", "USD"),
    "euro": ("CURRENCY", "EUR"), "eur": ("CURRENCY", "EUR"),
    "pound": ("CURRENCY", "GBP"), "sterling": ("CURRENCY", "GBP"), "gbp": ("CURRENCY", "GBP"),
    "yen": ("CURRENCY", "JPY"), "jpy": ("CURRENCY", "JPY"),
    "franc": ("CURRENCY", "CHF"), "chf": ("CURRENCY", "CHF"),
    "aud": ("CURRENCY", "AUD"),
    # Countries
    "united states": ("COUNTRY", "US"), "u.s.": ("COUNTRY", "US"),
    "eurozone": ("COUNTRY", "EU"), "europe": ("COUNTRY", "EU"),
    "united kingdom": ("COUNTRY", "UK"), "britain": ("COUNTRY", "UK"),
    "japan": ("COUNTRY", "JP"), "china": ("COUNTRY", "CN"),
    # Central banks
    "federal reserve": ("CENTRAL_BANK", "FED"), "the fed": ("CENTRAL_BANK", "FED"), "fed": ("CENTRAL_BANK", "FED"),
    "european central bank": ("CENTRAL_BANK", "ECB"), "ecb": ("CENTRAL_BANK", "ECB"),
    "bank of england": ("CENTRAL_BANK", "BOE"), "boe": ("CENTRAL_BANK", "BOE"),
    "bank of japan": ("CENTRAL_BANK", "BOJ"), "boj": ("CENTRAL_BANK", "BOJ"),
    "central bank": ("CENTRAL_BANK", "CENTRAL_BANK"),
    # Commodities
    "gold": ("COMMODITY", "XAU"), "silver": ("COMMODITY", "XAG"),
    "crude oil": ("COMMODITY", "WTI"), "oil": ("COMMODITY", "WTI"), "wti": ("COMMODITY", "WTI"),
    # Indices
    "s&p 500": ("INDEX", "SPX"), "s&p": ("INDEX", "SPX"),
    "nasdaq": ("INDEX", "NDX"),
    "dax": ("INDEX", "DAX"),
    "ibex": ("INDEX", "IBEX"),
    # Sectors
    "semiconductor": ("SECTOR", "SEMICONDUCTOR"), "chip": ("SECTOR", "SEMICONDUCTOR"),
    "chips": ("SECTOR", "SEMICONDUCTOR"), "chipmaker": ("SECTOR", "SEMICONDUCTOR"),
    "supply chain": ("SECTOR", "SUPPLY_CHAIN"),
    "banking sector": ("SECTOR", "BANKING"), "banks": ("SECTOR", "BANKING"),
    "energy sector": ("SECTOR", "ENERGY"),
    "technology sector": ("SECTOR", "TECHNOLOGY"), "tech sector": ("SECTOR", "TECHNOLOGY"),
    # Economic indicators
    "cpi": ("ECONOMIC_INDICATOR", "CPI"), "inflation": ("ECONOMIC_INDICATOR", "CPI"),
    "gdp": ("ECONOMIC_INDICATOR", "GDP"),
    "unemployment": ("ECONOMIC_INDICATOR", "UNEMPLOYMENT"), "payrolls": ("ECONOMIC_INDICATOR", "NFP"),
    "ppi": ("ECONOMIC_INDICATOR", "PPI"), "producer prices": ("ECONOMIC_INDICATOR", "PPI"),
    "interest rate": ("ECONOMIC_INDICATOR", "INTEREST_RATE"), "rate decision": ("ECONOMIC_INDICATOR", "INTEREST_RATE"),
}

_ALIASES_BY_LENGTH = sorted(_ENTITY_DICTIONARY, key=len, reverse=True)


def extract_entities(headline: str, body: str | None = None) -> list[Entity]:
    """Longest-alias-first so "s&p 500" matches before the bare "s&p" alias
    would also match inside it, and so on for any other alias that is a
    substring of a longer one."""
    text = f"{headline} {body or ''}".lower()
    found: dict[tuple[str, str], Entity] = {}
    for alias in _ALIASES_BY_LENGTH:
        pattern = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
        if re.search(pattern, text):
            entity_type, value = _ENTITY_DICTIONARY[alias]
            found[(entity_type, value)] = Entity(type=entity_type, value=value)
    return sorted(found.values(), key=lambda e: (e.type, e.value))
