"""Research Budget — "PROMPT 10" §56-60."""
from __future__ import annotations

import pytest

from packages.research import budget


def test_load_budget_limits_covers_every_resource_type():
    limits = budget.load_budget_limits()
    assert set(limits.keys()) == set(budget.RESOURCE_TYPES)
    assert all(v > 0 for v in limits.values())


def test_unknown_resource_type_rejected(db_session):
    with pytest.raises(ValueError):
        budget.check_budget(db_session, resource_type="not_a_real_resource")
    with pytest.raises(ValueError):
        budget.record_usage(db_session, resource_type="not_a_real_resource")


def test_usage_starts_at_zero(db_session):
    status = budget.check_budget(db_session, resource_type=budget.RESOURCE_EXPERIMENT, limit=10)
    assert status.used == 0.0
    assert status.remaining == 10.0
    assert status.exhausted is False


def test_spend_accumulates_and_reflects_in_check_budget(db_session):
    budget.spend(db_session, resource_type=budget.RESOURCE_BACKTEST, amount=3.0, limit=10)
    budget.spend(db_session, resource_type=budget.RESOURCE_BACKTEST, amount=4.0, limit=10)
    status = budget.check_budget(db_session, resource_type=budget.RESOURCE_BACKTEST, limit=10)
    assert status.used == 7.0
    assert status.remaining == 3.0


def test_spend_raises_before_exceeding_the_cap(db_session):
    budget.spend(db_session, resource_type=budget.RESOURCE_EXPERIMENT, amount=5.0, limit=5)
    with pytest.raises(budget.BudgetExceededError):
        budget.spend(db_session, resource_type=budget.RESOURCE_EXPERIMENT, amount=0.01, limit=5)


def test_exact_limit_is_allowed_one_unit_over_is_not(db_session):
    row = budget.spend(db_session, resource_type=budget.RESOURCE_LLM_CALL, amount=5.0, limit=5.0)
    assert row.amount == 5.0
    status = budget.check_budget(db_session, resource_type=budget.RESOURCE_LLM_CALL, limit=5.0)
    assert status.exhausted is True
    with pytest.raises(budget.BudgetExceededError):
        budget.spend(db_session, resource_type=budget.RESOURCE_LLM_CALL, amount=1.0, limit=5.0)


def test_usage_outside_the_rolling_period_does_not_count(db_session):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    old = now - timedelta(hours=48)
    budget.record_usage(db_session, resource_type=budget.RESOURCE_API_CALL, amount=100.0, now=old)
    status = budget.check_budget(db_session, resource_type=budget.RESOURCE_API_CALL, limit=10, period_hours=24, now=now)
    assert status.used == 0.0


def test_spend_failure_does_not_record_usage(db_session):
    budget.spend(db_session, resource_type=budget.RESOURCE_EXPERIMENT, amount=10.0, limit=10)
    try:
        budget.spend(db_session, resource_type=budget.RESOURCE_EXPERIMENT, amount=1.0, limit=10)
    except budget.BudgetExceededError:
        pass
    status = budget.check_budget(db_session, resource_type=budget.RESOURCE_EXPERIMENT, limit=10)
    assert status.used == 10.0  # the failed attempt never got recorded
