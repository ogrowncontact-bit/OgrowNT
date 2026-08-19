from datetime import datetime, timedelta, timezone

import pytest

from packages.backtest.split import split_train_validation_test


def test_default_60_20_20_split():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=100)
    split = split_train_validation_test(start, end)

    assert split.train_start == start
    assert split.test_end == end
    assert (split.train_end - split.train_start).days == 60
    assert (split.validation_end - split.validation_start).days == 20
    assert (split.test_end - split.test_start).days == 20
    assert split.validation_start == split.train_end
    assert split.test_start == split.validation_end


def test_ratios_must_sum_to_one():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=100)
    with pytest.raises(ValueError, match="sum to 1.0"):
        split_train_validation_test(start, end, train_ratio=0.5, validation_ratio=0.3, test_ratio=0.3)


def test_negative_ratio_rejected():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=100)
    with pytest.raises(ValueError, match="non-negative"):
        split_train_validation_test(start, end, train_ratio=1.1, validation_ratio=-0.1, test_ratio=0.0)


def test_end_before_start_rejected():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="after start_ts"):
        split_train_validation_test(start, start - timedelta(days=1))
