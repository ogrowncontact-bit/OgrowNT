"""Historical Analog Engine -- "PROMPT 11" §62-63.

A thin wrapper around packages/quant/learning/memory.py's structured
similarity search (Phase 5 Market Memory) -- this module adds only the
presentation layer the prompt asks for (sample_size, outcome distribution,
worst-case realized P&L, and a sample-size-aware quality label). It does
not reimplement the similarity search itself.

Realized P&L comes from `Position.realized_pnl` via each matched memory
row's `signal_id` (Position.signal_id) -- a real, closed-trade number,
never a fabricated distribution. MarketMemory itself stores only the
categorical `outcome` (win/loss/breakeven), not a P&L figure, so any
analog with a null/never-opened signal_id contributes to the outcome
count but not to the P&L sample.

§63's explicit constraint: "Não dizer: 'will happen again.'" -- every
result carries a fixed disclaimer; nothing here is ever phrased as a
prediction.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from packages.quant.learning.memory import find_similar_contexts, similar_context_win_rate
from packages.shared.models import Position

# Below this many analogs, the read is honestly too thin to lean on --
# "PROMPT 11" §63's "quality degrades with smaller sample or lower
# similarity" rule, expressed as an explicit label rather than a silently
# unqualified number.
MIN_ADEQUATE_SAMPLE = 5

QUALITY_LOW_SAMPLE = "low_sample"
QUALITY_ADEQUATE = "adequate"

_DISCLAIMER = (
    "Historical resemblance is not a guarantee of a repeat outcome -- "
    "treat this as context, not a prediction."
)

_OUTCOME_LABELS = ("win", "loss", "breakeven")


def _realized_pnls_for(db: Session, signal_ids: list[int]) -> list[float]:
    if not signal_ids:
        return []
    rows = (
        db.query(Position.realized_pnl)
        .filter(Position.signal_id.in_(signal_ids), Position.realized_pnl.isnot(None))
        .all()
    )
    return [r[0] for r in rows]


@dataclass(frozen=True)
class HistoricalAnalogResult:
    sample_size: int
    win_rate: float | None
    outcome_counts: dict[str, int] = field(default_factory=dict)
    realized_pnl_samples: list[float] = field(default_factory=list)
    worst_pnl: float | None = None
    quality: str = QUALITY_LOW_SAMPLE
    disclaimer: str = _DISCLAIMER


class HistoricalAnalogEngine:
    def find_analogs(
        self, db: Session, *, regime: str | None, pattern_type: str | None, direction: str | None,
        k: int = 10, exclude_signal_id: int | None = None,
    ) -> HistoricalAnalogResult:
        rows = find_similar_contexts(
            db, regime=regime, pattern_type=pattern_type, direction=direction, k=k,
            exclude_signal_id=exclude_signal_id,
        )
        win_rate = similar_context_win_rate(rows)

        outcome_counts = {label: 0 for label in _OUTCOME_LABELS}
        for row in rows:
            if row.outcome in outcome_counts:
                outcome_counts[row.outcome] += 1

        signal_ids = [row.signal_id for row in rows if row.signal_id is not None]
        pnls = _realized_pnls_for(db, signal_ids)

        return HistoricalAnalogResult(
            sample_size=len(rows), win_rate=win_rate, outcome_counts=outcome_counts,
            realized_pnl_samples=pnls, worst_pnl=min(pnls) if pnls else None,
            quality=QUALITY_ADEQUATE if len(rows) >= MIN_ADEQUATE_SAMPLE else QUALITY_LOW_SAMPLE,
        )
