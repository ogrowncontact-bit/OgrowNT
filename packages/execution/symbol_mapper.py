"""SymbolMapper — "PROMPT 13" §59.

Identity mapping today: this codebase has exactly one real provider
(MockMarketDataProvider) and one real broker (PaperBrokerAdapter), both of
which already speak Asset.symbol directly — there is no second vocabulary
to translate between yet. A per-broker override table is supported so a
future real adapter (whose venue might spell "BTCUSDT" as "XBTUSD" or
similar) doesn't need a SymbolMapper rewrite, only a registered mapping.
"""
from __future__ import annotations


class SymbolMapper:
    def __init__(self) -> None:
        # (broker_name, canonical_symbol) -> provider_symbol
        self._to_provider: dict[tuple[str, str], str] = {}
        # (broker_name, provider_symbol) -> canonical_symbol
        self._to_canonical: dict[tuple[str, str], str] = {}

    def register(self, *, broker: str, canonical_symbol: str, provider_symbol: str) -> None:
        self._to_provider[(broker, canonical_symbol)] = provider_symbol
        self._to_canonical[(broker, provider_symbol)] = canonical_symbol

    def to_provider_symbol(self, *, broker: str, canonical_symbol: str) -> str:
        return self._to_provider.get((broker, canonical_symbol), canonical_symbol)

    def to_canonical_symbol(self, *, broker: str, provider_symbol: str) -> str:
        return self._to_canonical.get((broker, provider_symbol), provider_symbol)
