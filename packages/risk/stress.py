"""Risk Stress Engine — "PROMPT 12" §77-84.

Applies the EXISTING Monte Carlo / Risk of Ruin bootstrap-resampling
primitives (packages/backtest/monte_carlo.py, packages/backtest/
risk_of_ruin.py — both built for "PROMPT 7" backtesting) to the LIVE
portfolio's own realized Trade history, instead of requiring an isolated
single backtest run's trade list. A thin wrapper, not a reimplementation —
risk of ruin/Monte Carlo IS the same resampling question whether the
trades came from a backtest or from real (paper) trading.

Value at Risk / Expected Shortfall (CVaR) are the genuinely NEW addition
this module brings: a historical-simulation estimate over
PortfolioSnapshot's own equity-return history (not trade-level resampling
— VaR/ES are about the distribution of PERIOD RETURNS, a different
question from "how deep could a drawdown get"). Per §84's own instruction
these are never used as the SOLE risk metric — see
packages/risk/advanced_engine.py, where this sits alongside every other
dimension, never standing alone.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.backtest.monte_carlo import DEFAULT_NUM_SIMULATIONS, MonteCarloOutput, run_monte_carlo
from packages.backtest.risk_of_ruin import RiskOfRuinResult, estimate_risk_of_ruin
from packages.portfolio.state import get_reset_epoch
from packages.shared.models import PortfolioSnapshot, Position, Trade

# Below this many closed live trades, a bootstrap resample over them is too
# noisy to mean much -- run_monte_carlo/estimate_risk_of_ruin already
# handle zero trades honestly (see their own docstrings); this is the
# analogous "too little evidence" floor for the live-portfolio case.
MIN_TRADES_FOR_STRESS_TEST = 10

# Historical-simulation VaR needs enough period-return observations to be
# more than noise -- below this, compute_value_at_risk reports "not enough
# history" rather than a number built on 3 data points.
MIN_RETURNS_FOR_VAR = 20


def _live_trade_dicts(db: Session, epoch: datetime | None) -> list[dict]:
    """Same {"pnl", "entry_price", "size"} shape packages/backtest/engine.py
    already produces for a backtest's trades -- so run_monte_carlo/
    estimate_risk_of_ruin work unmodified on either source."""
    query = db.query(Trade, Position).join(Position, Trade.position_id == Position.id).order_by(Trade.closed_at.asc())
    if epoch is not None:
        query = query.filter(Trade.closed_at >= epoch)
    return [{"pnl": t.pnl, "entry_price": p.entry_price, "size": p.size} for t, p in query.all()]


@dataclass(frozen=True)
class LiveStressAssessment:
    trades_used: int
    sufficient_history: bool
    monte_carlo: MonteCarloOutput | None
    risk_of_ruin: RiskOfRuinResult | None


def run_live_stress_test(
    db: Session,
    *,
    initial_capital: float,
    method: str = "bootstrap",
    num_simulations: int = DEFAULT_NUM_SIMULATIONS,
    random_seed: int = 42,
    drawdown_threshold_pct: float | None = None,
    capital_loss_threshold_pct: float | None = None,
) -> LiveStressAssessment:
    trades = _live_trade_dicts(db, get_reset_epoch(db))
    if len(trades) < MIN_TRADES_FOR_STRESS_TEST:
        return LiveStressAssessment(trades_used=len(trades), sufficient_history=False, monte_carlo=None, risk_of_ruin=None)

    monte_carlo = run_monte_carlo(
        trades, initial_capital=initial_capital, method=method, num_simulations=num_simulations,
        random_seed=random_seed, drawdown_threshold_pct=drawdown_threshold_pct,
    )
    risk_of_ruin = None
    if drawdown_threshold_pct is not None or capital_loss_threshold_pct is not None:
        risk_of_ruin = estimate_risk_of_ruin(
            trades, initial_capital=initial_capital, drawdown_threshold_pct=drawdown_threshold_pct,
            capital_loss_threshold_pct=capital_loss_threshold_pct, num_simulations=num_simulations, random_seed=random_seed,
        )
    return LiveStressAssessment(trades_used=len(trades), sufficient_history=True, monte_carlo=monte_carlo, risk_of_ruin=risk_of_ruin)


@dataclass(frozen=True)
class ValueAtRiskResult:
    confidence: float
    num_returns: int
    var_pct: float | None  # magnitude of loss (positive), None if not enough history
    cvar_pct: float | None  # expected shortfall beyond VaR (positive), None if not enough history
    note: str


def _period_returns(db: Session, epoch: datetime | None) -> list[float]:
    query = select(PortfolioSnapshot.equity).order_by(PortfolioSnapshot.ts.asc())
    if epoch is not None:
        query = query.where(PortfolioSnapshot.ts >= epoch)
    equities = [row[0] for row in db.execute(query).all()]
    returns = []
    for i in range(1, len(equities)):
        prev = equities[i - 1]
        if prev > 0:
            returns.append((equities[i] - prev) / prev)
    return returns


def compute_value_at_risk(db: Session, *, confidence: float = 0.95) -> ValueAtRiskResult:
    """Historical simulation, not a parametric (variance-covariance) model
    — no assumption that returns are normally distributed. `confidence`
    e.g. 0.95 => "on a normal period, losses shouldn't exceed var_pct 95%
    of the time"; cvar_pct is the average loss in the worst (1-confidence)
    tail, always >= var_pct."""
    epoch = get_reset_epoch(db)
    returns = _period_returns(db, epoch)
    if len(returns) < MIN_RETURNS_FOR_VAR:
        return ValueAtRiskResult(
            confidence=confidence, num_returns=len(returns), var_pct=None, cvar_pct=None,
            note=(
                f"fewer than {MIN_RETURNS_FOR_VAR} portfolio_snapshots returns available -- not enough "
                "history for a historical-simulation VaR estimate"
            ),
        )
    ordered = sorted(returns)  # most negative (worst) first
    idx = max(0, min(int((1 - confidence) * len(ordered)), len(ordered) - 1))
    var_return = ordered[idx]
    tail = ordered[: idx + 1]
    cvar_return = sum(tail) / len(tail)
    return ValueAtRiskResult(
        confidence=confidence, num_returns=len(returns),
        var_pct=round(-var_return * 100, 4), cvar_pct=round(-cvar_return * 100, 4),
        note="historical simulation over portfolio_snapshots equity returns -- one signal among several, never the sole risk metric (PROMPT 12 §84)",
    )
