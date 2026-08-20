"""Loss Streak Detector — "PROMPT 8" §37-39.

Portfolio-wide, not per-strategy: packages/quant/learning/quarantine.py
already demotes an individual underperforming *strategy* out of signal
generation; this catches a run of losses across the WHOLE book, which no
single strategy's health score would ever see if the losses are spread
across several strategies that are each, on their own, still "healthy".

Anti-martingale (§40) is deliberately what this module does NOT do: there
is no code path anywhere in packages/risk/position_sizing.py that reads
past P&L, win rate, or a streak to scale a position's size *up*. A loss
streak here only ever reduces size (never blocks outright — the safety
belts already own a full trading halt at a worse drawdown level); a win
streak is never read by sizing at all. See
tests/test_risk_loss_streak.py::test_win_streak_never_increases_size for
the behavioral proof.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from packages.risk.config import LossStreakConfig
from packages.shared.models import Trade

# How far back to look before giving up on finding a break in the streak —
# well above any realistic threshold, just a sane bound on the query.
_LOOKBACK_LIMIT = 200


@dataclass(frozen=True)
class LossStreakResult:
    consecutive_losses: int
    triggered: bool
    size_multiplier: float  # 1.0 unless triggered


def current_consecutive_losses(db: Session) -> int:
    """Consecutive losing trades (outcome == 'loss'), working backward from
    the most recently closed trade across the whole portfolio (not scoped
    to one strategy/asset). A win or breakeven anywhere resets the streak
    to 0 — "one trade doesn't decide the pattern" applies to ending a bad
    streak just as much as to declaring one (same caution as e.g.
    packages/quant/learning/degradation.py's cooldown)."""
    recent = db.query(Trade).order_by(Trade.closed_at.desc()).limit(_LOOKBACK_LIMIT).all()
    streak = 0
    for trade in recent:
        if trade.outcome != "loss":
            break
        streak += 1
    return streak


def evaluate_loss_streak(db: Session, limits: LossStreakConfig) -> LossStreakResult:
    streak = current_consecutive_losses(db)
    triggered = streak >= limits.threshold
    multiplier = limits.size_multiplier_when_triggered if triggered else 1.0
    return LossStreakResult(consecutive_losses=streak, triggered=triggered, size_multiplier=multiplier)
