"""Research Budget — "PROMPT 10" §56-60.

A resource_type-scoped, rolling-period spending cap so the Autonomous
Research Agent can never silently consume unbounded compute — the same
"bounded search" discipline `packages/research/generator.py`'s
`MAX_SEARCH_EVALUATIONS` already enforces for a single genetic-search
call, applied here across an entire rolling window's worth of
experiments/backtests/LLM calls/API calls. Multiple-testing correction —
the other half of "PROMPT 10"'s budget discipline, so a large batch of
experiments doesn't accept more false positives just because more were
tried — is `packages.research.significance.benjamini_hochberg`, built
earlier in this phase; nothing here duplicates it.

`spend()` checks the cap BEFORE recording usage and raises
`BudgetExceededError` rather than letting the caller go over — callers
(the research worker, `ExperimentEngine` wiring) are expected to call it
before actually running the experiment/backtest/LLM call, not after, so
the cap is enforced rather than merely observed.

Limits live in `config/research_budget.yaml`, loaded fresh on every call —
the same editable-config-file pattern as `packages/risk/config.py`'s
`load_risk_limits` (`config/risk_limits.yaml`), so an operator can raise a
cap without a code change or restart.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.shared.models import ResearchBudgetUsage

RESOURCE_EXPERIMENT = "experiment"
RESOURCE_BACKTEST = "backtest"
RESOURCE_LLM_CALL = "llm_call"
RESOURCE_API_CALL = "api_call"
RESOURCE_TYPES = (RESOURCE_EXPERIMENT, RESOURCE_BACKTEST, RESOURCE_LLM_CALL, RESOURCE_API_CALL)

DEFAULT_PERIOD_HOURS = 24.0
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "research_budget.yaml"


class BudgetExceededError(RuntimeError):
    pass


def load_budget_limits(path: Path = CONFIG_PATH) -> dict[str, float]:
    raw = yaml.safe_load(path.read_text())
    limits = raw["limits"]
    missing = [rt for rt in RESOURCE_TYPES if rt not in limits]
    if missing:
        raise ValueError(f"{path} is missing limits for resource_type(s): {missing}")
    return {rt: float(limits[rt]) for rt in RESOURCE_TYPES}


@dataclass(frozen=True)
class BudgetStatus:
    resource_type: str
    period_hours: float
    used: float
    limit: float
    remaining: float
    exhausted: bool


def _validate_resource_type(resource_type: str) -> None:
    if resource_type not in RESOURCE_TYPES:
        raise ValueError(f"unknown resource_type: {resource_type!r} (expected one of {RESOURCE_TYPES})")


def usage_in_period(db: Session, *, resource_type: str, period_hours: float = DEFAULT_PERIOD_HOURS, now: datetime | None = None) -> float:
    _validate_resource_type(resource_type)
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=period_hours)
    total = db.execute(
        select(func.coalesce(func.sum(ResearchBudgetUsage.amount), 0.0)).where(
            ResearchBudgetUsage.resource_type == resource_type, ResearchBudgetUsage.ts >= cutoff
        )
    ).scalar_one()
    return float(total)


def check_budget(
    db: Session, *, resource_type: str, limit: float | None = None, period_hours: float = DEFAULT_PERIOD_HOURS,
    now: datetime | None = None,
) -> BudgetStatus:
    _validate_resource_type(resource_type)
    effective_limit = limit if limit is not None else load_budget_limits()[resource_type]
    used = usage_in_period(db, resource_type=resource_type, period_hours=period_hours, now=now)
    remaining = max(0.0, effective_limit - used)
    return BudgetStatus(
        resource_type=resource_type, period_hours=period_hours, used=used, limit=effective_limit,
        remaining=remaining, exhausted=used >= effective_limit,
    )


def record_usage(
    db: Session, *, resource_type: str, amount: float = 1.0, experiment_id: int | None = None, now: datetime | None = None,
) -> ResearchBudgetUsage:
    _validate_resource_type(resource_type)
    row = ResearchBudgetUsage(ts=now or datetime.now(timezone.utc), resource_type=resource_type, amount=amount, experiment_id=experiment_id)
    db.add(row)
    db.commit()
    return row


def spend(
    db: Session, *, resource_type: str, amount: float = 1.0, limit: float | None = None,
    period_hours: float = DEFAULT_PERIOD_HOURS, experiment_id: int | None = None, now: datetime | None = None,
) -> ResearchBudgetUsage:
    status = check_budget(db, resource_type=resource_type, limit=limit, period_hours=period_hours, now=now)
    if status.used + amount > status.limit:
        raise BudgetExceededError(
            f"{resource_type} budget exhausted: {status.used}/{status.limit} already used in the last {period_hours}h window "
            f"(this call would add {amount})"
        )
    return record_usage(db, resource_type=resource_type, amount=amount, experiment_id=experiment_id, now=now)
