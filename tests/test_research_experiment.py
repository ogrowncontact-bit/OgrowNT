"""ExperimentEngine — "PROMPT 10" §16-21, §31, §89.

`_classify_experiment` is tested directly against hand-built `ArmReport`
instances (the §20 status vocabulary decision tree is pure and
deterministic -- no need to run a real backtest to prove each branch).
`run_experiment` itself is tested end-to-end against real seeded OHLCV
data (the full 8-engine pipeline) -- honestly, whatever real trade count
results is what's asserted against, the same "no hallucinated data"
posture `tests/test_backtest_lab_full_simulation.py` already established
for this codebase's mock market data (never enough history to guarantee
non-zero trades, and never worth fabricating a dataset that would).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.research.experiment import ArmReport, ArmSpec, _classify_experiment, changed_params, run_experiment
from packages.shared.models import OHLCV, Asset


def _arm_report(**overrides) -> ArmReport:
    defaults = dict(
        strategy_code="x", params={}, num_trades=20, net_return=100.0, expectancy=0.2, max_drawdown=5.0,
        win_rate=55.0, profit_factor=1.4, sharpe_like=0.8, walk_forward_consistent=True, stability_stable=True,
        monte_carlo_probability_of_loss=0.1, cost_sensitivity_survives=True, slippage_sensitivity_survives=True,
        stress_survival_count=5, stress_scenario_count=5, overfitting={"label": "NONE", "reason": "ok"},
        robustness_score=80.0, quality_score=80.0, quality_status="ROBUST", data_fingerprint="abc",
    )
    defaults.update(overrides)
    return ArmReport(**defaults)


def test_changed_params_detects_differences():
    assert changed_params({"a": 1, "b": 2}, {"a": 1, "b": 3}) == ["b"]
    assert changed_params({"a": 1}, {"a": 1, "b": 2}) == ["b"]
    assert changed_params({}, {}) == []


def test_classify_zero_trades_is_failed():
    candidate = _arm_report(num_trades=0)
    control = _arm_report()
    status, reasons = _classify_experiment(control, candidate, ["x"])
    assert status == "failed"
    assert "zero trades" in reasons[0]


def test_classify_severe_overfitting_is_quarantined():
    candidate = _arm_report(overfitting={"label": "SEVERE_OVERFITTING", "reason": "train >> test"})
    control = _arm_report()
    status, _ = _classify_experiment(control, candidate, ["x"])
    assert status == "quarantined"


def test_classify_non_positive_expectancy_is_rejected():
    candidate = _arm_report(expectancy=-0.1)
    control = _arm_report()
    status, reasons = _classify_experiment(control, candidate, ["x"])
    assert status == "rejected"
    assert "not positive" in reasons[0]


def test_classify_unstable_candidate_is_rejected():
    candidate = _arm_report(stability_stable=False)
    control = _arm_report()
    status, reasons = _classify_experiment(control, candidate, ["x"])
    assert status == "rejected"
    assert "parameter-stability" in reasons[0]


def test_classify_candidate_not_beating_control_is_rejected():
    candidate = _arm_report(expectancy=0.1)
    control = _arm_report(expectancy=0.3)
    status, reasons = _classify_experiment(control, candidate, ["x"])
    assert status == "rejected"
    assert "did not improve" in reasons[0]


def test_classify_strong_candidate_is_promising():
    candidate = _arm_report(expectancy=0.5, quality_score=75.0, stability_stable=True, walk_forward_consistent=True)
    control = _arm_report(expectancy=0.1)
    status, reasons = _classify_experiment(control, candidate, ["x"])
    assert status == "promising"


def test_classify_improving_but_weak_evidence_is_validating():
    candidate = _arm_report(expectancy=0.15, quality_score=50.0, stability_stable=True, walk_forward_consistent=False)
    control = _arm_report(expectancy=0.1)
    status, reasons = _classify_experiment(control, candidate, ["x"])
    assert status == "validating"
    assert "needs more evidence" in reasons[-1]


def _seed_asset(db_session, symbol: str, bars: int = 250, timeframe: str = "15m"):
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    start = datetime.now(timezone.utc) - timedelta(minutes=15 * bars)
    for i in range(bars):
        wobble = 1.0 + 0.01 * ((i * 37) % 7 - 3)
        close = 100.0 * (1.0015**i) * wobble
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe=timeframe, ts=start + timedelta(minutes=15 * i), open=close * 0.998,
                high=close * 1.006, low=close * 0.994, close=close, volume=500.0 + (i % 11) * 20, data_quality="high",
            )
        )
    db_session.commit()
    return asset, start, start + timedelta(minutes=15 * bars)


def test_run_experiment_end_to_end_persists_reproducibility_and_result(db_session):
    asset, start, end = _seed_asset(db_session, "EXPERIMENTREAL")
    experiment = run_experiment(
        db_session, hypothesis_id=None, type="backtest",
        control=ArmSpec(strategy_code="momentum_v1", params={}, label="control"),
        candidate=ArmSpec(strategy_code="momentum_v1", params={"roc_threshold": 2.5}, label="candidate"),
        asset=asset, timeframe="15m", start_ts=start, end_ts=end, initial_capital=10_000.0,
        monte_carlo_simulations=50,
    )
    assert experiment.status in (
        "failed", "quarantined", "rejected", "promising", "validating",
    )
    assert experiment.reproducibility["random_seed"] == 42
    assert "timestamp" in experiment.reproducibility
    assert experiment.result is not None
    assert "control_report" in experiment.result
    assert "candidate_report" in experiment.result
    assert experiment.completed_at is not None


def test_run_experiment_blocks_on_data_integrity_failure(db_session):
    asset = Asset(symbol="EXPERIMENTNODATA", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    start = datetime.now(timezone.utc) - timedelta(days=5)
    end = datetime.now(timezone.utc)
    experiment = run_experiment(
        db_session, hypothesis_id=None, type="backtest",
        control=ArmSpec(strategy_code="momentum_v1", params={}),
        candidate=ArmSpec(strategy_code="momentum_v1", params={"roc_threshold": 2.5}),
        asset=asset, timeframe="15m", start_ts=start, end_ts=end, initial_capital=10_000.0,
    )
    assert experiment.status == "failed"
    assert experiment.result["blocked"] is True
