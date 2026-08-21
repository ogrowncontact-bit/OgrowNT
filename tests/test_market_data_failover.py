"""packages/data/connectors/market/failover.py -- "PROMPT 12" §52-53.

Two independent stub providers stand in for a real second data source --
this codebase has exactly one real provider implementation
(MockMarketDataProvider), so there's no genuine second live source to test
against yet (see the module's own docstring)."""
from __future__ import annotations

from datetime import datetime, timezone

from packages.data.connectors.market.base import Candle
from packages.data.connectors.market.failover import FailoverMarketDataProvider


def _candle(close: float) -> Candle:
    return Candle(ts=datetime.now(timezone.utc), open=close, high=close, low=close, close=close, volume=100.0)


class _StubProvider:
    def __init__(self, name: str, *, candle: Candle | None = None, candles: list[Candle] | None = None, connected: bool = True, raises: bool = False) -> None:
        self.name = name
        self._candle = candle
        self._candles = candles or []
        self._connected = connected
        self._raises = raises
        self.calls = 0

    def is_connected(self) -> bool:
        return self._connected

    def get_latest_candle(self, symbol: str, timeframe: str) -> Candle | None:
        self.calls += 1
        if self._raises:
            raise RuntimeError("simulated provider outage")
        return self._candle

    def get_recent_candles(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        self.calls += 1
        if self._raises:
            raise RuntimeError("simulated provider outage")
        return self._candles


def test_is_connected_true_if_either_provider_is_connected():
    primary = _StubProvider("primary", connected=False)
    secondary = _StubProvider("secondary", connected=True)
    provider = FailoverMarketDataProvider(primary, secondary)
    assert provider.is_connected() is True


def test_is_connected_false_if_neither_provider_is_connected():
    primary = _StubProvider("primary", connected=False)
    secondary = _StubProvider("secondary", connected=False)
    provider = FailoverMarketDataProvider(primary, secondary)
    assert provider.is_connected() is False


def test_get_latest_candle_uses_primary_when_available():
    primary = _StubProvider("primary", candle=_candle(100.0))
    secondary = _StubProvider("secondary", candle=_candle(999.0))
    provider = FailoverMarketDataProvider(primary, secondary)

    candle = provider.get_latest_candle("BTCUSD", "1m")
    assert candle is not None and candle.close == 100.0
    assert provider.active_provider_name == "primary"
    assert secondary.calls == 0  # never consulted -- primary already answered
    assert provider.last_failover_at is None


def test_get_latest_candle_falls_back_to_secondary_when_primary_returns_none():
    primary = _StubProvider("primary", candle=None)
    secondary = _StubProvider("secondary", candle=_candle(50.0))
    provider = FailoverMarketDataProvider(primary, secondary)

    candle = provider.get_latest_candle("BTCUSD", "1m")
    assert candle is not None and candle.close == 50.0
    assert provider.active_provider_name == "secondary"
    assert provider.last_failover_at is not None


def test_get_latest_candle_falls_back_to_secondary_when_primary_raises():
    primary = _StubProvider("primary", raises=True)
    secondary = _StubProvider("secondary", candle=_candle(75.0))
    provider = FailoverMarketDataProvider(primary, secondary)

    candle = provider.get_latest_candle("BTCUSD", "1m")
    assert candle is not None and candle.close == 75.0
    assert provider.active_provider_name == "secondary"


def test_get_latest_candle_returns_none_honestly_when_both_fail():
    primary = _StubProvider("primary", candle=None)
    secondary = _StubProvider("secondary", raises=True)
    provider = FailoverMarketDataProvider(primary, secondary)

    candle = provider.get_latest_candle("BTCUSD", "1m")
    assert candle is None
    assert provider.active_provider_name is None


def test_get_recent_candles_fails_over_the_same_way():
    primary = _StubProvider("primary", candles=[])
    secondary = _StubProvider("secondary", candles=[_candle(10.0), _candle(11.0)])
    provider = FailoverMarketDataProvider(primary, secondary)

    candles = provider.get_recent_candles("BTCUSD", "1m", 10)
    assert len(candles) == 2
    assert provider.active_provider_name == "secondary"


def test_get_recent_candles_empty_when_both_empty():
    primary = _StubProvider("primary", candles=[])
    secondary = _StubProvider("secondary", candles=[])
    provider = FailoverMarketDataProvider(primary, secondary)

    assert provider.get_recent_candles("BTCUSD", "1m", 10) == []
    assert provider.active_provider_name is None


def test_cross_check_no_conflict_when_prices_agree():
    primary = _StubProvider("primary", candle=_candle(100.0))
    secondary = _StubProvider("secondary", candle=_candle(100.1))
    provider = FailoverMarketDataProvider(primary, secondary, conflict_tolerance_pct=0.5)

    result = provider.cross_check_latest("BTCUSD", "1m")
    assert result.conflict is False
    assert result.detail is None


def test_cross_check_flags_conflict_when_prices_diverge():
    primary = _StubProvider("primary", candle=_candle(100.0))
    secondary = _StubProvider("secondary", candle=_candle(110.0))  # 10% apart
    provider = FailoverMarketDataProvider(primary, secondary, conflict_tolerance_pct=0.5)

    result = provider.cross_check_latest("BTCUSD", "1m")
    assert result.conflict is True
    assert result.detail is not None and "DATA_CONFLICT" in result.detail
    assert result.primary_close == 100.0
    assert result.secondary_close == 110.0


def test_cross_check_not_a_conflict_when_one_source_has_no_data():
    primary = _StubProvider("primary", candle=_candle(100.0))
    secondary = _StubProvider("secondary", candle=None)
    provider = FailoverMarketDataProvider(primary, secondary)

    result = provider.cross_check_latest("BTCUSD", "1m")
    assert result.conflict is False
    assert result.secondary_close is None
    assert result.detail is not None and "cannot cross-check" in result.detail


def test_cross_check_queries_both_providers_even_when_primary_has_data():
    """Unlike get_latest_candle's failover reads, cross_check_latest must
    always consult both sources -- that's the entire point."""
    primary = _StubProvider("primary", candle=_candle(100.0))
    secondary = _StubProvider("secondary", candle=_candle(100.0))
    provider = FailoverMarketDataProvider(primary, secondary)

    provider.cross_check_latest("BTCUSD", "1m")
    assert primary.calls == 1
    assert secondary.calls == 1
