"""Transaction Cost Model & Net Expectancy Gate — "PROMPT 12" §37-40.

Reuses packages/execution/fills.py::simulate_fill -- the SAME spread/
slippage/fee model already used by both PaperExecutionProvider and the
Backtest Engine -- for the round-trip cost estimate, rather than a second,
drifting cost model.

"Se após custos: expected edge <= 0 então: NO_TRADE" (§37): expected edge
is the STRATEGY's own historical expectancy
(StrategyPerformance.expectancy, an R-multiple computed from real closed
trades — packages/quant/learning/strategy_stats.py), converted to dollar
terms via the candidate trade's own risk amount (entry-to-stop distance x
size). expectancy is None only when the strategy has no closed trade with
a recorded r_multiple yet -- in that case evaluate_net_expectancy honestly
reports "not enough evidence to evaluate" (passes=True, evaluated=False)
rather than fabricating a pass or a block from an unproven number, the
same "no hallucinated data" convention strategy_stats.py already uses for
health_score=None below its own minimum sample size.

This module deliberately does NOT wire itself into
packages/risk/engine.py::evaluate_signal — that happens once
AdvancedRiskEngine exists (packages/risk/advanced_engine.py, wired in a
later task) and can supply the strategy_id/qty/risk_amount context this
needs.
"""
from __future__ import annotations

from dataclasses import dataclass

from packages.execution.fills import simulate_fill


@dataclass(frozen=True)
class RoundTripCostEstimate:
    entry_cost: float
    exit_cost: float
    total_cost: float
    total_cost_pct_of_notional: float


def estimate_round_trip_cost(*, mid_price: float, volume: float, qty: float, direction: str) -> RoundTripCostEstimate:
    """Both legs priced off the SAME mid_price (a simplifying "cost drag"
    estimate, not a P&L forecast — we don't know the future exit price at
    entry time). `direction` follows Position.direction's vocabulary
    ('long' enters by buying and exits by selling; 'short' the reverse).
    """
    entry_side = "buy" if direction == "long" else "sell"
    exit_side = "sell" if direction == "long" else "buy"

    entry_fill = simulate_fill(mid_price=mid_price, volume=volume, qty=qty, side=entry_side)
    exit_fill = simulate_fill(mid_price=mid_price, volume=volume, qty=qty, side=exit_side)

    entry_cost = abs(entry_fill.price - mid_price) * qty + entry_fill.fees
    exit_cost = abs(exit_fill.price - mid_price) * qty + exit_fill.fees
    total_cost = entry_cost + exit_cost
    notional = mid_price * qty
    total_cost_pct = (total_cost / notional * 100) if notional > 0 else 0.0

    return RoundTripCostEstimate(
        entry_cost=round(entry_cost, 4),
        exit_cost=round(exit_cost, 4),
        total_cost=round(total_cost, 4),
        total_cost_pct_of_notional=round(total_cost_pct, 4),
    )


@dataclass(frozen=True)
class NetExpectancyResult:
    evaluated: bool  # False when the strategy has no evidenced expectancy yet
    raw_expectancy_r: float | None
    raw_expected_edge: float | None  # dollars, before costs
    round_trip_cost: float | None  # dollars
    net_expected_edge: float | None  # dollars, after costs
    passes: bool  # True unless evaluated AND net_expected_edge <= 0


def evaluate_net_expectancy(*, expectancy_r: float | None, risk_amount: float, cost: RoundTripCostEstimate) -> NetExpectancyResult:
    if expectancy_r is None:
        return NetExpectancyResult(
            evaluated=False, raw_expectancy_r=None, raw_expected_edge=None,
            round_trip_cost=cost.total_cost, net_expected_edge=None, passes=True,
        )
    raw_edge = expectancy_r * risk_amount
    net_edge = raw_edge - cost.total_cost
    return NetExpectancyResult(
        evaluated=True, raw_expectancy_r=expectancy_r, raw_expected_edge=round(raw_edge, 4),
        round_trip_cost=cost.total_cost, net_expected_edge=round(net_edge, 4), passes=net_edge > 0,
    )
