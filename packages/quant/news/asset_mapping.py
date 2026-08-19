"""Asset mapping — Prompt 6 §8: news -> potentially-affected assets, with an
explicit DIRECT vs INDIRECT distinction (§8: "o sistema deve diferenciar").

DIRECT: the entity IS the asset (a STOCK/CRYPTO/COMMODITY/INDEX alias, or a
currency that is one leg of a forex pair in this universe).
INDIRECT: the entity is a related driver (a central bank, a macro indicator,
a sector) — never silently collapsed into a direct hit, since the Risk/
Opportunity Engines should treat "Apple reports earnings" very differently
from "the Fed meets" even though both may touch NASDAQ.
"""
from __future__ import annotations

from dataclasses import dataclass

from packages.quant.news.entities import Entity

# Indirect drivers: entity value -> [(asset_symbol, reason), ...], scoped to
# this deployment's seeded asset universe (scripts/seed.py) — extend as the
# universe grows, never guess a mapping that isn't backed by a real listed
# relationship.
_INDIRECT_DRIVERS: dict[str, list[tuple[str, str]]] = {
    "FED": [
        ("SPX", "US equity index"), ("NDX", "US equity index"),
        ("XAU", "rate-sensitive"), ("BTCUSDT", "risk asset"),
    ],
    "ECB": [("DAX", "EU equity index"), ("EURUSD", "policy currency")],
    "BOE": [("GBPUSD", "policy currency")],
    "BOJ": [("USDJPY", "policy currency")],
    "USD": [
        ("XAU", "USD-denominated"), ("XAG", "USD-denominated"), ("WTI", "USD-denominated"),
        ("EURUSD", "USD leg"), ("GBPUSD", "USD leg"), ("USDJPY", "USD leg"),
        ("USDCHF", "USD leg"), ("AUDUSD", "USD leg"),
    ],
    "CPI": [("XAU", "inflation hedge"), ("SPX", "rate expectations"), ("NDX", "rate expectations")],
    "INTEREST_RATE": [("SPX", "rate expectations"), ("NDX", "rate expectations"), ("XAU", "rate-sensitive")],
    "GDP": [("SPX", "growth proxy"), ("NDX", "growth proxy")],
    "NFP": [("SPX", "labor-market proxy"), ("USD", "labor-market proxy")],
    "SEMICONDUCTOR": [("NVDA", "sector peer"), ("NDX", "sector-heavy index")],
    "SUPPLY_CHAIN": [("AAPL", "hardware supply chain"), ("NVDA", "hardware supply chain")],
    "TECHNOLOGY": [("NDX", "sector-heavy index")],
}

_CURRENCY_TO_FOREX_PAIRS: dict[str, list[str]] = {
    "EUR": ["EURUSD"], "GBP": ["GBPUSD"], "JPY": ["USDJPY"], "CHF": ["USDCHF"], "AUD": ["AUDUSD"],
}


@dataclass(frozen=True)
class AssetMapping:
    asset_symbol: str
    is_direct: bool
    reason: str


def map_entities_to_assets(entities: list[Entity], asset_universe: set[str]) -> list[AssetMapping]:
    mappings: dict[str, AssetMapping] = {}

    def _add(symbol: str, direct: bool, reason: str) -> None:
        if symbol not in asset_universe:
            return
        existing = mappings.get(symbol)
        if existing is None or (direct and not existing.is_direct):
            mappings[symbol] = AssetMapping(asset_symbol=symbol, is_direct=direct, reason=reason)

    for entity in entities:
        if entity.type in ("COMPANY", "STOCK", "CRYPTO", "COMMODITY", "INDEX") and entity.value in asset_universe:
            _add(entity.value, True, f"{entity.type.lower()} named directly")
        elif entity.type == "CURRENCY":
            for symbol in _CURRENCY_TO_FOREX_PAIRS.get(entity.value, []):
                _add(symbol, True, f"{entity.value} is one leg of this pair")
        for symbol, reason in _INDIRECT_DRIVERS.get(entity.value, []):
            _add(symbol, False, reason)

    return sorted(mappings.values(), key=lambda m: m.asset_symbol)
