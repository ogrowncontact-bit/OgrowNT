from packages.backtest.failure_detector import STRATEGY_OK, STRATEGY_QUARANTINED, STRATEGY_REJECTED, detect_strategy_failure
from packages.backtest.quality_score import (
    ASSESSMENT_INSUFFICIENT_EVIDENCE,
    EXPERIMENTAL,
    REJECTED,
    ROBUST,
    compute_quality_score,
)
from packages.backtest.reality_gap import RealityGapResult
from packages.backtest.robustness import compute_robustness_score
from packages.backtest.walkforward_optimization import WalkForwardOptimizationResult


def test_robustness_score_zero_with_no_evidence_at_all():
    result = compute_robustness_score()
    assert result.score == 0.0
    assert len(result.insufficient_evidence) > 0


def test_robustness_score_rewards_low_drawdown_and_sample_size():
    good = compute_robustness_score(max_drawdown_pct=2.0, num_trades=40, asset_count=3)
    bad = compute_robustness_score(max_drawdown_pct=40.0, num_trades=2, asset_count=1)
    assert good.score > bad.score


def test_robustness_never_exceeds_100():
    wf = WalkForwardOptimizationResult(pooled_oos_expectancy=1.0, oos_positive_window_ratio=1.0, consistent=True, reason="great")
    result = compute_robustness_score(
        walk_forward=wf, max_drawdown_pct=0.0, num_trades=1000, regime_breakdown={r: {} for r in range(8)},
        asset_count=10, cost_sensitivity_survives=True, slippage_sensitivity_survives=True,
    )
    assert result.score <= 100.0


def test_quality_score_experimental_below_min_trades():
    from packages.backtest.robustness import RobustnessScoreResult

    robustness = RobustnessScoreResult(score=0.0, insufficient_evidence=["out_of_sample"])
    result = compute_quality_score(expectancy=0.5, num_trades=3, robustness=robustness)
    assert result.status == EXPERIMENTAL


def test_quality_score_rejected_on_negative_expectancy():
    from packages.backtest.robustness import RobustnessScoreResult

    robustness = RobustnessScoreResult(score=60.0, insufficient_evidence=[])
    result = compute_quality_score(expectancy=-0.2, num_trades=50, robustness=robustness)
    assert result.status == REJECTED


def test_quality_score_robust_with_strong_evidence():
    from packages.backtest.robustness import RobustnessScoreResult

    robustness = RobustnessScoreResult(score=90.0, insufficient_evidence=[])
    result = compute_quality_score(expectancy=0.6, num_trades=50, robustness=robustness)
    assert result.status == ROBUST
    assert result.final_assessment != ASSESSMENT_INSUFFICIENT_EVIDENCE


def test_quality_score_never_uses_forbidden_wording():
    from packages.backtest.quality_score import FINAL_ASSESSMENT_LABELS, STATUS_LABELS

    forbidden = ("guaranteed profit", "safe", "will make money")
    for label in (*STATUS_LABELS, *FINAL_ASSESSMENT_LABELS):
        for phrase in forbidden:
            assert phrase not in label.lower()


def test_override_status_lets_caller_set_degraded_or_quarantined():
    from packages.backtest.quality_score import DEGRADED
    from packages.backtest.robustness import RobustnessScoreResult

    robustness = RobustnessScoreResult(score=80.0, insufficient_evidence=[])
    result = compute_quality_score(expectancy=0.4, num_trades=50, robustness=robustness, override_status=DEGRADED)
    assert result.status == DEGRADED


def test_failure_detector_ok_with_no_red_flags():
    verdict = detect_strategy_failure(expectancy=0.4, max_drawdown_pct=5.0, max_drawdown_limit_pct=20.0)
    assert verdict.verdict == STRATEGY_OK


def test_failure_detector_rejects_negative_expectancy():
    verdict = detect_strategy_failure(expectancy=-0.1)
    assert verdict.verdict == STRATEGY_REJECTED
    assert any("expectancy" in r for r in verdict.reasons)


def test_failure_detector_rejects_excessive_drawdown():
    verdict = detect_strategy_failure(expectancy=0.2, max_drawdown_pct=50.0, max_drawdown_limit_pct=20.0)
    assert verdict.verdict == STRATEGY_REJECTED


def test_failure_detector_rejects_high_monte_carlo_ruin_probability():
    verdict = detect_strategy_failure(expectancy=0.2, monte_carlo_probability_of_loss=0.9)
    assert verdict.verdict == STRATEGY_REJECTED


def test_failure_detector_quarantines_on_reality_gap_degradation():
    gap = RealityGapResult(
        strategy_id=1, reference_backtest_id=1, return_difference=None, win_rate_difference=-0.1,
        expectancy_difference=-0.3, drawdown_difference=5.0, execution_difference=None, notes=[],
    )
    verdict = detect_strategy_failure(expectancy=0.4, reality_gap=gap)
    assert verdict.verdict == STRATEGY_QUARANTINED


def test_rejection_always_wins_over_quarantine():
    """A strategy that's both currently unprofitable AND degraded from a
    reference backtest is REJECTED (backtest-time evidence), not merely
    QUARANTINED (live-degradation evidence) -- rejection is the stronger claim."""
    gap = RealityGapResult(
        strategy_id=1, reference_backtest_id=1, return_difference=None, win_rate_difference=-0.1,
        expectancy_difference=-0.3, drawdown_difference=5.0, execution_difference=None, notes=[],
    )
    verdict = detect_strategy_failure(expectancy=-0.05, reality_gap=gap)
    assert verdict.verdict == STRATEGY_REJECTED
