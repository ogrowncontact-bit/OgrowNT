"""apps/worker/trade_monitor.py's HOLD/REDUCE/CLOSE wiring — "PROMPT 8"
§28-30. Complements tests/test_trade_monitor.py's default-policy (CLOSE)
regime-shift case and tests/test_execution.py's reduce_position() unit
tests with the hold/reduce paths and the two portfolio-emergency triggers
(Kill Switch, EMERGENCY belt) plus critical news.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from apps.worker.trade_monitor import run_trade_monitor_cycle
from packages.execution.adapters.paper import PaperExecutionProvider
from packages.quant.strategies import TrendFollowingStrategy
from packages.risk.config import load_risk_limits
from packages.shared.models import OHLCV, Asset, MarketRegime, NewsEvent, Position, StrategyRow, SystemState, TradingEvent

REAL_LIMITS = load_risk_limits()


def _limits_with_policy(**overrides):
    policy = replace(REAL_LIMITS.position_risk_policy, **overrides)
    return replace(REAL_LIMITS, position_risk_policy=policy)


def _asset_with_price(db_session, symbol: str, price: float) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    db_session.add(
        OHLCV(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), open=price, high=price * 1.001, low=price * 0.999, close=price, volume=1000)
    )
    db_session.commit()
    return asset


def _strategy(db_session, code: str) -> StrategyRow:
    existing = db_session.query(StrategyRow).filter(StrategyRow.code == code).first()
    if existing is not None:
        return existing
    strategy = StrategyRow(code=code, name=code, family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _mean_reversion_position_in_worst_regime(db_session, symbol: str, *, price: float = 102.0, size: float = 2.0) -> Position:
    """entry=100/stop=95/target=115 with price=102 -- inside both, so only
    the regime-shift trigger (not stop/target) can end this position."""
    asset = _asset_with_price(db_session, symbol, price)
    strategy = _strategy(db_session, "mean_reversion_v1")  # worst_regimes includes trending_bull
    position = Position(
        asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0,
        current_stop=95.0, target_price=115.0, size=size, status="open",
    )
    db_session.add(position)
    db_session.add(
        MarketRegime(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), regime="trending_bull", confidence=0.9, features={})
    )
    db_session.commit()
    assert "trending_bull" in TrendFollowingStrategy().best_regimes  # sanity: this really is mean_reversion's worst regime
    return position


def test_regime_shift_with_hold_policy_leaves_position_open_and_unchanged(db_session, monkeypatch):
    monkeypatch.setattr("apps.worker.trade_monitor.load_risk_limits", lambda: _limits_with_policy(regime_change="hold"))
    position = _mean_reversion_position_in_worst_regime(db_session, "POLICYHOLD")

    provider = PaperExecutionProvider(db_session)
    run_trade_monitor_cycle(db_session, provider)

    db_session.refresh(position)
    assert position.status == "open"
    assert position.size == 2.0
    event = db_session.query(TradingEvent).filter(TradingEvent.event_type == "portfolio_emergency_action").first()
    assert event is not None
    assert event.payload["action"] == "hold"
    assert event.payload["trigger"] == "regime_change"


def test_regime_shift_with_reduce_policy_shrinks_but_keeps_position_open(db_session, monkeypatch):
    monkeypatch.setattr(
        "apps.worker.trade_monitor.load_risk_limits", lambda: _limits_with_policy(regime_change="reduce", reduce_fraction=0.5)
    )
    position = _mean_reversion_position_in_worst_regime(db_session, "POLICYREDUCE", size=2.0)

    provider = PaperExecutionProvider(db_session)
    run_trade_monitor_cycle(db_session, provider)

    db_session.refresh(position)
    assert position.status == "open"
    assert position.size == 1.0


def test_kill_switch_active_closes_open_positions_with_kill_switch_close_reason(db_session):
    db_session.add(SystemState(id=True, trading_enabled=False, safety_belt_level="normal"))
    db_session.commit()
    # A clean long, well inside stop/target -- only the Kill Switch trigger applies.
    asset = _asset_with_price(db_session, "POLICYKILLSWITCH", 105.0)
    strategy = _strategy(db_session, "kill_switch_policy_strategy")
    position = Position(
        asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0,
        current_stop=90.0, target_price=200.0, size=1.0, status="open",
    )
    db_session.add(position)
    db_session.commit()

    provider = PaperExecutionProvider(db_session)
    run_trade_monitor_cycle(db_session, provider)

    db_session.refresh(position)
    assert position.status == "closed"
    assert position.exit_reason == "kill_switch_close"


def test_emergency_belt_closes_open_positions_with_portfolio_emergency_close_reason(db_session):
    db_session.add(SystemState(id=True, trading_enabled=True, safety_belt_level="emergency"))
    db_session.commit()
    asset = _asset_with_price(db_session, "POLICYEMERGENCY", 105.0)
    strategy = _strategy(db_session, "emergency_policy_strategy")
    position = Position(
        asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0,
        current_stop=90.0, target_price=200.0, size=1.0, status="open",
    )
    db_session.add(position)
    db_session.commit()

    provider = PaperExecutionProvider(db_session)
    run_trade_monitor_cycle(db_session, provider)

    db_session.refresh(position)
    assert position.status == "closed"
    assert position.exit_reason == "portfolio_emergency_close"


def test_critical_news_with_default_reduce_policy_shrinks_open_positions(db_session):
    db_session.add(
        NewsEvent(
            source="Reuters", published_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            headline="Central bank shocks markets with emergency rate move", category="central_bank",
            importance="critical", sentiment="bearish",
        )
    )
    db_session.commit()
    asset = _asset_with_price(db_session, "POLICYNEWSCRIT", 105.0)
    strategy = _strategy(db_session, "news_critical_policy_strategy")
    position = Position(
        asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0,
        current_stop=90.0, target_price=200.0, size=2.0, status="open",
    )
    db_session.add(position)
    db_session.commit()

    provider = PaperExecutionProvider(db_session)
    run_trade_monitor_cycle(db_session, provider)  # default config/risk_limits.yaml policy: news_risk=reduce

    db_session.refresh(position)
    assert position.status == "open"
    assert position.size == 1.0  # halved by the default reduce_fraction=0.5


def test_kill_switch_outranks_a_simultaneous_regime_shift(db_session):
    """Severity ordering (apps/worker/trade_monitor.py's
    _position_risk_decision): an active Kill Switch is checked before a
    mere regime shift, so the more urgent trigger wins when both apply."""
    db_session.add(SystemState(id=True, trading_enabled=False, safety_belt_level="normal"))
    db_session.commit()
    position = _mean_reversion_position_in_worst_regime(db_session, "POLICYPRIORITY")

    provider = PaperExecutionProvider(db_session)
    run_trade_monitor_cycle(db_session, provider)

    db_session.refresh(position)
    assert position.status == "closed"
    assert position.exit_reason == "kill_switch_close"  # not regime_change_exit
