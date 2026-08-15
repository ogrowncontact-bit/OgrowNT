from datetime import datetime, timedelta, timezone

from packages.portfolio.state import PortfolioState
from packages.risk.engine import SignalForRisk, evaluate_signal
from packages.shared.models import Asset, Position, Signal, StrategyRow, SystemState

NOW = datetime.now(timezone.utc)


def _portfolio_state(**overrides) -> PortfolioState:
    base = dict(
        ts=NOW, cash=10000, equity=10000, exposure_pct=0.0, daily_pnl=0.0,
        daily_loss_pct=0.0, weekly_loss_pct=0.0, drawdown_pct=0.0, unrealized_pnl=0.0, open_positions=[],
    )
    base.update(overrides)
    return PortfolioState(**base)


def _signal_for_risk(db_session, asset, **overrides) -> SignalForRisk:
    strategy = db_session.query(StrategyRow).filter(StrategyRow.code == "risk_test_strategy").first()
    if strategy is None:
        strategy = StrategyRow(code="risk_test_strategy", name="Risk Test", family="trend", version="1.0")
        db_session.add(strategy)
        db_session.commit()

    signal_row = Signal(
        strategy_id=strategy.id, asset_id=asset.id, ts=NOW, direction="long",
        entry_price=100.0, stop_price=95.0, target_price=115.0, status="scored",
    )
    db_session.add(signal_row)
    db_session.commit()

    base = dict(
        signal_id=signal_row.id, asset_id=asset.id, direction="long", entry_price=100.0, stop_price=95.0,
        target_price=115.0, risk_reward=3.0, confidence=0.9, volatility_factor=1.0,
        data_quality="high", data_ts=NOW, tier="high_quality",
    )
    base.update(overrides)
    return SignalForRisk(**base)


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def test_approves_a_clean_high_quality_signal(db_session):
    asset = _asset(db_session, "RISKAPPROVE")
    sfr = _signal_for_risk(db_session, asset)
    verdict = evaluate_signal(db_session, sfr, _portfolio_state(), SystemState(id=True, trading_enabled=True))
    assert verdict.approved
    assert verdict.approved_quantity is not None and verdict.approved_quantity > 0
    assert all(c.passed for c in verdict.checks)


def test_kill_switch_blocks_everything(db_session):
    asset = _asset(db_session, "RISKKILL")
    sfr = _signal_for_risk(db_session, asset)
    verdict = evaluate_signal(db_session, sfr, _portfolio_state(), SystemState(id=True, trading_enabled=False))
    assert not verdict.approved
    assert verdict.reason == "kill_switch"


def test_poor_risk_reward_is_rejected(db_session):
    asset = _asset(db_session, "RISKRR")
    sfr = _signal_for_risk(db_session, asset, risk_reward=1.0)  # below min 1.5
    verdict = evaluate_signal(db_session, sfr, _portfolio_state(), SystemState(id=True, trading_enabled=True))
    assert not verdict.approved
    assert verdict.reason == "poor_risk_reward"


def test_stale_data_is_rejected(db_session):
    asset = _asset(db_session, "RISKSTALE")
    sfr = _signal_for_risk(db_session, asset, data_ts=NOW - timedelta(seconds=999))
    verdict = evaluate_signal(db_session, sfr, _portfolio_state(), SystemState(id=True, trading_enabled=True))
    assert not verdict.approved
    assert verdict.reason == "data_unavailable"


def test_degraded_data_quality_is_rejected(db_session):
    asset = _asset(db_session, "RISKDEGRADED")
    sfr = _signal_for_risk(db_session, asset, data_quality="degraded")
    verdict = evaluate_signal(db_session, sfr, _portfolio_state(), SystemState(id=True, trading_enabled=True))
    assert not verdict.approved
    assert verdict.reason == "data_unavailable"


def test_watch_tier_never_reaches_risk_review_via_tier_floor(db_session):
    # The Strategy cycle already filters by tier before calling the Risk
    # Engine, but the engine itself must independently refuse a
    # below-floor tier too -- defense in depth, not just caller discipline.
    asset = _asset(db_session, "RISKTIER")
    sfr = _signal_for_risk(db_session, asset, tier="watch")
    verdict = evaluate_signal(db_session, sfr, _portfolio_state(), SystemState(id=True, trading_enabled=True))
    assert not verdict.approved
    assert verdict.reason == "below_safety_belt_tier_floor"


def test_portfolio_exposure_at_limit_is_rejected(db_session):
    asset = _asset(db_session, "RISKEXPOSURE")
    sfr = _signal_for_risk(db_session, asset)
    state = _portfolio_state(exposure_pct=60.0)  # at max_exposure_pct
    verdict = evaluate_signal(db_session, sfr, state, SystemState(id=True, trading_enabled=True))
    assert not verdict.approved
    assert verdict.reason == "exposure"


def test_single_asset_concentration_is_rejected(db_session):
    asset = _asset(db_session, "RISKCONCENTRATION")
    strategy = StrategyRow(code="risk_conc_strategy", name="Conc", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    existing_position = Position(
        asset_id=asset.id, strategy_id=strategy.id, direction="long",
        entry_price=100.0, current_stop=95.0, size=15.0, status="open",  # 1500 = 15% of 10k, at the cap
    )
    db_session.add(existing_position)
    db_session.commit()

    sfr = _signal_for_risk(db_session, asset)
    state = _portfolio_state(open_positions=[existing_position])
    verdict = evaluate_signal(db_session, sfr, state, SystemState(id=True, trading_enabled=True))
    assert not verdict.approved
    assert verdict.reason == "concentration"


def test_daily_loss_limit_blocks_new_trades(db_session):
    asset = _asset(db_session, "RISKDAILYLOSS")
    sfr = _signal_for_risk(db_session, asset)
    state = _portfolio_state(daily_loss_pct=3.5)  # above max_daily_loss_pct(3)
    verdict = evaluate_signal(db_session, sfr, state, SystemState(id=True, trading_enabled=True))
    assert not verdict.approved
    assert verdict.reason == "daily_loss_limit"


def test_defensive_belt_rejects_below_high_quality(db_session):
    asset = _asset(db_session, "RISKBELT")
    sfr = _signal_for_risk(db_session, asset, tier="possible")
    # daily_loss_pct at max -> DEFENSIVE belt, which requires >= high_quality
    state = _portfolio_state(daily_loss_pct=3.0)
    verdict = evaluate_signal(db_session, sfr, state, SystemState(id=True, trading_enabled=True))
    assert not verdict.approved
    assert verdict.safety_belt_level == "defensive"
    assert verdict.reason == "below_safety_belt_tier_floor"


def test_emergency_belt_blocks_all_new_trades(db_session):
    asset = _asset(db_session, "RISKEMERGENCY")
    sfr = _signal_for_risk(db_session, asset, tier="exceptional")
    state = _portfolio_state(drawdown_pct=15.0)  # EMERGENCY
    verdict = evaluate_signal(db_session, sfr, state, SystemState(id=True, trading_enabled=True))
    assert not verdict.approved
    assert verdict.reason == "safety_belt_emergency"


def test_every_check_is_persisted_for_audit(db_session):
    from packages.shared.models import RiskCheck, RiskDecision

    asset = _asset(db_session, "RISKAUDIT")
    sfr = _signal_for_risk(db_session, asset)
    evaluate_signal(db_session, sfr, _portfolio_state(), SystemState(id=True, trading_enabled=True))

    checks = db_session.query(RiskCheck).filter(RiskCheck.signal_id == sfr.signal_id).all()
    decision = db_session.query(RiskDecision).filter(RiskDecision.signal_id == sfr.signal_id).first()
    assert len(checks) > 0
    assert decision is not None
    assert decision.approved is True
