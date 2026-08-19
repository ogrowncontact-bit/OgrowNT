"""Backtest Report / full Strategy Lab run — "PROMPT 7" §50 (the 13-section
report) and the orchestrator behind the `full_lab` BacktestJob kind
(apps/backtest_worker) and the Strategy Lab dashboard panel. Runs every
analysis this phase added, once, over the same strategy/asset/window, and
assembles the results into the 13 named sections.

Deliberately bounded by default (small walk-forward-optimization grid,
moderate Monte Carlo sample count) -- this function alone can trigger
dozens of nested backtest re-runs; the mock market data provider's short
history (packages/backtest/engine.py's own docstring) already limits how
much a bigger budget would actually buy here.

§51's wording rule lives entirely inside quality_score.py's closed label
sets (already enforced there) -- this module only ever assembles those
labels into the report, never writes its own free-text verdict.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from sqlalchemy.orm import Session

from packages.backtest.data_integrity import check_data_integrity
from packages.backtest.engine import run_backtest
from packages.backtest.failure_detector import detect_strategy_failure
from packages.backtest.monte_carlo import run_monte_carlo
from packages.backtest.quality_score import compute_quality_score
from packages.backtest.reality_gap import analyze_reality_gap
from packages.backtest.robustness import compute_robustness_score
from packages.backtest.sensitivity import run_cost_sensitivity, run_slippage_sensitivity
from packages.backtest.stability import check_parameter_stability
from packages.backtest.stress_test import SCENARIOS, run_stress_scenario
from packages.backtest.walkforward_optimization import run_walk_forward_optimization
from packages.quant.strategies import STRATEGY_CLASSES
from packages.risk.config import RiskLimits, load_risk_limits
from packages.shared.models import Asset, StrategyRow

DEFAULT_MONTE_CARLO_SIMULATIONS = 300
# Walk-forward-optimization's train/validation windows are sized as a
# fraction of whatever period was actually requested, not a fixed absolute
# number of days -- with only a short mock-data history available
# (packages/backtest/engine.py's own docstring), a hardcoded "1 day train"
# would never produce even one window. Same 60/20 split spirit as
# packages/backtest/split.py's TRAIN/VALIDATION ratios, applied as a
# rolling window size here rather than a single held-out slice.
WF_TRAIN_FRACTION = 0.5
WF_VALIDATION_FRACTION = 0.2
DEFAULT_MAX_DRAWDOWN_LIMIT_PCT = 20.0


def run_full_lab(
    db: Session, *, strategy_row: StrategyRow, asset: Asset, timeframe: str,
    start_ts: datetime, end_ts: datetime, initial_capital: float, risk_limits: RiskLimits | None = None,
    monte_carlo_simulations: int = DEFAULT_MONTE_CARLO_SIMULATIONS, random_seed: int = 42,
    run_stress_tests: bool = True, run_walk_forward: bool = True,
) -> dict:
    limits = risk_limits or load_risk_limits()
    strategy_class = STRATEGY_CLASSES.get(strategy_row.code)
    if strategy_class is None:
        return {"blocked": True, "reason": f"no backtest-capable strategy implementation registered for '{strategy_row.code}'"}

    integrity = check_data_integrity(db, asset.id, timeframe, start_ts, end_ts)
    if integrity.blocked:
        return {
            "blocked": True, "reason": "BACKTEST_BLOCKED",
            "data": {"issues": [asdict(i) for i in integrity.issues], "bars_checked": integrity.bars_checked},
        }

    baseline = run_backtest(
        db, strategy=strategy_class(), asset_id=asset.id, symbol=asset.symbol, timeframe=timeframe,
        start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital, risk_limits=limits,
    )

    stability = check_parameter_stability(
        db, strategy_code=strategy_row.code, asset_id=asset.id, symbol=asset.symbol, timeframe=timeframe,
        start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital, risk_limits=limits,
    )

    walk_forward = None
    if run_walk_forward:
        window_days = (end_ts - start_ts).total_seconds() / 86400
        walk_forward = run_walk_forward_optimization(
            db, strategy_code=strategy_row.code, asset_id=asset.id, symbol=asset.symbol, timeframe=timeframe,
            start_ts=start_ts, end_ts=end_ts, train_days=window_days * WF_TRAIN_FRACTION,
            validation_days=window_days * WF_VALIDATION_FRACTION, initial_capital=initial_capital, risk_limits=limits,
        )

    monte_carlo = run_monte_carlo(
        baseline.trades, initial_capital=initial_capital, method="bootstrap",
        num_simulations=monte_carlo_simulations, random_seed=random_seed, drawdown_threshold_pct=DEFAULT_MAX_DRAWDOWN_LIMIT_PCT,
    )

    cost_sensitivity = run_cost_sensitivity(
        db, strategy=strategy_class(), asset_id=asset.id, symbol=asset.symbol, timeframe=timeframe,
        start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital, risk_limits=limits,
    )
    slippage_sensitivity = run_slippage_sensitivity(
        db, strategy=strategy_class(), asset_id=asset.id, symbol=asset.symbol, timeframe=timeframe,
        start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital, risk_limits=limits,
    )

    stress_results = []
    if run_stress_tests:
        for scenario in SCENARIOS:
            stress_results.append(
                run_stress_scenario(
                    db, scenario=scenario, strategy_factory=strategy_class, asset_id=asset.id, symbol=asset.symbol,
                    timeframe=timeframe, start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital, risk_limits=limits,
                )
            )

    regime_breakdown = baseline.extra_metrics.get("regime_breakdown")
    robustness = compute_robustness_score(
        walk_forward=walk_forward, stability=stability, max_drawdown_pct=baseline.max_drawdown,
        num_trades=baseline.num_trades, regime_breakdown=regime_breakdown, asset_count=1,
        cost_sensitivity_survives=cost_sensitivity.survives_all_levels,
        slippage_sensitivity_survives=slippage_sensitivity.survives_all_levels,
    )
    quality = compute_quality_score(expectancy=baseline.expectancy, num_trades=baseline.num_trades, robustness=robustness)
    reality_gap = analyze_reality_gap(db, strategy_row.id)
    failure = detect_strategy_failure(
        expectancy=baseline.expectancy, max_drawdown_pct=baseline.max_drawdown, max_drawdown_limit_pct=DEFAULT_MAX_DRAWDOWN_LIMIT_PCT,
        quality_status=quality.status, reality_gap=reality_gap, monte_carlo_probability_of_loss=monte_carlo.probability_of_loss,
        cost_sensitivity_survives=cost_sensitivity.survives_all_levels, slippage_sensitivity_survives=slippage_sensitivity.survives_all_levels,
    )

    return {
        "blocked": False,
        "configuration": {
            "strategy_code": strategy_row.code, "asset_symbol": asset.symbol, "timeframe": timeframe,
            "start_ts": start_ts.isoformat(), "end_ts": end_ts.isoformat(), "initial_capital": initial_capital,
            "risk_config": "config/risk_limits.yaml (production risk limits, same as paper trading)",
        },
        "data": {
            "bars_checked": integrity.bars_checked,
            "issues": [asdict(i) for i in integrity.issues],
            "data_fingerprint": baseline.data_fingerprint,
        },
        "strategy": {"code": strategy_row.code, "name": strategy_row.name, "version": strategy_row.version, "params": strategy_row.params},
        "performance": {
            "num_trades": baseline.num_trades, "net_return": baseline.net_return, "cagr_like_return": baseline.cagr_like_return,
            "win_rate": baseline.win_rate, "profit_factor": baseline.profit_factor, "expectancy": baseline.expectancy,
            "sharpe_like": baseline.sharpe_like, "sortino_ratio": baseline.extra_metrics.get("sortino_ratio"),
            "avg_win": baseline.extra_metrics.get("avg_win"), "avg_loss": baseline.extra_metrics.get("avg_loss"),
            "gross_profit": baseline.extra_metrics.get("gross_profit"), "gross_loss": baseline.extra_metrics.get("gross_loss"),
        },
        "risk": {
            "max_drawdown": baseline.max_drawdown, "avg_exposure_pct": baseline.extra_metrics.get("avg_exposure_pct"),
            "turnover": baseline.extra_metrics.get("turnover"), "risk_veto_counts": baseline.extra_metrics.get("risk_veto_counts", {}),
            "total_fees": baseline.extra_metrics.get("total_fees"),
        },
        "drawdown": baseline.extra_metrics.get("drawdown_detail"),
        "walk_forward": {
            "consistent": walk_forward.consistent if walk_forward else None,
            "reason": walk_forward.reason if walk_forward else "not run",
            "pooled_oos_expectancy": walk_forward.pooled_oos_expectancy if walk_forward else None,
            "num_windows": len(walk_forward.windows) if walk_forward else 0,
        },
        "monte_carlo": {
            "method": monte_carlo.method, "num_simulations": monte_carlo.num_simulations,
            "percentiles": monte_carlo.percentiles, "probability_of_loss": monte_carlo.probability_of_loss,
            "probability_of_drawdown_threshold": monte_carlo.probability_of_drawdown_threshold,
        },
        "stress_tests": [
            {"scenario": r.scenario, "params": r.params, "return_delta": r.return_delta, "drawdown_delta": r.drawdown_delta, "survived": r.survived, "notes": r.notes}
            for r in stress_results
        ],
        "robustness": {"score": robustness.score, "components": [asdict(c) for c in robustness.components], "insufficient_evidence": robustness.insufficient_evidence},
        "parameter_stability": {"stable": stability.stable, "reason": stability.reason},
        "reality_gap": asdict(reality_gap),
        "final_assessment": {
            "quality_score": quality.score, "status": quality.status, "assessment": quality.final_assessment,
            "reasons": quality.reasons, "failure_verdict": failure.verdict, "failure_reasons": failure.reasons,
        },
    }
