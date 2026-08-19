"""MacroCalendarWorker cycle — Prompt 6 §15-17.

Ingests upcoming/recent macro calendar entries from
packages/data/connectors/macro, upserting on (event, country, scheduled_at)
so repeated fetches update forecast/actual in place instead of duplicating
rows. `surprise` is computed here (actual - forecast) the moment `actual`
first appears — never assumed or backfilled before the real event has
occurred (Prompt 6 §16).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from packages.data.connectors.macro.base import MacroCalendarProvider
from packages.quant.news.impact_score import load_event_window_minutes
from packages.shared.models import Alert, MacroEvent

logger = logging.getLogger("worker.macro_agent")

LOOKBACK_DAYS = 3
LOOKAHEAD_DAYS = 14


def _already_alerted(db: Session, marker: str, macro_event_id: int) -> bool:
    recent = db.query(Alert).filter(Alert.category == "news").all()
    return any(a.meta.get("marker") == marker and a.meta.get("macro_event_id") == macro_event_id for a in recent)


def _raise_macro_alerts(db: Session, macro_event: MacroEvent, *, just_resolved: bool) -> None:
    """Prompt 6 §17/§36: HIGH_IMPACT_EVENT once a high/critical event enters
    the pre-event window, MACRO_SURPRISE the moment one resolves."""
    if macro_event.importance in ("high", "critical"):
        pre_window_min, _ = load_event_window_minutes()
        now = datetime.now(timezone.utc)
        if now <= macro_event.scheduled_at <= now + timedelta(minutes=pre_window_min):
            if not _already_alerted(db, "high_impact_event", macro_event.id):
                db.add(
                    Alert(
                        severity="critical" if macro_event.importance == "critical" else "warning",
                        category="news",
                        message=f"High-impact macro event upcoming: {macro_event.event} ({macro_event.country})",
                        meta={"marker": "high_impact_event", "macro_event_id": macro_event.id, "event": macro_event.event},
                    )
                )

        if just_resolved and macro_event.surprise is not None:
            db.add(
                Alert(
                    severity="warning", category="news",
                    message=(
                        f"Macro surprise: {macro_event.event} ({macro_event.country}) actual="
                        f"{macro_event.actual} forecast={macro_event.forecast} surprise={macro_event.surprise:+g}"
                    ),
                    meta={
                        "marker": "macro_surprise", "macro_event_id": macro_event.id, "event": macro_event.event,
                        "surprise": macro_event.surprise,
                    },
                )
            )


def run_macro_calendar_cycle(db: Session, provider: MacroCalendarProvider) -> dict:
    now = datetime.now(timezone.utc)
    items = provider.get_events(now - timedelta(days=LOOKBACK_DAYS), now + timedelta(days=LOOKAHEAD_DAYS))

    created, updated, resolved = 0, 0, 0
    for item in items:
        existing = (
            db.query(MacroEvent)
            .filter(
                MacroEvent.event == item.event, MacroEvent.country == item.country,
                MacroEvent.scheduled_at == item.scheduled_at,
            )
            .first()
        )
        surprise = (item.actual - item.forecast) if (item.actual is not None and item.forecast is not None) else None
        status = "released" if item.actual is not None else "scheduled"

        if existing is None:
            macro_event = MacroEvent(
                event=item.event, country=item.country, currency=item.currency,
                scheduled_at=item.scheduled_at, importance=item.importance,
                forecast=item.forecast, previous=item.previous, actual=item.actual,
                surprise=surprise, status=status,
            )
            db.add(macro_event)
            db.flush()
            _raise_macro_alerts(db, macro_event, just_resolved=status == "released")
            created += 1
        else:
            just_resolved = existing.status == "scheduled" and status == "released"
            existing.forecast = item.forecast
            existing.previous = item.previous
            existing.actual = item.actual
            existing.surprise = surprise
            existing.status = status
            _raise_macro_alerts(db, existing, just_resolved=just_resolved)
            if just_resolved:
                resolved += 1
            else:
                updated += 1

    db.commit()
    summary = {"created": created, "updated": updated, "resolved": resolved}
    logger.info("Macro calendar cycle complete: %s", summary)
    return summary
