"""Dynamic Watchlist -- "PROMPT 11" §77-79.

One row per asset (packages/shared/models.py::WatchlistEntry, unique on
asset_id) -- re-triggering an already-active entry updates `reason`/
`updated_at` in place rather than inserting a duplicate row, so
`watchlist_entries` never accumulates one row per trigger event the way a
log table would.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from packages.shared.models import WatchlistEntry

# -- closed vocabulary -- matches ck_watchlist_entries_reason ------------
REASON_ANOMALY = "anomaly"
REASON_NEWS = "news"
REASON_VOLUME = "volume"
REASON_VOLATILITY = "volatility"
REASON_OPPORTUNITY = "opportunity"
REASON_MANUAL = "manual"

STATUS_ACTIVE = "active"
STATUS_REMOVED = "removed"

# -- closed vocabulary -- matches ck_watchlist_entries_removal_reason ----
REMOVAL_OPPORTUNITY_DISAPPEARED = "opportunity_disappeared"
REMOVAL_LIQUIDITY_DETERIORATION = "liquidity_deterioration"
REMOVAL_DATA_QUALITY_DETERIORATION = "data_quality_deterioration"
REMOVAL_MANUAL = "manual"

# How long an entry can go un-refreshed before decay_stale_entries treats
# whatever put it on the watchlist as presumed gone -- a passive time-based
# complement to the three explicit, event-driven removal reasons above.
DEFAULT_STALE_AFTER = timedelta(hours=24)


class DynamicWatchlist:
    def add_or_refresh(self, db: Session, asset_id: int, reason: str, *, now: datetime | None = None) -> WatchlistEntry:
        now = now or datetime.now(timezone.utc)
        entry = db.query(WatchlistEntry).filter(WatchlistEntry.asset_id == asset_id).one_or_none()
        if entry is None:
            entry = WatchlistEntry(asset_id=asset_id, reason=reason, status=STATUS_ACTIVE, added_at=now, updated_at=now)
            db.add(entry)
        else:
            entry.reason = reason
            entry.status = STATUS_ACTIVE
            entry.updated_at = now
            entry.removed_at = None
            entry.removal_reason = None
        db.commit()
        return entry

    def remove(self, db: Session, asset_id: int, removal_reason: str, *, now: datetime | None = None) -> WatchlistEntry | None:
        now = now or datetime.now(timezone.utc)
        entry = (
            db.query(WatchlistEntry)
            .filter(WatchlistEntry.asset_id == asset_id, WatchlistEntry.status == STATUS_ACTIVE)
            .one_or_none()
        )
        if entry is None:
            return None
        entry.status = STATUS_REMOVED
        entry.removed_at = now
        entry.removal_reason = removal_reason
        db.commit()
        return entry

    def active_entries(self, db: Session) -> list[WatchlistEntry]:
        return (
            db.query(WatchlistEntry)
            .filter(WatchlistEntry.status == STATUS_ACTIVE)
            .order_by(WatchlistEntry.updated_at.desc())
            .all()
        )

    def decay_stale_entries(
        self, db: Session, *, stale_after: timedelta = DEFAULT_STALE_AFTER, now: datetime | None = None,
    ) -> list[WatchlistEntry]:
        now = now or datetime.now(timezone.utc)
        cutoff = now - stale_after
        stale = (
            db.query(WatchlistEntry)
            .filter(WatchlistEntry.status == STATUS_ACTIVE, WatchlistEntry.updated_at < cutoff)
            .all()
        )
        for entry in stale:
            entry.status = STATUS_REMOVED
            entry.removed_at = now
            entry.removal_reason = REMOVAL_OPPORTUNITY_DISAPPEARED
        if stale:
            db.commit()
        return stale
