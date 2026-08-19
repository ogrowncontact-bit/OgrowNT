from packages.backtest.overfitting import (
    DEGRADED_OR_FLAT,
    INSUFFICIENT_EVIDENCE,
    MORE_ROBUST,
    SEVERE_OVERFITTING,
    classify_overfitting,
)


def test_spec_worked_example_severe_overfitting():
    verdict = classify_overfitting(train_return=0.80, test_return=-0.03)
    assert verdict.label == SEVERE_OVERFITTING


def test_spec_worked_example_more_robust():
    verdict = classify_overfitting(train_return=0.25, test_return=0.19)
    assert verdict.label == MORE_ROBUST


def test_moderate_degradation_is_not_severe():
    verdict = classify_overfitting(train_return=0.30, test_return=0.10)
    assert verdict.label == "MODERATE_OVERFITTING"


def test_never_profitable_train_is_degraded_not_overfitting():
    verdict = classify_overfitting(train_return=-0.05, test_return=-0.10)
    assert verdict.label == DEGRADED_OR_FLAT


def test_missing_data_is_insufficient_evidence():
    verdict = classify_overfitting(train_return=None, test_return=0.1)
    assert verdict.label == INSUFFICIENT_EVIDENCE
    verdict2 = classify_overfitting(train_return=0.1, test_return=None)
    assert verdict2.label == INSUFFICIENT_EVIDENCE


def test_never_classified_by_profit_alone():
    # Two very different train/test pairs sharing the same (positive) test
    # sign must not collapse into the same verdict -- the spec's "não
    # classificar somente por lucro" rule.
    small_gap = classify_overfitting(train_return=0.20, test_return=0.18)
    big_gap = classify_overfitting(train_return=0.90, test_return=0.05)
    assert small_gap.label != big_gap.label
