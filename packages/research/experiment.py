"""ExperimentEngine — "PROMPT 10" §16-21, §31, §89.

Evaluates a strategy CONFIGURATION (code + specific params) end-to-end by
composing the exact same primitives `packages/backtest/report.py::run_full_lab`
already composes (backtest, parameter stability, walk-forward, Monte
Carlo, cost/slippage sensitivity, stress tests, robustness/quality
scoring) — deliberately NOT `run_full_lab` itself, since that function
always evaluates a strategy class's own hardcoded constructor defaults
(the Strategy Lab dashboard's existing use case); an experiment needs to
evaluate two SPECIFIC, independently-chosen parameter sets against each
other (§17 "CONTROL vs CANDIDATE"), so this threads `params` through
instead. No backtesting math is duplicated — every call below is the same
function Strategy Lab already uses.

Reproducibility (§89): `code_version` (git sha / `OGROWNT_CODE_VERSION`),
`random_seed`, and every input parameter are recorded on the persisted
`Experiment` row — re-running the same `ExperimentSpec` against the same
data produces the same result.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.backtest.data_integrity import check_data_integrity
from packages.backtest.engine import run_backtest
from packages.backtest.monte_carlo import run_monte_carlo
from packages.backtest.overfitting import classify_overfitting
from packages.backtest.quality_score import compute_quality_score
from packages.backtest.robustness import compute_robustness_score
from packages.backtest.sensitivity import run_cost_sensitivity, run_slippage_sensitivity
from packages.backtest.split import split_train_validation_test
from packages.backtest.stability import check_parameter_stability
from packages.backtest.stress_test import SCENARIOS, run_stress_scenario
from packages.backtest.versioning import get_code_version
from packages.backtest.walkforward import run_walk_forward
from packages.quant.strategies import STRATEGY_CLASSES
from packages.risk.config import RiskLimits, load_risk_limits
from packages.shared.models import Asset
from packages.shared.models import Experiment as ExperimentRow

DEFAULT_MONTE_CARLO_SIMULATIONS = 200
DEFAULT_RANDOM_SEED = 42
DEFAULT_MAX_DRAWDOWN_LIMIT_PCT = 20.0
MIN_WINDOW_DAYS = 1.0
WALK_FORWARD_WINDOWS = 4


@dataclass(frozen=True)
class ArmSpec:
    """One side of an experiment — CONTROL or CANDIDATE, "PROMPT 10" §17."""
    strategy_code: str
    params: dict = field(default_factory=dict)
    label: str = ""


@dataclass(frozen=True)
class ArmReport:
    strategy_code: str
    params: dict
    num_trades: int
    net_return: float | None
    expectancy: float | None
    max_drawdown: float | None
    win_rate: float | None
    profit_factor: float | None
    sharpe_like: float | None
    walk_forward_consistent: bool | None
    stability_stable: bool | None
    monte_carlo_probability_of_loss: float | None
    cost_sensitivity_survives: bool | None
    slippage_sensitivity_survives: bool | None
    stress_survival_count: int
    stress_scenario_count: int
    overfitting: dict
    robustness_score: float
    quality_score: float
    quality_status: str
    data_fingerprint: str | None


def _instantiate(strategy_code: str, params: dict):
    strategy_class = STRATEGY_CLASSES.get(strategy_code)
    if strategy_class is None:
        raise ValueError(f"unknown strategy code: {strategy_code!r}")
    return strategy_class(**params) if params else strategy_class()


def evaluate_arm(
    db: Session, *, arm: ArmSpec, asset: Asset, timeframe: str, start_ts: datetime, end_ts: datetime,
    initial_capital: float, risk_limits: RiskLimits, monte_carlo_simulations: int = DEFAULT_MONTE_CARLO_SIMULATIONS,
    random_seed: int = DEFAULT_RANDOM_SEED,
) -> ArmReport:
    strategy_class = STRATEGY_CLASSES.get(arm.strategy_code)
    if strategy_class is None:
        raise ValueError(f"unknown strategy code: {arm.strategy_code!r}")

    full_result = run_backtest(
        db, strategy=_instantiate(arm.strategy_code, arm.params), asset_id=asset.id, symbol=asset.symbol,
        timeframe=timeframe, start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital, risk_limits=risk_limits,
    )

    split = split_train_validation_test(start_ts, end_ts)
    train_result = run_backtest(
        db, strategy=_instantiate(arm.strategy_code, arm.params), asset_id=asset.id, symbol=asset.symbol,
        timeframe=timeframe, start_ts=split.train_start, end_ts=split.train_end, initial_capital=initial_capital, risk_limits=risk_limits,
    )
    test_result = run_backtest(
        db, strategy=_instantiate(arm.strategy_code, arm.params), asset_id=asset.id, symbol=asset.symbol,
        timeframe=timeframe, start_ts=split.test_start, end_ts=split.test_end, initial_capital=initial_capital, risk_limits=risk_limits,
    )
    overfitting = classify_overfitting(train_result.net_return, test_result.net_return)

    window_days = max(MIN_WINDOW_DAYS, (end_ts - start_ts).total_seconds() / 86400 / WALK_FORWARD_WINDOWS)
    walk_forward = run_walk_forward(
        db, strategy=_instantiate(arm.strategy_code, arm.params), asset_id=asset.id, symbol=asset.symbol,
        timeframe=timeframe, start_ts=start_ts, end_ts=end_ts, window_days=window_days, initial_capital=initial_capital, risk_limits=risk_limits,
    )

    stability = check_parameter_stability(
        db, strategy_code=arm.strategy_code, asset_id=asset.id, symbol=asset.symbol, timeframe=timeframe,
        start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital, risk_limits=risk_limits, base_params=arm.params or None,
    )

    monte_carlo = run_monte_carlo(
        full_result.trades, initial_capital=initial_capital, method="bootstrap", num_simulations=monte_carlo_simulations,
        random_seed=random_seed, drawdown_threshold_pct=DEFAULT_MAX_DRAWDOWN_LIMIT_PCT,
    )

    cost = run_cost_sensitivity(
        db, strategy=_instantiate(arm.strategy_code, arm.params), asset_id=asset.id, symbol=asset.symbol,
        timeframe=timeframe, start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital, risk_limits=risk_limits,
    )
    slippage = run_slippage_sensitivity(
        db, strategy=_instantiate(arm.strategy_code, arm.params), asset_id=asset.id, symbol=asset.symbol,
        timeframe=timeframe, start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital, risk_limits=risk_limits,
    )

    def _factory():
        return _instantiate(arm.strategy_code, arm.params)

    stress_results = [
        run_stress_scenario(
            db, scenario=scenario, strategy_factory=_factory, asset_id=asset.id, symbol=asset.symbol,
            timeframe=timeframe, start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital, risk_limits=risk_limits,
        )
        for scenario in SCENARIOS
    ]
    stress_survival_count = sum(1 for r in stress_results if r.survived)

    # walk_forward here is the plain (fixed-params) run_walk_forward, not
    # the optimization variant compute_robustness_score's OOS/consistency
    # components expect -- passing None is the honest choice (no false
    # credit for evidence this call didn't produce); walk_forward_consistent
    # is still surfaced separately on ArmReport below so the information
    # isn't lost, just not folded into this particular 0-100 number.
    regime_breakdown = full_result.extra_metrics.get("regime_breakdown")
    robustness = compute_robustness_score(
        walk_forward=None, stability=stability, max_drawdown_pct=full_result.max_drawdown, num_trades=full_result.num_trades,
        regime_breakdown=regime_breakdown, asset_count=1,
        cost_sensitivity_survives=cost.survives_all_levels, slippage_sensitivity_survives=slippage.survives_all_levels,
    )
    quality = compute_quality_score(expectancy=full_result.expectancy, num_trades=full_result.num_trades, robustness=robustness)

    return ArmReport(
        strategy_code=arm.strategy_code, params=arm.params, num_trades=full_result.num_trades, net_return=full_result.net_return,
        expectancy=full_result.expectancy, max_drawdown=full_result.max_drawdown, win_rate=full_result.win_rate,
        profit_factor=full_result.profit_factor, sharpe_like=full_result.sharpe_like,
        walk_forward_consistent=walk_forward.consistent, stability_stable=stability.stable,
        monte_carlo_probability_of_loss=monte_carlo.probability_of_loss,
        cost_sensitivity_survives=cost.survives_all_levels, slippage_sensitivity_survives=slippage.survives_all_levels,
        stress_survival_count=stress_survival_count, stress_scenario_count=len(stress_results),
        overfitting={
            "label": overfitting.label, "train_return": overfitting.train_return, "test_return": overfitting.test_return,
            "degradation_ratio": overfitting.degradation_ratio, "reason": overfitting.reason,
        },
        robustness_score=robustness.score, quality_score=quality.score, quality_status=quality.status,
        data_fingerprint=full_result.data_fingerprint,
    )


def changed_params(control: dict, candidate: dict) -> list[str]:
    keys = set(control) | set(candidate)
    return sorted(k for k in keys if control.get(k) != candidate.get(k))


def run_experiment(
    db: Session, *, hypothesis_id: int | None, type: str, control: ArmSpec, candidate: ArmSpec,
    asset: Asset, timeframe: str, start_ts: datetime, end_ts: datetime, initial_capital: float = 10_000.0,
    monte_carlo_simulations: int = DEFAULT_MONTE_CARLO_SIMULATIONS, random_seed: int = DEFAULT_RANDOM_SEED,
    risk_limits: RiskLimits | None = None,
) -> ExperimentRow:
    limits = risk_limits or load_risk_limits()
    changed = changed_params(control.params, candidate.params)

    row = ExperimentRow(
        hypothesis_id=hypothesis_id, type=type,
        control={"strategy_code": control.strategy_code, "params": control.params, "label": control.label},
        candidate={"strategy_code": candidate.strategy_code, "params": candidate.params, "label": candidate.label, "changed_params": changed},
        dataset={"asset_symbol": asset.symbol, "timeframe": timeframe, "start_ts": start_ts.isoformat(), "end_ts": end_ts.isoformat()},
        parameters={"initial_capital": initial_capital, "monte_carlo_simulations": monte_carlo_simulations, "random_seed": random_seed},
        status="running",
        reproducibility={
            "code_version": get_code_version(), "random_seed": random_seed, "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    db.add(row)
    db.commit()

    integrity = check_data_integrity(db, asset.id, timeframe, start_ts, end_ts)
    if integrity.blocked:
        row.status = "failed"
        row.result = {"blocked": True, "reason": "BACKTEST_BLOCKED", "issues": [asdict(i) for i in integrity.issues]}
        row.completed_at = datetime.now(timezone.utc)
        db.commit()
        return row

    control_report = evaluate_arm(
        db, arm=control, asset=asset, timeframe=timeframe, start_ts=start_ts, end_ts=end_ts,
        initial_capital=initial_capital, risk_limits=limits, monte_carlo_simulations=monte_carlo_simulations, random_seed=random_seed,
    )
    candidate_report = evaluate_arm(
        db, arm=candidate, asset=asset, timeframe=timeframe, start_ts=start_ts, end_ts=end_ts,
        initial_capital=initial_capital, risk_limits=limits, monte_carlo_simulations=monte_carlo_simulations, random_seed=random_seed,
    )

    status, reasons = _classify_experiment(control_report, candidate_report, changed)

    row.status = status
    row.result = {
        "control_report": asdict(control_report), "candidate_report": asdict(candidate_report),
        "changed_params": changed, "one_change_at_a_time": len(changed) <= 1, "reasons": reasons,
        "expectancy_delta": _delta(control_report.expectancy, candidate_report.expectancy),
        "net_return_delta": _delta(control_report.net_return, candidate_report.net_return),
        "max_drawdown_delta": _delta(control_report.max_drawdown, candidate_report.max_drawdown),
        "quality_score_delta": round(candidate_report.quality_score - control_report.quality_score, 2),
    }
    row.completed_at = datetime.now(timezone.utc)
    db.commit()
    return row


def _delta(control: float | None, candidate: float | None) -> float | None:
    if control is None or candidate is None:
        return None
    return round(candidate - control, 6)


def _classify_experiment(control: ArmReport, candidate: ArmReport, changed: list[str]) -> tuple[str, list[str]]:
    """§20's status vocabulary, DET-only. QUARANTINED here means "the
    candidate itself failed badly enough it should never be proposed for
    shadow trading" -- not the strategy-level quarantine
    (packages/quant/learning/quarantine.py), a different entity entirely.
    """
    reasons: list[str] = []
    if candidate.num_trades == 0:
        return "failed", ["candidate produced zero trades over the experiment period"]
    if candidate.overfitting["label"] == "SEVERE_OVERFITTING":
        return "quarantined", [f"candidate shows severe overfitting: {candidate.overfitting['reason']}"]
    if candidate.expectancy is not None and candidate.expectancy <= 0:
        reasons.append(f"candidate expectancy {candidate.expectancy} is not positive")
        return "rejected", reasons
    if candidate.stability_stable is False:
        reasons.append("candidate failed the parameter-stability check (perturbation flips the expectancy sign)")
        return "rejected", reasons
    if control.expectancy is not None and candidate.expectancy is not None and candidate.expectancy <= control.expectancy:
        reasons.append(f"candidate expectancy {candidate.expectancy} did not improve on control {control.expectancy}")
        return "rejected", reasons

    reasons.append(f"candidate expectancy {candidate.expectancy} improves on control {control.expectancy}")
    if candidate.quality_score >= 70.0 and candidate.stability_stable and (candidate.walk_forward_consistent or False):
        return "promising", reasons
    return "validating", reasons + ["needs more evidence (walk-forward consistency, stability, or sample size) before promising"]
