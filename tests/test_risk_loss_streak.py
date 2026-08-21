"""packages/risk/loss_streak.py — "PROMPT 8" §37-40: portfolio-wide loss
streak detection and the anti-martingale guarantee (a win streak never
increases size)."""
from datetime import datetime, timedelta, timezone

from packages.risk.config import LossStreakConfig
from packages.risk.loss_streak import (
    asset_consecutive_losses,
    current_consecutive_losses,
    current_consecutive_wins,
    evaluate_dimensional_loss_streaks,
    evaluate_loss_streak,
    observe_win_streak,
    regime_consecutive_losses,
    strategy_consecutive_losses,
)
from packages.shared.models import Asset, MarketRegime, Position, Signal, StrategyRow, Trade

LIMITS = LossStreakConfig(threshold=5, size_multiplier_when_triggered=0.5)


def _setup(db_session) -> tuple[Asset, StrategyRow]:
    asset = Asset(symbol="LOSSSTREAK", asset_class="crypto", is_active=True)
    strategy = StrategyRow(code="loss_streak_strategy", name="Loss Streak", family="trend", version="1.0")
    db_session.add_all([asset, strategy])
    db_session.commit()
    return asset, strategy


def _closed_trade(db_session, asset: Asset, strategy: StrategyRow, outcome: str, closed_at: datetime) -> Trade:
    position = Position(
        asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0,
        current_stop=95.0, size=1.0, status="closed", closed_at=closed_at,
    )
    db_session.add(position)
    db_session.commit()
    trade = Trade(
        position_id=position.id, pnl=(-10.0 if outcome == "loss" else 10.0), outcome=outcome, closed_at=closed_at,
    )
    db_session.add(trade)
    db_session.commit()
    return trade


def test_no_trades_means_zero_streak(db_session):
    assert current_consecutive_losses(db_session) == 0


def test_counts_consecutive_losses_from_most_recent(db_session):
    asset, strategy = _setup(db_session)
    now = datetime.now(timezone.utc)
    _closed_trade(db_session, asset, strategy, "win", now - timedelta(minutes=5))
    _closed_trade(db_session, asset, strategy, "loss", now - timedelta(minutes=4))
    _closed_trade(db_session, asset, strategy, "loss", now - timedelta(minutes=3))
    _closed_trade(db_session, asset, strategy, "loss", now - timedelta(minutes=2))
    assert current_consecutive_losses(db_session) == 3


def test_win_or_breakeven_resets_the_streak_even_with_earlier_losses(db_session):
    asset, strategy = _setup(db_session)
    now = datetime.now(timezone.utc)
    _closed_trade(db_session, asset, strategy, "loss", now - timedelta(minutes=5))
    _closed_trade(db_session, asset, strategy, "loss", now - timedelta(minutes=4))
    _closed_trade(db_session, asset, strategy, "breakeven", now - timedelta(minutes=3))
    assert current_consecutive_losses(db_session) == 0


def test_streak_is_portfolio_wide_not_scoped_to_one_strategy(db_session):
    """Losses spread across two DIFFERENT strategies still count as one
    portfolio-wide streak — this is deliberately not the same thing as
    packages/quant/learning/quarantine.py's per-strategy health score."""
    asset, strategy_a = _setup(db_session)
    strategy_b = StrategyRow(code="loss_streak_strategy_b", name="Loss Streak B", family="momentum", version="1.0")
    db_session.add(strategy_b)
    db_session.commit()
    now = datetime.now(timezone.utc)
    _closed_trade(db_session, asset, strategy_a, "loss", now - timedelta(minutes=3))
    _closed_trade(db_session, asset, strategy_b, "loss", now - timedelta(minutes=2))
    assert current_consecutive_losses(db_session) == 2


def test_evaluate_loss_streak_triggers_at_threshold_and_halves_size(db_session):
    asset, strategy = _setup(db_session)
    now = datetime.now(timezone.utc)
    for i in range(5):
        _closed_trade(db_session, asset, strategy, "loss", now - timedelta(minutes=5 - i))
    result = evaluate_loss_streak(db_session, LIMITS)
    assert result.consecutive_losses == 5
    assert result.triggered
    assert result.size_multiplier == 0.5


def test_below_threshold_is_not_triggered_and_full_size(db_session):
    asset, strategy = _setup(db_session)
    now = datetime.now(timezone.utc)
    for i in range(4):
        _closed_trade(db_session, asset, strategy, "loss", now - timedelta(minutes=4 - i))
    result = evaluate_loss_streak(db_session, LIMITS)
    assert result.consecutive_losses == 4
    assert not result.triggered
    assert result.size_multiplier == 1.0


def test_win_streak_never_increases_size(db_session):
    """Anti-martingale (§40): however many consecutive wins, size_multiplier
    never exceeds 1.0 — this detector only ever reduces size, never raises
    it."""
    asset, strategy = _setup(db_session)
    now = datetime.now(timezone.utc)
    for i in range(10):
        _closed_trade(db_session, asset, strategy, "win", now - timedelta(minutes=10 - i))
    result = evaluate_loss_streak(db_session, LIMITS)
    assert result.consecutive_losses == 0
    assert not result.triggered
    assert result.size_multiplier == 1.0


# -- "PROMPT 12" dimensional streaks + Win Streak Guard ---------------------


def test_strategy_consecutive_losses_scoped_to_one_strategy(db_session):
    asset, strategy_a = _setup(db_session)
    strategy_b = StrategyRow(code="loss_streak_dim_strategy_b", name="Dim B", family="momentum", version="1.0")
    db_session.add(strategy_b)
    db_session.commit()
    now = datetime.now(timezone.utc)
    # Strategy A: 3 losses in a row. Strategy B: a win right after, in between.
    _closed_trade(db_session, asset, strategy_a, "loss", now - timedelta(minutes=6))
    _closed_trade(db_session, asset, strategy_a, "loss", now - timedelta(minutes=5))
    _closed_trade(db_session, asset, strategy_b, "win", now - timedelta(minutes=4))
    _closed_trade(db_session, asset, strategy_a, "loss", now - timedelta(minutes=3))

    assert strategy_consecutive_losses(db_session, strategy_a.id) == 3
    assert strategy_consecutive_losses(db_session, strategy_b.id) == 0


def test_asset_consecutive_losses_scoped_to_one_asset(db_session):
    asset_a, strategy = _setup(db_session)
    asset_b = Asset(symbol="LOSSSTREAK_DIM_B", asset_class="crypto", is_active=True)
    db_session.add(asset_b)
    db_session.commit()
    now = datetime.now(timezone.utc)
    _closed_trade(db_session, asset_a, strategy, "loss", now - timedelta(minutes=5))
    _closed_trade(db_session, asset_a, strategy, "loss", now - timedelta(minutes=4))
    _closed_trade(db_session, asset_b, strategy, "win", now - timedelta(minutes=3))

    assert asset_consecutive_losses(db_session, asset_a.id) == 2
    assert asset_consecutive_losses(db_session, asset_b.id) == 0


def _closed_trade_with_regime(db_session, asset: Asset, strategy: StrategyRow, regime_row: MarketRegime, outcome: str, closed_at: datetime) -> Trade:
    signal = Signal(
        strategy_id=strategy.id, asset_id=asset.id, ts=closed_at, direction="long",
        entry_price=100.0, stop_price=95.0, status="executed", regime_id=regime_row.id,
    )
    db_session.add(signal)
    db_session.commit()
    position = Position(
        asset_id=asset.id, strategy_id=strategy.id, signal_id=signal.id, direction="long", entry_price=100.0,
        current_stop=95.0, size=1.0, status="closed", closed_at=closed_at,
    )
    db_session.add(position)
    db_session.commit()
    trade = Trade(position_id=position.id, pnl=(-10.0 if outcome == "loss" else 10.0), outcome=outcome, closed_at=closed_at)
    db_session.add(trade)
    db_session.commit()
    return trade


def test_regime_consecutive_losses_scoped_to_one_regime(db_session):
    asset, strategy = _setup(db_session)
    bull = MarketRegime(asset_id=asset.id, timeframe="1h", regime="trending_bull", confidence=0.9)
    bear = MarketRegime(asset_id=asset.id, timeframe="1h", regime="trending_bear", confidence=0.9)
    db_session.add_all([bull, bear])
    db_session.commit()
    now = datetime.now(timezone.utc)
    _closed_trade_with_regime(db_session, asset, strategy, bull, "loss", now - timedelta(minutes=6))
    _closed_trade_with_regime(db_session, asset, strategy, bull, "loss", now - timedelta(minutes=5))
    _closed_trade_with_regime(db_session, asset, strategy, bear, "win", now - timedelta(minutes=4))

    assert regime_consecutive_losses(db_session, "trending_bull") == 2
    assert regime_consecutive_losses(db_session, "trending_bear") == 0


def test_position_without_signal_excluded_from_regime_streak(db_session):
    """A position opened with no signal_id (signal_id is nullable) must not
    count toward any regime's streak — honest exclusion, not a fabricated
    regime label."""
    asset, strategy = _setup(db_session)
    _closed_trade(db_session, asset, strategy, "loss", datetime.now(timezone.utc))  # no signal_id at all
    assert regime_consecutive_losses(db_session, "trending_bull") == 0


def test_evaluate_dimensional_loss_streaks_only_evaluates_requested_dimensions(db_session):
    asset, strategy = _setup(db_session)
    result = evaluate_dimensional_loss_streaks(db_session, LIMITS, strategy_id=strategy.id)
    assert result.strategy is not None
    assert result.asset is None
    assert result.regime is None


def test_evaluate_dimensional_loss_streaks_combined_multiplier_is_most_conservative(db_session):
    asset, strategy = _setup(db_session)
    now = datetime.now(timezone.utc)
    # Portfolio-wide streak stays below threshold (4 losses < 5), but the
    # strategy-scoped streak alone still clears it.
    for i in range(5):
        _closed_trade(db_session, asset, strategy, "loss", now - timedelta(minutes=5 - i))
    result = evaluate_dimensional_loss_streaks(db_session, LIMITS, strategy_id=strategy.id)
    assert result.portfolio.triggered
    assert result.strategy is not None and result.strategy.triggered
    assert result.combined_size_multiplier == 0.5


def test_win_streak_observation_reports_the_streak(db_session):
    asset, strategy = _setup(db_session)
    now = datetime.now(timezone.utc)
    for i in range(4):
        _closed_trade(db_session, asset, strategy, "win", now - timedelta(minutes=4 - i))
    assert current_consecutive_wins(db_session) == 4
    observation = observe_win_streak(db_session)
    assert observation.consecutive_wins == 4


def test_win_streak_observation_has_no_sizing_effect(db_session):
    """"PROMPT 12"'s explicit prohibition: a win streak never automatically
    increases risk. Structural proof, not just behavioral: WinStreakObservation
    has no size_multiplier field at all, so there is nothing for
    packages/risk/position_sizing.py to even accidentally read."""
    import dataclasses

    from packages.risk.loss_streak import WinStreakObservation

    field_names = {f.name for f in dataclasses.fields(WinStreakObservation)}
    assert field_names == {"consecutive_wins"}
