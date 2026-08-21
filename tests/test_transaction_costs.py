"""packages/risk/costs.py -- "PROMPT 12" §37-40 Transaction Cost Model &
Net Expectancy Gate."""
from __future__ import annotations

from packages.execution.fills import FEE_RATE, SPREAD_BPS
from packages.risk.costs import estimate_round_trip_cost, evaluate_net_expectancy


def test_round_trip_cost_is_positive_for_a_normal_trade():
    cost = estimate_round_trip_cost(mid_price=100.0, volume=1000.0, qty=1.0, direction="long")
    assert cost.total_cost > 0
    assert cost.entry_cost > 0
    assert cost.exit_cost > 0
    assert cost.total_cost == round(cost.entry_cost + cost.exit_cost, 4)


def test_round_trip_cost_long_and_short_are_symmetric():
    """Costs always work against the trader regardless of side (same
    guarantee packages/execution/fills.py::simulate_fill documents) -- a
    long and a short of the same size at the same price/volume should cost
    the same round-trip amount."""
    long_cost = estimate_round_trip_cost(mid_price=100.0, volume=1000.0, qty=2.0, direction="long")
    short_cost = estimate_round_trip_cost(mid_price=100.0, volume=1000.0, qty=2.0, direction="short")
    assert long_cost.total_cost == short_cost.total_cost


def test_round_trip_cost_scales_with_size():
    small = estimate_round_trip_cost(mid_price=100.0, volume=10000.0, qty=1.0, direction="long")
    large = estimate_round_trip_cost(mid_price=100.0, volume=10000.0, qty=10.0, direction="long")
    assert large.total_cost > small.total_cost


def test_round_trip_cost_pct_reflects_configured_spread_and_fee():
    # A large, liquid bar (volume >> qty) keeps slippage's size-scaling term
    # near its floor, so total_cost_pct should stay in the right ballpark
    # for SPREAD_BPS/FEE_RATE rather than exploding from slippage alone.
    cost = estimate_round_trip_cost(mid_price=100.0, volume=1_000_000.0, qty=1.0, direction="long")
    assert 0 < cost.total_cost_pct_of_notional < (SPREAD_BPS / 100) + (FEE_RATE * 100) + 1.0


def test_net_expectancy_not_evaluated_without_strategy_history():
    cost = estimate_round_trip_cost(mid_price=100.0, volume=1000.0, qty=1.0, direction="long")
    result = evaluate_net_expectancy(expectancy_r=None, risk_amount=50.0, cost=cost)
    assert result.evaluated is False
    assert result.passes is True  # no evidence to veto on, not a fabricated pass
    assert result.net_expected_edge is None


def test_net_expectancy_passes_when_edge_exceeds_costs():
    cost = estimate_round_trip_cost(mid_price=100.0, volume=100000.0, qty=1.0, direction="long")
    # Expectancy of 2.0R on a $500 risk amount = $1000 raw edge, dwarfing a
    # tiny round-trip cost on a $100 notional trade.
    result = evaluate_net_expectancy(expectancy_r=2.0, risk_amount=500.0, cost=cost)
    assert result.evaluated is True
    assert result.raw_expected_edge == 1000.0
    assert result.net_expected_edge is not None and result.net_expected_edge > 0
    assert result.passes is True


def test_net_expectancy_fails_when_costs_exceed_edge():
    cost = estimate_round_trip_cost(mid_price=100.0, volume=1000.0, qty=1.0, direction="long")
    # A tiny positive expectancy on a tiny risk amount can't outrun even a
    # small round-trip cost -- "se após custos: expected edge <= 0 então
    # NO_TRADE" (§37).
    result = evaluate_net_expectancy(expectancy_r=0.05, risk_amount=0.01, cost=cost)
    assert result.evaluated is True
    assert result.net_expected_edge is not None and result.net_expected_edge <= 0
    assert result.passes is False


def test_net_expectancy_negative_strategy_expectancy_always_fails():
    cost = estimate_round_trip_cost(mid_price=100.0, volume=1000.0, qty=1.0, direction="long")
    result = evaluate_net_expectancy(expectancy_r=-0.5, risk_amount=100.0, cost=cost)
    assert result.evaluated is True
    assert result.raw_expected_edge == -50.0
    assert result.passes is False
