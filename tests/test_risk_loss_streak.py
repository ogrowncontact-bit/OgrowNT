"""packages/risk/loss_streak.py — "PROMPT 8" §37-40: portfolio-wide loss
streak detection and the anti-martingale guarantee (a win streak never
increases size)."""
from datetime import datetime, timedelta, timezone

from packages.risk.config import LossStreakConfig
from packages.risk.loss_streak import current_consecutive_losses, evaluate_loss_streak
from packages.shared.models import Asset, Position, StrategyRow, Trade

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
