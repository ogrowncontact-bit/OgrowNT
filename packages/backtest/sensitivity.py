"""Sensitivity analysis — "PROMPT 7" §35-37 (transaction cost, slippage,
capital). Each sweep re-runs the same strategy/asset/window at a series of
multipliers/levels and reports whether the strategy's edge survives —
"survival" means net_return stayed positive, the plain, literal reading of
§35's "Mostrar se a estratégia continua positiva."
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from packages.backtest.engine import BacktestResult, run_backtest
from packages.backtest.execution_models import ExecutionConfig, FeeModel, SlippageModel
from packages.quant.strategies.base import Strategy
from packages.risk.config import RiskLimits

# §35: Base Case, +25%, +50%, +100% costs.
COST_MULTIPLIERS = (1.0, 1.25, 1.5, 2.0)
# §36: normal, 2x, 5x, 10x slippage.
SLIPPAGE_MULTIPLIERS = (1.0, 2.0, 5.0, 10.0)
# §37: illustrative capital levels -- a real deployment's actual candidate
# sizes would replace these, exposed as a parameter for exactly that reason.
DEFAULT_CAPITAL_LEVELS = (1_000.0, 5_000.0, 10_000.0, 50_000.0, 100_000.0)


@dataclass(frozen=True)
class SensitivityPoint:
    level: float
    result: BacktestResult
    survived: bool | None


@dataclass(frozen=True)
class SensitivityReport:
    kind: str  # 'cost' | 'slippage' | 'capital'
    points: list[SensitivityPoint] = field(default_factory=list)
    survives_all_levels: bool | None = None


def _survived(result: BacktestResult) -> bool | None:
    return None if result.net_return is None else result.net_return > 0


def run_cost_sensitivity(
    db: Session, *, strategy: Strategy, asset_id: int, symbol: str, timeframe: str,
    start_ts: datetime, end_ts: datetime, initial_capital: float, risk_limits: RiskLimits | None = None,
    multipliers: tuple[float, ...] = COST_MULTIPLIERS,
) -> SensitivityReport:
    points = []
    for multiplier in multipliers:
        execution = ExecutionConfig(fee_model=FeeModel(kind="percentage", rate=0.0005 * multiplier))
        result = run_backtest(
            db, strategy=strategy, asset_id=asset_id, symbol=symbol, timeframe=timeframe,
            start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital, risk_limits=risk_limits, execution=execution,
        )
        points.append(SensitivityPoint(level=multiplier, result=result, survived=_survived(result)))
    judged = [p.survived for p in points if p.survived is not None]
    return SensitivityReport(kind="cost", points=points, survives_all_levels=all(judged) if judged else None)


def run_slippage_sensitivity(
    db: Session, *, strategy: Strategy, asset_id: int, symbol: str, timeframe: str,
    start_ts: datetime, end_ts: datetime, initial_capital: float, risk_limits: RiskLimits | None = None,
    multipliers: tuple[float, ...] = SLIPPAGE_MULTIPLIERS,
) -> SensitivityReport:
    points = []
    for multiplier in multipliers:
        execution = ExecutionConfig(slippage_model=SlippageModel(kind="liquidity_based", slippage_bps=2.0 * multiplier))
        result = run_backtest(
            db, strategy=strategy, asset_id=asset_id, symbol=symbol, timeframe=timeframe,
            start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital, risk_limits=risk_limits, execution=execution,
        )
        points.append(SensitivityPoint(level=multiplier, result=result, survived=_survived(result)))
    judged = [p.survived for p in points if p.survived is not None]
    return SensitivityReport(kind="slippage", points=points, survives_all_levels=all(judged) if judged else None)


def run_capital_sensitivity(
    db: Session, *, strategy: Strategy, asset_id: int, symbol: str, timeframe: str,
    start_ts: datetime, end_ts: datetime, risk_limits: RiskLimits | None = None,
    capital_levels: tuple[float, ...] = DEFAULT_CAPITAL_LEVELS,
) -> SensitivityReport:
    points = []
    for capital in capital_levels:
        result = run_backtest(
            db, strategy=strategy, asset_id=asset_id, symbol=symbol, timeframe=timeframe,
            start_ts=start_ts, end_ts=end_ts, initial_capital=capital, risk_limits=risk_limits,
        )
        points.append(SensitivityPoint(level=capital, result=result, survived=_survived(result)))
    judged = [p.survived for p in points if p.survived is not None]
    return SensitivityReport(kind="capital", points=points, survives_all_levels=all(judged) if judged else None)
