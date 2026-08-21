"""packages/execution/gate.py -- "PROMPT 13" §5-6, §14-19, §65-66: the final
pre-submit revalidation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.execution.gate import MAX_PRICE_DEVIATION_PCT, evaluate
from packages.shared.models import OHLCV, Asset, Signal, StrategyPerformance, StrategyRow, SystemState

_NOW = datetime.now(timezone.utc)


class _HealthResult:
    def __init__(self, ok: bool):
        self.ok = ok
        self.latency_ms = 1.0
        self.detail: dict = {}


class _StubBroker:
    def __init__(self, *, healthy: bool = True):
        self._healthy = healthy

    def health_check(self):
        return _HealthResult(self._healthy)


def _asset_with_price(db_session, symbol: str, price: float, *, volume: float = 1000.0, asset_class: str = "crypto", exchange: str | None = None) -> Asset:
    asset = Asset(symbol=symbol, asset_class=asset_class, exchange=exchange, is_active=True)
    db_session.add(asset)
    db_session.commit()
    db_session.add(OHLCV(asset_id=asset.id, timeframe="1m", ts=_NOW, open=price, high=price * 1.001, low=price * 0.999, close=price, volume=volume))
    db_session.commit()
    return asset


def _strategy(db_session, code: str) -> StrategyRow:
    strategy = StrategyRow(code=code, name=code, family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _signal(db_session, asset, strategy, *, entry_price: float, stop_price: float, expires_at=None) -> Signal:
    signal = Signal(strategy_id=strategy.id, asset_id=asset.id, direction="long", entry_price=entry_price, stop_price=stop_price, status="approved", expires_at=expires_at)
    db_session.add(signal)
    db_session.commit()
    return signal


def _healthy_system_state() -> SystemState:
    return SystemState(id=True, trading_mode="paper", trading_enabled=True)


def test_full_approval_path(db_session):
    asset = _asset_with_price(db_session, "GATEAPPROVE", 100.0)
    strategy = _strategy(db_session, "gate_approve_strategy")
    signal = _signal(db_session, asset, strategy, entry_price=100.0, stop_price=95.0)

    approval = evaluate(
        db_session, signal_row=signal, asset=asset, direction="long", entry_price=100.0, stop_price=95.0,
        quantity=1.0, system_state=_healthy_system_state(), broker=_StubBroker(), now=_NOW,
    )
    assert approval.approved is True
    assert approval.reason == "approved"
    assert approval.expires_at is not None and approval.expires_at > _NOW
    assert "live_trading_firewall:ok" in approval.checks


def test_live_mode_is_blocked_by_the_firewall(db_session):
    asset = _asset_with_price(db_session, "GATELIVE", 100.0)
    strategy = _strategy(db_session, "gate_live_strategy")
    signal = _signal(db_session, asset, strategy, entry_price=100.0, stop_price=95.0)

    live_state = SystemState(id=True, trading_mode="live", trading_enabled=True)  # never persisted
    approval = evaluate(
        db_session, signal_row=signal, asset=asset, direction="long", entry_price=100.0, stop_price=95.0,
        quantity=1.0, system_state=live_state, now=_NOW,
    )
    assert approval.approved is False
    assert "live_trading_blocked" in approval.reason


def test_expired_signal_is_blocked(db_session):
    asset = _asset_with_price(db_session, "GATEEXPIRED", 100.0)
    strategy = _strategy(db_session, "gate_expired_strategy")
    signal = _signal(db_session, asset, strategy, entry_price=100.0, stop_price=95.0, expires_at=_NOW - timedelta(minutes=5))

    approval = evaluate(
        db_session, signal_row=signal, asset=asset, direction="long", entry_price=100.0, stop_price=95.0,
        quantity=1.0, system_state=_healthy_system_state(), now=_NOW,
    )
    assert approval.approved is False
    assert approval.reason == "signal_expired"


def test_non_positive_quantity_is_blocked(db_session):
    asset = _asset_with_price(db_session, "GATEZEROQTY", 100.0)
    strategy = _strategy(db_session, "gate_zero_qty_strategy")
    signal = _signal(db_session, asset, strategy, entry_price=100.0, stop_price=95.0)

    approval = evaluate(
        db_session, signal_row=signal, asset=asset, direction="long", entry_price=100.0, stop_price=95.0,
        quantity=0.0, system_state=_healthy_system_state(), now=_NOW,
    )
    assert approval.approved is False
    assert approval.reason == "invalid_position_size"


def test_forex_weekend_market_closed_is_blocked(db_session):
    asset = _asset_with_price(db_session, "GATEFXCLOSED", 1.1, asset_class="forex")
    strategy = _strategy(db_session, "gate_fx_closed_strategy")
    signal = _signal(db_session, asset, strategy, entry_price=1.1, stop_price=1.05)
    saturday_noon_utc = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)  # a real Saturday

    approval = evaluate(
        db_session, signal_row=signal, asset=asset, direction="long", entry_price=1.1, stop_price=1.05,
        quantity=1.0, system_state=_healthy_system_state(), now=saturday_noon_utc,
    )
    assert approval.approved is False
    assert approval.reason == "market_closed"


def test_unhealthy_broker_is_blocked(db_session):
    asset = _asset_with_price(db_session, "GATEBADBROKER", 100.0)
    strategy = _strategy(db_session, "gate_bad_broker_strategy")
    signal = _signal(db_session, asset, strategy, entry_price=100.0, stop_price=95.0)

    approval = evaluate(
        db_session, signal_row=signal, asset=asset, direction="long", entry_price=100.0, stop_price=95.0,
        quantity=1.0, system_state=_healthy_system_state(), broker=_StubBroker(healthy=False), now=_NOW,
    )
    assert approval.approved is False
    assert approval.reason == "broker_unavailable"


def test_missing_market_data_is_blocked(db_session):
    asset = Asset(symbol="GATENODATA", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    strategy = _strategy(db_session, "gate_no_data_strategy")
    signal = _signal(db_session, asset, strategy, entry_price=100.0, stop_price=95.0)

    approval = evaluate(
        db_session, signal_row=signal, asset=asset, direction="long", entry_price=100.0, stop_price=95.0,
        quantity=1.0, system_state=_healthy_system_state(), now=_NOW,
    )
    assert approval.approved is False
    assert approval.reason == "data_unavailable"


def test_price_deviation_exceeding_tolerance_is_blocked(db_session):
    asset = _asset_with_price(db_session, "GATEDEVIATION", 100.0)
    strategy = _strategy(db_session, "gate_deviation_strategy")
    # entry_price scored far from the current (unchanged) market price.
    deviated_entry = 100.0 * (1 + (MAX_PRICE_DEVIATION_PCT * 3) / 100)
    signal = _signal(db_session, asset, strategy, entry_price=deviated_entry, stop_price=deviated_entry * 0.95)

    approval = evaluate(
        db_session, signal_row=signal, asset=asset, direction="long", entry_price=deviated_entry, stop_price=deviated_entry * 0.95,
        quantity=1.0, system_state=_healthy_system_state(), now=_NOW,
    )
    assert approval.approved is False
    assert approval.reason.startswith("price_deviation_exceeded")


def test_instrument_precision_violation_is_blocked(db_session):
    asset = _asset_with_price(db_session, "GATEPRECISION", 100.0)
    asset.min_quantity = 5.0
    db_session.add(asset)
    db_session.commit()
    strategy = _strategy(db_session, "gate_precision_strategy")
    signal = _signal(db_session, asset, strategy, entry_price=100.0, stop_price=95.0)

    approval = evaluate(
        db_session, signal_row=signal, asset=asset, direction="long", entry_price=100.0, stop_price=95.0,
        quantity=0.1, system_state=_healthy_system_state(), now=_NOW,
    )
    assert approval.approved is False
    assert approval.reason.startswith("precision_violation")


def test_negative_net_expectancy_is_blocked(db_session):
    asset = _asset_with_price(db_session, "GATEEXPECTANCY", 100.0)
    strategy = _strategy(db_session, "gate_expectancy_strategy")
    signal = _signal(db_session, asset, strategy, entry_price=100.0, stop_price=95.0)
    db_session.add(StrategyPerformance(strategy_id=strategy.id, as_of=_NOW, window_trades=30, total_trades=30, expectancy=-5.0))
    db_session.commit()

    approval = evaluate(
        db_session, signal_row=signal, asset=asset, direction="long", entry_price=100.0, stop_price=95.0,
        quantity=1.0, system_state=_healthy_system_state(), now=_NOW,
    )
    assert approval.approved is False
    assert approval.reason.startswith("negative_net_expectancy")


def test_net_expectancy_not_evaluated_when_no_strategy_performance_yet(db_session):
    """§65's evaluate_net_expectancy() honestly reports evaluated=False
    (passes=True) instead of fabricating a pass/fail from an unproven
    number -- the gate must not block on absence of evidence."""
    asset = _asset_with_price(db_session, "GATENOPERF", 100.0)
    strategy = _strategy(db_session, "gate_no_perf_strategy")
    signal = _signal(db_session, asset, strategy, entry_price=100.0, stop_price=95.0)

    approval = evaluate(
        db_session, signal_row=signal, asset=asset, direction="long", entry_price=100.0, stop_price=95.0,
        quantity=1.0, system_state=_healthy_system_state(), now=_NOW,
    )
    assert approval.approved is True
    assert "net_expectancy:not_evaluated" in approval.checks
