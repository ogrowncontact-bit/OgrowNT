"""Train / Validation / Test time split — "PROMPT 7" §17. A pure date-range
splitter: TRAIN gets the earliest slice, then VALIDATION, then TEST gets the
most recent slice (chronological order, never shuffled — shuffling calendar
time across a split would itself be a look-ahead leak). Ratios must sum to
1.0; the caller (packages/backtest/walkforward_optimization.py,
apps/api/routers/backtests.py) is responsible for never touching the TEST
range's data while optimizing, per §17's "Não permitir que o sistema
utilize TEST durante otimização" — this module only computes the boundaries,
it doesn't gate access to them (there is no separate query-time enforcement
mechanism to bypass here: the caller simply never passes the TEST range's
start/end into run_backtest/optimize_parameters until final evaluation).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

DEFAULT_TRAIN_RATIO = 0.6
DEFAULT_VALIDATION_RATIO = 0.2
DEFAULT_TEST_RATIO = 0.2


@dataclass(frozen=True)
class TrainValidationTestSplit:
    train_start: datetime
    train_end: datetime
    validation_start: datetime
    validation_end: datetime
    test_start: datetime
    test_end: datetime
    train_ratio: float
    validation_ratio: float
    test_ratio: float


def split_train_validation_test(
    start_ts: datetime, end_ts: datetime, *,
    train_ratio: float = DEFAULT_TRAIN_RATIO, validation_ratio: float = DEFAULT_VALIDATION_RATIO,
    test_ratio: float = DEFAULT_TEST_RATIO,
) -> TrainValidationTestSplit:
    if end_ts <= start_ts:
        raise ValueError("end_ts must be after start_ts")
    total = train_ratio + validation_ratio + test_ratio
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"train/validation/test ratios must sum to 1.0, got {total}")
    if min(train_ratio, validation_ratio, test_ratio) < 0:
        raise ValueError("ratios must be non-negative")

    total_seconds = (end_ts - start_ts).total_seconds()
    train_end = start_ts + timedelta(seconds=total_seconds * train_ratio)
    validation_end = train_end + timedelta(seconds=total_seconds * validation_ratio)

    return TrainValidationTestSplit(
        train_start=start_ts, train_end=train_end,
        validation_start=train_end, validation_end=validation_end,
        test_start=validation_end, test_end=end_ts,
        train_ratio=train_ratio, validation_ratio=validation_ratio, test_ratio=test_ratio,
    )
