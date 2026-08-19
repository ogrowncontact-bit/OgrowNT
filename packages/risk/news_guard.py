"""News Risk Guard — Prompt 6 §17/§26.

Consults upcoming MacroEvent rows (pre-event risk) and recent
high/critical-importance NewsEvent rows (post-event/breaking risk) to
produce a NORMAL/ELEVATED/HIGH/CRITICAL verdict. This is the News
Intelligence layer's *only* path to influencing a trade: the verdict below
feeds packages/risk/engine.py as one more check step, exactly like
packages/risk/strategy_health.py's StrategyHealthVerdict — it can only
reduce the approved size or block outright, never approve, size, or submit
an order itself. Prompt 6 §2/§43's absolute rule ("NEWS NUNCA deve
diretamente BUY/SELL/EXECUTE") holds structurally: nothing in this module
touches packages/execution.

Deliberately global/portfolio-wide, not per-asset — mirrors
packages/risk/safety_belt.py's own global scope. A Fed decision or a
banking-system shock is a market-wide risk-off event, not one this system
should try to argue is irrelevant to a specific instrument.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from packages.quant.news.impact_score import load_event_window_minutes
from packages.risk.config import RiskLimits
from packages.shared.models import MacroEvent, NewsEvent

NORMAL = "normal"
ELEVATED = "elevated"
HIGH = "high"
CRITICAL = "critical"

# How much further out than the tight pre-event window (config/news_weights.yaml)
# an upcoming high-importance macro event still counts as ELEVATED rather
# than NORMAL — a softer, earlier warning before the harder HIGH cutoff.
ELEVATED_WINDOW_MULTIPLIER = 3


@dataclass(frozen=True)
class NewsRiskVerdict:
    level: str
    size_multiplier: float
    blocked: bool
    reasons: list[str]


def evaluate_news_risk(db: Session, limits: RiskLimits, *, now: datetime | None = None) -> NewsRiskVerdict:
    now = now or datetime.now(timezone.utc)
    pre_window_min, post_window_min = load_event_window_minutes()

    pre_cutoff = now + timedelta(minutes=pre_window_min)
    elevated_cutoff = now + timedelta(minutes=pre_window_min * ELEVATED_WINDOW_MULTIPLIER)
    post_cutoff = now - timedelta(minutes=post_window_min)

    upcoming = (
        db.query(MacroEvent)
        .filter(MacroEvent.scheduled_at > now, MacroEvent.scheduled_at <= elevated_cutoff)
        .filter(MacroEvent.importance.in_(("high", "critical")))
        .all()
    )
    recent_news = (
        db.query(NewsEvent)
        .filter(NewsEvent.published_at >= post_cutoff, NewsEvent.importance.in_(("high", "critical")))
        .all()
    )

    reasons: list[str] = []

    critical_macro_near = [m for m in upcoming if m.importance == "critical" and m.scheduled_at <= pre_cutoff]
    critical_news_recent = [n for n in recent_news if n.importance == "critical"]
    if critical_macro_near or critical_news_recent:
        for macro_event in critical_macro_near:
            reasons.append(f"macro_event_imminent:{macro_event.event}")
        for news_event in critical_news_recent:
            reasons.append(f"critical_news_recent:{news_event.headline[:60]}")
        return _verdict(CRITICAL, limits, reasons)

    high_macro_near = [m for m in upcoming if m.importance == "high" and m.scheduled_at <= pre_cutoff]
    high_news_recent = [n for n in recent_news if n.importance == "high"]
    if high_macro_near or high_news_recent:
        for macro_event in high_macro_near:
            reasons.append(f"macro_event_imminent:{macro_event.event}")
        for news_event in high_news_recent:
            reasons.append(f"high_impact_news_recent:{news_event.headline[:60]}")
        return _verdict(HIGH, limits, reasons)

    if upcoming:  # high-importance, but only within the wider elevated window
        for macro_event in upcoming:
            reasons.append(f"macro_event_upcoming:{macro_event.event}")
        return _verdict(ELEVATED, limits, reasons)

    return _verdict(NORMAL, limits, reasons)


def _verdict(level: str, limits: RiskLimits, reasons: list[str]) -> NewsRiskVerdict:
    multiplier = getattr(limits.news_risk_multipliers, level)
    return NewsRiskVerdict(level=level, size_multiplier=multiplier, blocked=level == CRITICAL, reasons=reasons)
