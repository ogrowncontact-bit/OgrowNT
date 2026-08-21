"""packages/execution/rate_limit.py -- "PROMPT 13" §51-52."""
from __future__ import annotations

from packages.execution.rate_limit import RateLimitManager


def test_unconfigured_pair_always_allows():
    manager = RateLimitManager()
    assert manager.try_acquire(broker="paper", category="orders") is True
    assert manager.headroom(broker="paper", category="orders") is None


def test_configured_bucket_is_consumed_by_acquisitions():
    manager = RateLimitManager()
    manager.configure(broker="paper", category="orders", capacity=2, refill_per_second=0.0)
    assert manager.try_acquire(broker="paper", category="orders") is True
    assert manager.try_acquire(broker="paper", category="orders") is True
    assert manager.try_acquire(broker="paper", category="orders") is False  # exhausted


def test_headroom_reflects_remaining_fraction():
    manager = RateLimitManager()
    manager.configure(broker="paper", category="orders", capacity=4, refill_per_second=0.0)
    manager.try_acquire(broker="paper", category="orders")
    assert manager.headroom(broker="paper", category="orders") == 0.75


def test_categories_have_independent_budgets():
    manager = RateLimitManager()
    manager.configure(broker="paper", category="orders", capacity=1, refill_per_second=0.0)
    manager.configure(broker="paper", category="market_data", capacity=1, refill_per_second=0.0)
    assert manager.try_acquire(broker="paper", category="orders") is True
    assert manager.try_acquire(broker="paper", category="orders") is False
    assert manager.try_acquire(broker="paper", category="market_data") is True  # untouched budget


def test_acquiring_more_than_available_cost_fails_without_partial_consumption():
    manager = RateLimitManager()
    manager.configure(broker="paper", category="orders", capacity=5, refill_per_second=0.0)
    assert manager.try_acquire(broker="paper", category="orders", cost=10) is False
    assert manager.headroom(broker="paper", category="orders") == 1.0  # nothing was consumed
