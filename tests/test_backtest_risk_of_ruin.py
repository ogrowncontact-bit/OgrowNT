import pytest

from packages.backtest.risk_of_ruin import estimate_risk_of_ruin

WINNING_TRADES = [{"pnl": 100.0, "entry_price": 50.0, "size": 10.0} for _ in range(10)]
MIXED_TRADES = [
    {"pnl": 100.0, "entry_price": 50.0, "size": 10.0}, {"pnl": -400.0, "entry_price": 50.0, "size": 10.0},
    {"pnl": 90.0, "entry_price": 50.0, "size": 10.0}, {"pnl": -350.0, "entry_price": 50.0, "size": 10.0},
    {"pnl": 80.0, "entry_price": 50.0, "size": 10.0}, {"pnl": -300.0, "entry_price": 50.0, "size": 10.0},
]


def test_requires_at_least_one_threshold():
    with pytest.raises(ValueError, match="threshold"):
        estimate_risk_of_ruin(WINNING_TRADES, initial_capital=10_000.0)


def test_no_trades_reports_none_with_assumptions_stated():
    result = estimate_risk_of_ruin([], initial_capital=10_000.0, drawdown_threshold_pct=20.0)
    assert result.probability_of_ruin is None
    assert result.assumptions  # non-empty -- documented, not silent


def test_all_winning_trades_never_ruins():
    result = estimate_risk_of_ruin(WINNING_TRADES, initial_capital=10_000.0, drawdown_threshold_pct=5.0, num_simulations=200, random_seed=1)
    assert result.probability_of_ruin == 0.0


def test_deep_losing_streak_risk_is_higher_than_shallow_threshold():
    shallow = estimate_risk_of_ruin(MIXED_TRADES, initial_capital=10_000.0, drawdown_threshold_pct=2.0, num_simulations=500, random_seed=5)
    deep = estimate_risk_of_ruin(MIXED_TRADES, initial_capital=10_000.0, drawdown_threshold_pct=50.0, num_simulations=500, random_seed=5)
    assert shallow.probability_of_ruin >= deep.probability_of_ruin


def test_reproducible_with_same_seed():
    r1 = estimate_risk_of_ruin(MIXED_TRADES, initial_capital=10_000.0, drawdown_threshold_pct=10.0, num_simulations=300, random_seed=9)
    r2 = estimate_risk_of_ruin(MIXED_TRADES, initial_capital=10_000.0, drawdown_threshold_pct=10.0, num_simulations=300, random_seed=9)
    assert r1.probability_of_ruin == r2.probability_of_ruin


def test_assumptions_are_documented_not_silent():
    result = estimate_risk_of_ruin(MIXED_TRADES, initial_capital=10_000.0, capital_loss_threshold_pct=30.0, num_simulations=100, random_seed=1)
    assert any("independent" in a or "resampled" in a for a in result.assumptions)
    assert any("not a" in a.lower() or "estimate" in a.lower() for a in result.assumptions)
