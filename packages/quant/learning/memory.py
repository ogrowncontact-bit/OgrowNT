"""Market Memory — docs/blueprint/06-memory-system.md: "have I seen a
market context like this before, and what happened?"

The blueprint calls for a pgvector `embedding` column with cosine-distance
search; this deployment doesn't have the pgvector extension available (see
packages/shared/models.py's MarketMemory docstring for how that was
verified), so this does structured similarity instead — match on regime,
pattern_type and direction, the fields actually captured at signal time
(apps/worker/strategy_runner.py), ranked by how many of those match plus
recency. Not a replacement for real semantic search over arbitrary context,
just an honest, deterministic stand-in that works with what's actually
stored.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from packages.shared.models import MarketMemory

# Bounded scan window — a plain ORDER BY ts DESC LIMIT scan, not an
# index-backed nearest-neighbor search. Fine at this data volume; revisit
# once market_memory has enough rows for this to matter.
_SCAN_WINDOW = 500


def find_similar_contexts(
    db: Session, *, regime: str | None, pattern_type: str | None, direction: str | None,
    k: int = 10, exclude_signal_id: int | None = None,
) -> list[MarketMemory]:
    rows = (
        db.query(MarketMemory)
        .filter(MarketMemory.outcome.isnot(None))
        .order_by(MarketMemory.ts.desc())
        .limit(_SCAN_WINDOW)
        .all()
    )
    if exclude_signal_id is not None:
        rows = [r for r in rows if r.signal_id != exclude_signal_id]

    def _match_score(row: MarketMemory) -> int:
        ctx = row.context or {}
        score = 0
        if regime is not None and ctx.get("regime") == regime:
            score += 1
        if pattern_type is not None and ctx.get("pattern_type") == pattern_type:
            score += 1
        if direction is not None and ctx.get("direction") == direction:
            score += 1
        return score

    scored = [(row, _match_score(row)) for row in rows]
    scored = [pair for pair in scored if pair[1] > 0]
    scored.sort(key=lambda pair: (pair[1], pair[0].ts), reverse=True)
    return [row for row, _ in scored[:k]]


def similar_context_win_rate(rows: list[MarketMemory]) -> float | None:
    resolved = [row for row in rows if row.outcome in ("win", "loss", "breakeven")]
    if not resolved:
        return None
    wins = sum(1 for row in resolved if row.outcome == "win")
    return round(wins / len(resolved), 4)
