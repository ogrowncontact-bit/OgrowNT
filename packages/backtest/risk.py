"""Backtest-local adaptation of the Risk Engine's DET primitives
(docs/blueprint/08-risk-engine.md) — evaluates a candidate signal against a
*simulated* single-asset portfolio, reusing the exact same pure
safety-belt/position-sizing functions production uses
(packages/risk/safety_belt.py, packages/risk/position_sizing.py), per
docs/blueprint/10-backtesting-paper-trading.md: "usa o mesmo Risk Engine/
PositionSizer... da produção."

Deliberately narrower than packages/risk/engine.py's full pipeline:
- No correlation guard: packages/backtest/engine.py only ever holds one
  open position at a time in one asset, so cross-asset correlation is
  structurally vacuous here — not skipped for convenience, skipped because
  there is nothing for it to check. A genuinely multi-asset, portfolio-
  level backtest is a natural future extension.
- No live system_state/kill-switch: that gates the live system, not a
  historical replay. should_trigger_kill_switch is still applied to the
  simulated portfolio's own drawdown, since that IS a property of this
  backtest run.
- No RiskCheck/RiskDecision persistence: the backtest's own trade list and
  equity curve (packages/backtest/portfolio.py) are its audit trail —
  writing rows tied to a signal_id that was never persisted would pollute
  the live audit tables for no benefit.
"""
from __future__ import annotations

from dataclasses import dataclass

from packages.portfolio.state import PortfolioState
from packages.risk.config import RiskLimits
from packages.risk.position_sizing import calculate_position_size
from packages.risk.safety_belt import evaluate_safety_belt, policy_for, should_trigger_kill_switch, tier_meets_floor


@dataclass(frozen=True)
class BacktestRiskVerdict:
    approved: bool
    approved_quantity: float | None
    reason: str


def evaluate_signal_for_backtest(
    *, tier: str, risk_reward: float, entry_price: float, stop_price: float, confidence: float,
    volatility_factor: float, portfolio_state: PortfolioState, limits: RiskLimits,
) -> BacktestRiskVerdict:
    if should_trigger_kill_switch(portfolio_state, limits):
        return BacktestRiskVerdict(False, None, "kill_switch")

    belt = evaluate_safety_belt(portfolio_state, limits)
    policy = policy_for(belt, limits)
    if not policy.allow_new_trades:
        return BacktestRiskVerdict(False, None, f"safety_belt_{belt}")
    if not tier_meets_floor(tier, policy.min_tier):
        return BacktestRiskVerdict(False, None, "below_safety_belt_tier_floor")

    if risk_reward < limits.per_trade.min_risk_reward:
        return BacktestRiskVerdict(False, None, "poor_risk_reward")

    # At most one open position at a time (packages/backtest/engine.py) ->
    # full portfolio/single-asset exposure headroom is always available
    # going into a new trade.
    portfolio_headroom_pct = limits.portfolio.max_exposure_pct
    single_asset_headroom_pct = limits.portfolio.max_single_asset_pct

    if portfolio_state.daily_loss_pct >= limits.loss_limits.max_daily_loss_pct:
        return BacktestRiskVerdict(False, None, "daily_loss_limit")
    if portfolio_state.weekly_loss_pct >= limits.loss_limits.max_weekly_loss_pct:
        return BacktestRiskVerdict(False, None, "weekly_loss_limit")

    sizing = calculate_position_size(
        capital=portfolio_state.equity, entry_price=entry_price, stop_price=stop_price, confidence=confidence,
        volatility_factor=volatility_factor, portfolio_headroom_pct=min(portfolio_headroom_pct, single_asset_headroom_pct),
        correlation_headroom_pct=limits.portfolio.max_correlated_cluster_pct, limits=limits,
    )
    approved_quantity = sizing.quantity * policy.size_multiplier
    if approved_quantity <= 0:
        return BacktestRiskVerdict(False, None, "zero_size")

    return BacktestRiskVerdict(True, approved_quantity, "approved")
