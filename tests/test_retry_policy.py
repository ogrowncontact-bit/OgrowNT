"""packages/execution/retry.py -- "PROMPT 13" §53-54."""
from __future__ import annotations

import pytest

from packages.execution.retry import is_retryable, retry_with_backoff


def test_read_operations_are_retryable():
    assert is_retryable("health_check") is True
    assert is_retryable("get_positions") is True


def test_order_mutations_are_never_retryable():
    assert is_retryable("create_order") is False
    assert is_retryable("submit_order") is False
    assert is_retryable("cancel_order") is False
    assert is_retryable("replace_order") is False


def test_retry_with_backoff_succeeds_on_first_attempt():
    calls = []

    def fn():
        calls.append(1)
        return "ok"

    result = retry_with_backoff("get_order", fn, sleep=lambda _: None)
    assert result == "ok"
    assert len(calls) == 1


def test_retry_with_backoff_retries_then_succeeds():
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("transient")
        return "recovered"

    result = retry_with_backoff("get_order", fn, max_attempts=5, sleep=lambda _: None)
    assert result == "recovered"
    assert attempts["n"] == 3


def test_retry_with_backoff_raises_after_exhausting_attempts():
    def always_fails():
        raise RuntimeError("permanent failure")

    with pytest.raises(RuntimeError, match="permanent failure"):
        retry_with_backoff("get_order", always_fails, max_attempts=3, sleep=lambda _: None)


def test_retry_with_backoff_refuses_a_non_idempotent_operation():
    with pytest.raises(ValueError, match="not a safe/idempotent operation"):
        retry_with_backoff("submit_order", lambda: "should never run", sleep=lambda _: None)
