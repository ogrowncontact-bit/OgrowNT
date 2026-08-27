"""packages/system/briefing.py -- "PROMPT 14" §78-81."""
from __future__ import annotations

from datetime import datetime, timezone

from packages.shared.models import Alert, Asset, Incident, OpportunityScore, Position, Signal, StrategyRow, SystemState, Trade
from packages.system.briefing import generate_daily_briefing


def test_briefing_on_an_empty_system_reports_zeros_honestly(db_session):
    briefing = generate_daily_briefing(db_session)
    assert briefing.trades_closed == 0
    assert briefing.win_rate is None  # honestly unset, never fabricated as 0%
    assert briefing.open_positions == 0
    assert briefing.active_incidents == 0


def test_briefing_counts_open_positions(db_session):
    asset = Asset(symbol="BRIEFPOS", asset_class="crypto", is_active=True)
    strategy = StrategyRow(code="brief_strategy", name="x", family="test", version="1.0")
    db_session.add_all([asset, strategy])
    db_session.commit()
    signal = Signal(strategy_id=strategy.id, asset_id=asset.id, ts=datetime.now(timezone.utc), direction="long", entry_price=100.0, stop_price=95.0, status="executed")
    db_session.add(signal)
    db_session.commit()
    db_session.add(Position(asset_id=asset.id, strategy_id=strategy.id, signal_id=signal.id, direction="long", entry_price=100.0, current_stop=95.0, size=1.0, status="open"))
    db_session.commit()

    briefing = generate_daily_briefing(db_session)
    assert briefing.open_positions == 1


def test_briefing_counts_active_incidents_but_not_resolved_ones(db_session):
    db_session.add(Incident(category="system", severity="critical", status="detected", title="x"))
    db_session.add(Incident(category="system", severity="critical", status="resolved", title="y"))
    db_session.commit()

    briefing = generate_daily_briefing(db_session)
    assert briefing.active_incidents == 1


def test_briefing_counts_unacknowledged_alerts(db_session):
    db_session.add(Alert(severity="warning", category="system", message="x", acknowledged=False))
    db_session.add(Alert(severity="warning", category="system", message="y", acknowledged=True))
    db_session.commit()

    briefing = generate_daily_briefing(db_session)
    assert briefing.unacknowledged_alerts == 1


def test_briefing_counts_only_high_quality_and_exceptional_opportunities(db_session):
    asset = Asset(symbol="BRIEFOPP", asset_class="crypto", is_active=True)
    strategy = StrategyRow(code="brief_opp_strategy", name="x", family="test", version="1.0")
    db_session.add_all([asset, strategy])
    db_session.commit()
    for tier in ("ignore", "watch", "possible", "high_quality", "exceptional"):
        signal = Signal(strategy_id=strategy.id, asset_id=asset.id, ts=datetime.now(timezone.utc), direction="long", entry_price=100.0, stop_price=95.0, status="scored")
        db_session.add(signal)
        db_session.commit()
        db_session.add(
            OpportunityScore(
                signal_id=signal.id, technical=50, pattern=0, regime_fit=50, historical_edge=50, liquidity=50, news=50,
                risk_reward=50, strategy_performance=50, volatility_penalty=0, correlation_penalty=0,
                execution_cost_penalty=0, drawdown_penalty=0, final_score=50, tier=tier,
            )
        )
    db_session.commit()

    briefing = generate_daily_briefing(db_session)
    assert briefing.top_opportunity_count == 2


def test_briefing_reflects_current_safety_belt_and_trading_state(db_session):
    db_session.add(SystemState(id=True, trading_enabled=False, safety_belt_level="kill_switch"))
    db_session.commit()
    briefing = generate_daily_briefing(db_session)
    assert briefing.trading_enabled is False
    assert briefing.safety_belt_level == "kill_switch"


def test_briefing_win_rate_is_a_genuine_ratio_of_closed_trades(db_session):
    asset = Asset(symbol="BRIEFWIN", asset_class="crypto", is_active=True)
    strategy = StrategyRow(code="brief_win_strategy", name="x", family="test", version="1.0")
    db_session.add_all([asset, strategy])
    db_session.commit()
    signal = Signal(strategy_id=strategy.id, asset_id=asset.id, ts=datetime.now(timezone.utc), direction="long", entry_price=100.0, stop_price=95.0, status="executed")
    db_session.add(signal)
    db_session.commit()
    position = Position(asset_id=asset.id, strategy_id=strategy.id, signal_id=signal.id, direction="long", entry_price=100.0, current_stop=95.0, size=1.0, status="closed")
    db_session.add(position)
    db_session.commit()
    now = datetime.now(timezone.utc)
    db_session.add(Trade(position_id=position.id, pnl=10.0, outcome="win", is_paper=True, closed_at=now))
    db_session.add(Trade(position_id=position.id, pnl=-5.0, outcome="loss", is_paper=True, closed_at=now))
    db_session.commit()

    briefing = generate_daily_briefing(db_session)
    assert briefing.trades_closed == 2
    assert briefing.win_rate == 0.5
