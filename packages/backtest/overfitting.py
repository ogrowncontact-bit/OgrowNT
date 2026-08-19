"""Overfitting classification — "PROMPT 7" §21. A pure label over a
(train, test) performance pair. Spec's own worked examples:

    train +80%, test -3%   -> SEVERE_OVERFITTING
    train +25%, test +19%  -> MORE_ROBUST

"Não classificar somente por lucro": the classifier looks at the *gap*
between train and test, not test's absolute sign alone — a strategy that's
flat-to-slightly-negative in both windows is DEGRADED_OR_FLAT, not
"overfitting" (nothing to overfit to if train wasn't profitable either).
"""
from __future__ import annotations

from dataclasses import dataclass

SEVERE_OVERFITTING = "SEVERE_OVERFITTING"
MODERATE_OVERFITTING = "MODERATE_OVERFITTING"
MORE_ROBUST = "MORE_ROBUST"
DEGRADED_OR_FLAT = "DEGRADED_OR_FLAT"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

# Train-vs-test degradation thresholds, as a fraction of train's return.
# e.g. train=+80%, test=-3%: degradation = (0.80 - (-0.03)) / 0.80 = 1.0375 -> severe.
SEVERE_DEGRADATION_RATIO = 0.75
MODERATE_DEGRADATION_RATIO = 0.35


@dataclass(frozen=True)
class OverfittingVerdict:
    label: str
    train_return: float | None
    test_return: float | None
    degradation_ratio: float | None
    reason: str


def classify_overfitting(train_return: float | None, test_return: float | None) -> OverfittingVerdict:
    if train_return is None or test_return is None:
        return OverfittingVerdict(
            INSUFFICIENT_EVIDENCE, train_return, test_return, None,
            "missing train or test return -- cannot judge overfitting",
        )

    if train_return <= 0:
        return OverfittingVerdict(
            DEGRADED_OR_FLAT, train_return, test_return, None,
            f"train return {train_return:.4f} was not positive -- nothing profitable for the strategy to have overfit to",
        )

    degradation_ratio = (train_return - test_return) / train_return

    if test_return <= 0 and degradation_ratio >= SEVERE_DEGRADATION_RATIO:
        label = SEVERE_OVERFITTING
    elif degradation_ratio >= MODERATE_DEGRADATION_RATIO:
        label = MODERATE_OVERFITTING
    else:
        label = MORE_ROBUST

    reason = f"train={train_return:.4f}, test={test_return:.4f}, degradation_ratio={degradation_ratio:.4f}"
    return OverfittingVerdict(label, train_return, test_return, round(degradation_ratio, 4), reason)
