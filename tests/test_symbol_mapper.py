"""packages/execution/symbol_mapper.py -- "PROMPT 13" §59."""
from __future__ import annotations

from packages.execution.symbol_mapper import SymbolMapper


def test_unregistered_symbol_maps_to_itself_in_both_directions():
    mapper = SymbolMapper()
    assert mapper.to_provider_symbol(broker="paper", canonical_symbol="BTCUSDT") == "BTCUSDT"
    assert mapper.to_canonical_symbol(broker="paper", provider_symbol="BTCUSDT") == "BTCUSDT"


def test_registered_mapping_translates_both_ways():
    mapper = SymbolMapper()
    mapper.register(broker="future_real_broker", canonical_symbol="BTCUSDT", provider_symbol="XBTUSD")
    assert mapper.to_provider_symbol(broker="future_real_broker", canonical_symbol="BTCUSDT") == "XBTUSD"
    assert mapper.to_canonical_symbol(broker="future_real_broker", provider_symbol="XBTUSD") == "BTCUSDT"


def test_mappings_are_scoped_per_broker():
    mapper = SymbolMapper()
    mapper.register(broker="broker_a", canonical_symbol="BTCUSDT", provider_symbol="XBTUSD")
    # broker_b never registered this mapping -- must NOT inherit broker_a's translation.
    assert mapper.to_provider_symbol(broker="broker_b", canonical_symbol="BTCUSDT") == "BTCUSDT"
