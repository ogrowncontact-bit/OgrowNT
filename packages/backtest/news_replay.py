"""News-aware backtest replay — "PROMPT 7" §34 ("reproduzir NEWS -> SENTIMENT
-> EVENT RISK -> STRATEGY DECISION... Nunca permitir que o backtest use
notícias publicadas posteriormente") and §6 (data leakage protection for
news specifically).

Mirrors apps/worker/strategy_runner.py's `_recent_news_signals` exactly,
with one addition that IS the whole point of this module: `as_of` replaces
`datetime.now()`. The live worker's "now" and a backtest bar's timestamp are
different clocks, and using the wall-clock one here would leak every
NewsImpact row created after the backtest started straight into bars from
before it — the textbook look-ahead bug this module exists to prevent.

Honest limitation, stated in packages/backtest/engine.py's own module
docstring and unchanged by this module: `news_events`/`news_impact` only
started accumulating real rows once the News Intelligence worker
(docs/news-intelligence.md) went live. A backtest window that predates that
will correctly find zero news rows and fall back to the same neutral
"no read available" default packages/quant/scoring/inputs.py already uses —
not a bug, an honest reflection of what data actually exists.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from packages.quant.regime.classifier import NewsSignal
from packages.shared.models import NewsImpact

NEWS_LOOKBACK_HOURS = 48  # same widest horizon as apps/worker/strategy_runner.py, filtered tighter per-row below


def news_signals_as_of(db: Session, asset_id: int, as_of: datetime, lookback_hours: float = NEWS_LOOKBACK_HOURS) -> list[NewsSignal]:
    """Every NewsSignal a live worker could honestly have seen at `as_of` --
    never a row whose `created_at` is after it."""
    cutoff = as_of - timedelta(hours=lookback_hours)
    rows = (
        db.query(NewsImpact)
        .filter(NewsImpact.asset_id == asset_id, NewsImpact.created_at >= cutoff, NewsImpact.created_at <= as_of)
        .all()
    )
    return [
        NewsSignal(direction=r.direction, impact=r.impact, confidence=r.confidence)
        for r in rows
        if as_of - r.created_at <= timedelta(hours=r.horizon_hours)
    ]
