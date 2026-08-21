"""Loss Streak Detector — "PROMPT 8" §37-39, extended by "PROMPT 12" §22-ish
with strategy/asset/regime dimensions and a Win Streak Guard.

Portfolio-wide, not per-strategy: packages/quant/learning/quarantine.py
already demotes an individual underperforming *strategy* out of signal
generation; this catches a run of losses across the WHOLE book, which no
single strategy's health score would ever see if the losses are spread
across several strategies that are each, on their own, still "healthy".
The new dimensional checks below add strategy/asset/regime-scoped streaks
on top of that portfolio-wide one (not instead of it) — engine.py's
sovereign per-signal gate keeps calling evaluate_loss_streak() exactly as
before; the dimensional version is additional context for
AdvancedRiskEngine (packages/risk/advanced_engine.py).

Anti-martingale (§40) is deliberately what this module does NOT do: there
is no code path anywhere in packages/risk/position_sizing.py that reads
past P&L, win rate, or a streak to scale a position's size *up*. A loss
streak here only ever reduces size (never blocks outright — the safety
belts already own a full trading halt at a worse drawdown level); a win
streak is never read by sizing at all — see WinStreakObservation below and
tests/test_risk_loss_streak.py::test_win_streak_never_increases_size for
the behavioral proof.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from packages.risk.config import LossStreakConfig
from packages.shared.models import MarketRegime, Position, Signal, Trade

# How far back to look before giving up on finding a break in the streak —
# well above any realistic threshold, just a sane bound on the query.
_LOOKBACK_LIMIT = 200


@dataclass(frozen=True)
class LossStreakResult:
    consecutive_losses: int
    triggered: bool
    size_multiplier: float  # 1.0 unless triggered


def _consecutive_losses_from(trades_desc: Iterable[Trade]) -> int:
    """`trades_desc` must already be ordered most-recent-first. A win or
    breakeven anywhere resets the streak to 0 — "one trade doesn't decide
    the pattern" applies to ending a bad streak just as much as to
    declaring one (same caution as e.g.
    packages/quant/learning/degradation.py's cooldown)."""
    streak = 0
    for trade in trades_desc:
        if trade.outcome != "loss":
            break
        streak += 1
    return streak


def current_consecutive_losses(db: Session) -> int:
    """Consecutive losing trades, working backward from the most recently
    closed trade across the whole portfolio (not scoped to one
    strategy/asset)."""
    recent = db.query(Trade).order_by(Trade.closed_at.desc()).limit(_LOOKBACK_LIMIT).all()
    return _consecutive_losses_from(recent)


def evaluate_loss_streak(db: Session, limits: LossStreakConfig) -> LossStreakResult:
    streak = current_consecutive_losses(db)
    triggered = streak >= limits.threshold
    multiplier = limits.size_multiplier_when_triggered if triggered else 1.0
    return LossStreakResult(consecutive_losses=streak, triggered=triggered, size_multiplier=multiplier)


def _result_for(streak: int, limits: LossStreakConfig) -> LossStreakResult:
    triggered = streak >= limits.threshold
    return LossStreakResult(
        consecutive_losses=streak, triggered=triggered,
        size_multiplier=limits.size_multiplier_when_triggered if triggered else 1.0,
    )


def strategy_consecutive_losses(db: Session, strategy_id: int) -> int:
    recent = (
        db.query(Trade)
        .join(Position, Trade.position_id == Position.id)
        .filter(Position.strategy_id == strategy_id)
        .order_by(Trade.closed_at.desc())
        .limit(_LOOKBACK_LIMIT)
        .all()
    )
    return _consecutive_losses_from(recent)


def asset_consecutive_losses(db: Session, asset_id: int) -> int:
    recent = (
        db.query(Trade)
        .join(Position, Trade.position_id == Position.id)
        .filter(Position.asset_id == asset_id)
        .order_by(Trade.closed_at.desc())
        .limit(_LOOKBACK_LIMIT)
        .all()
    )
    return _consecutive_losses_from(recent)


def regime_consecutive_losses(db: Session, regime: str) -> int:
    """Scoped to trades whose signal was scored under the given market
    regime (Position -> Signal -> MarketRegime, same join chain
    packages/quant/learning/strategy_stats.py's per-trade regime lookup
    already uses). A position opened without a signal, or a signal with no
    regime recorded, simply doesn't count toward any regime's streak —
    honest exclusion, not a fabricated regime label.
    """
    recent = (
        db.query(Trade)
        .join(Position, Trade.position_id == Position.id)
        .join(Signal, Position.signal_id == Signal.id)
        .join(MarketRegime, Signal.regime_id == MarketRegime.id)
        .filter(MarketRegime.regime == regime)
        .order_by(Trade.closed_at.desc())
        .limit(_LOOKBACK_LIMIT)
        .all()
    )
    return _consecutive_losses_from(recent)


@dataclass(frozen=True)
class DimensionalLossStreakResult:
    """Each non-portfolio dimension is None when the caller didn't ask for
    it (no strategy_id/asset_id/regime given) — no hallucinated "not
    triggered" result for a dimension nobody evaluated."""

    portfolio: LossStreakResult
    strategy: LossStreakResult | None
    asset: LossStreakResult | None
    regime: LossStreakResult | None

    @property
    def combined_size_multiplier(self) -> float:
        """The most conservative (lowest) multiplier across every dimension
        that was actually evaluated — a dimensional streak can only ever
        match or tighten the portfolio-wide multiplier, never loosen it."""
        multipliers = [self.portfolio.size_multiplier]
        for dim in (self.strategy, self.asset, self.regime):
            if dim is not None:
                multipliers.append(dim.size_multiplier)
        return min(multipliers)


def evaluate_dimensional_loss_streaks(
    db: Session,
    limits: LossStreakConfig,
    *,
    strategy_id: int | None = None,
    asset_id: int | None = None,
    regime: str | None = None,
) -> DimensionalLossStreakResult:
    """"PROMPT 12"'s strategy/asset/regime loss-streak dimensions, layered
    on top of (not replacing) evaluate_loss_streak's portfolio-wide check.
    Every dimension reuses the SAME threshold/multiplier
    (config/risk_limits.yaml's single loss_streak section) rather than a
    separate configurable block per dimension — the spec doesn't ask for
    independently-tunable per-dimension thresholds, and one number kept
    consistent across all of them is simpler to reason about and audit
    than four.
    """
    portfolio = evaluate_loss_streak(db, limits)
    strategy = _result_for(strategy_consecutive_losses(db, strategy_id), limits) if strategy_id is not None else None
    asset = _result_for(asset_consecutive_losses(db, asset_id), limits) if asset_id is not None else None
    regime_result = _result_for(regime_consecutive_losses(db, regime), limits) if regime is not None else None
    return DimensionalLossStreakResult(portfolio=portfolio, strategy=strategy, asset=asset, regime=regime_result)


@dataclass(frozen=True)
class WinStreakObservation:
    """"PROMPT 12"'s explicit prohibition: "Uma sequência de vitórias NÃO
    deve automaticamente aumentar risco." This exists ONLY to make a win
    streak observable (RiskAssessment/dashboard reporting) — by
    construction there is no size_multiplier field here, and nothing in
    packages/risk/position_sizing.py reads this. See
    tests/test_risk_loss_streak.py::test_win_streak_observation_has_no_
    sizing_effect for the structural proof.
    """

    consecutive_wins: int


def current_consecutive_wins(db: Session) -> int:
    recent = db.query(Trade).order_by(Trade.closed_at.desc()).limit(_LOOKBACK_LIMIT).all()
    streak = 0
    for trade in recent:
        if trade.outcome != "win":
            break
        streak += 1
    return streak


def observe_win_streak(db: Session) -> WinStreakObservation:
    return WinStreakObservation(consecutive_wins=current_consecutive_wins(db))
