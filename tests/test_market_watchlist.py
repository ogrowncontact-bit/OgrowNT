"""Dynamic Watchlist -- "PROMPT 11" §77-79."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.market.watchlist import (
    DEFAULT_STALE_AFTER,
    REASON_ANOMALY,
    REASON_NEWS,
    REASON_VOLUME,
    REMOVAL_LIQUIDITY_DETERIORATION,
    STATUS_ACTIVE,
    STATUS_REMOVED,
    DynamicWatchlist,
)
from packages.shared.models import Asset, WatchlistEntry

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto")
    db_session.add(asset)
    db_session.commit()
    return asset


def test_add_or_refresh_creates_a_new_entry(db_session):
    asset = _asset(db_session, "WL_NEW")
    entry = DynamicWatchlist().add_or_refresh(db_session, asset.id, REASON_ANOMALY, now=_NOW)
    assert entry.status == STATUS_ACTIVE
    assert entry.reason == REASON_ANOMALY
    assert entry.added_at == _NOW


def test_add_or_refresh_is_idempotent_per_asset(db_session):
    asset = _asset(db_session, "WL_IDEMPOTENT")
    watchlist = DynamicWatchlist()
    watchlist.add_or_refresh(db_session, asset.id, REASON_ANOMALY, now=_NOW)
    watchlist.add_or_refresh(db_session, asset.id, REASON_NEWS, now=_NOW + timedelta(hours=1))

    rows = db_session.query(WatchlistEntry).filter(WatchlistEntry.asset_id == asset.id).all()
    assert len(rows) == 1
    assert rows[0].reason == REASON_NEWS
    assert rows[0].updated_at == _NOW + timedelta(hours=1)


def test_add_or_refresh_reactivates_a_removed_entry(db_session):
    asset = _asset(db_session, "WL_REACTIVATE")
    watchlist = DynamicWatchlist()
    watchlist.add_or_refresh(db_session, asset.id, REASON_ANOMALY, now=_NOW)
    watchlist.remove(db_session, asset.id, REMOVAL_LIQUIDITY_DETERIORATION, now=_NOW + timedelta(hours=1))

    entry = watchlist.add_or_refresh(db_session, asset.id, REASON_VOLUME, now=_NOW + timedelta(hours=2))
    assert entry.status == STATUS_ACTIVE
    assert entry.removed_at is None
    assert entry.removal_reason is None
    assert entry.reason == REASON_VOLUME


def test_remove_marks_entry_removed_with_reason(db_session):
    asset = _asset(db_session, "WL_REMOVE")
    watchlist = DynamicWatchlist()
    watchlist.add_or_refresh(db_session, asset.id, REASON_ANOMALY, now=_NOW)
    entry = watchlist.remove(db_session, asset.id, REMOVAL_LIQUIDITY_DETERIORATION, now=_NOW + timedelta(hours=1))
    assert entry is not None
    assert entry.status == STATUS_REMOVED
    assert entry.removal_reason == REMOVAL_LIQUIDITY_DETERIORATION
    assert entry.removed_at == _NOW + timedelta(hours=1)


def test_remove_is_a_no_op_for_an_asset_never_watchlisted(db_session):
    asset = _asset(db_session, "WL_NEVER")
    assert DynamicWatchlist().remove(db_session, asset.id, REMOVAL_LIQUIDITY_DETERIORATION) is None


def test_active_entries_excludes_removed_rows(db_session):
    active = _asset(db_session, "WL_ACTIVE")
    removed = _asset(db_session, "WL_REMOVED")
    watchlist = DynamicWatchlist()
    watchlist.add_or_refresh(db_session, active.id, REASON_ANOMALY, now=_NOW)
    watchlist.add_or_refresh(db_session, removed.id, REASON_ANOMALY, now=_NOW)
    watchlist.remove(db_session, removed.id, REMOVAL_LIQUIDITY_DETERIORATION, now=_NOW)

    entries = watchlist.active_entries(db_session)
    asset_ids = {e.asset_id for e in entries}
    assert active.id in asset_ids
    assert removed.id not in asset_ids


def test_decay_stale_entries_removes_only_entries_past_the_ttl(db_session):
    fresh = _asset(db_session, "WL_FRESH")
    stale = _asset(db_session, "WL_STALE")
    watchlist = DynamicWatchlist()
    watchlist.add_or_refresh(db_session, fresh.id, REASON_ANOMALY, now=_NOW)
    watchlist.add_or_refresh(db_session, stale.id, REASON_ANOMALY, now=_NOW - DEFAULT_STALE_AFTER - timedelta(minutes=1))

    decayed = watchlist.decay_stale_entries(db_session, now=_NOW)
    decayed_ids = {e.asset_id for e in decayed}
    assert stale.id in decayed_ids
    assert fresh.id not in decayed_ids

    stale_row = db_session.query(WatchlistEntry).filter(WatchlistEntry.asset_id == stale.id).one()
    assert stale_row.status == STATUS_REMOVED
    fresh_row = db_session.query(WatchlistEntry).filter(WatchlistEntry.asset_id == fresh.id).one()
    assert fresh_row.status == STATUS_ACTIVE
