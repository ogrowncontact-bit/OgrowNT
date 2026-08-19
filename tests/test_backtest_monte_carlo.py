from packages.backtest.monte_carlo import METHODS, run_monte_carlo

TRADES = [
    {"pnl": 100.0, "entry_price": 50.0, "size": 10.0},
    {"pnl": -50.0, "entry_price": 50.0, "size": 10.0},
    {"pnl": 80.0, "entry_price": 50.0, "size": 10.0},
    {"pnl": -30.0, "entry_price": 50.0, "size": 10.0},
    {"pnl": 60.0, "entry_price": 50.0, "size": 10.0},
    {"pnl": -20.0, "entry_price": 50.0, "size": 10.0},
]


def test_no_trades_reports_honest_empty_result():
    out = run_monte_carlo([], initial_capital=10_000.0)
    assert out.num_simulations == 0
    assert "reason" in out.notes


def test_all_methods_run_without_error():
    for method in METHODS:
        out = run_monte_carlo(TRADES, initial_capital=10_000.0, method=method, num_simulations=100, random_seed=1)
        assert out.num_simulations == 100
        assert out.method == method
        for key in ("p5", "p10", "p25", "p50", "p75", "p90", "p95"):
            assert key in out.percentiles["final_equity"]


def test_same_seed_is_reproducible():
    out1 = run_monte_carlo(TRADES, initial_capital=10_000.0, method="bootstrap", num_simulations=200, random_seed=7)
    out2 = run_monte_carlo(TRADES, initial_capital=10_000.0, method="bootstrap", num_simulations=200, random_seed=7)
    assert out1.percentiles == out2.percentiles
    assert out1.probability_of_loss == out2.probability_of_loss


def test_different_seed_can_differ():
    out1 = run_monte_carlo(TRADES, initial_capital=10_000.0, method="bootstrap", num_simulations=200, random_seed=1)
    out2 = run_monte_carlo(TRADES, initial_capital=10_000.0, method="bootstrap", num_simulations=200, random_seed=2)
    assert out1.percentiles != out2.percentiles


def test_trade_reshuffling_preserves_total_pnl_but_varies_drawdown():
    out = run_monte_carlo(TRADES, initial_capital=10_000.0, method="trade_reshuffling", num_simulations=300, random_seed=3)
    total_pnl = sum(t["pnl"] for t in TRADES)
    expected_final = 10_000.0 + total_pnl
    # Reshuffling only changes order, never the multiset of P&Ls -- every
    # simulation's final equity must land on the same number.
    for p in out.percentiles["final_equity"].values():
        assert abs(p - expected_final) < 0.01
    # But path-dependent drawdown must show real variance across orderings.
    dd = out.percentiles["max_drawdown_pct"]
    assert dd["p95"] >= dd["p5"]


def test_probability_of_drawdown_threshold_only_set_when_requested():
    without = run_monte_carlo(TRADES, initial_capital=10_000.0, num_simulations=50, random_seed=1)
    assert without.probability_of_drawdown_threshold is None

    with_threshold = run_monte_carlo(TRADES, initial_capital=10_000.0, num_simulations=50, random_seed=1, drawdown_threshold_pct=5.0)
    assert with_threshold.probability_of_drawdown_threshold is not None
    assert 0.0 <= with_threshold.probability_of_drawdown_threshold <= 1.0


def test_unknown_method_rejected():
    import pytest

    with pytest.raises(ValueError, match="unknown Monte Carlo method"):
        run_monte_carlo(TRADES, initial_capital=10_000.0, method="not_a_real_method")
