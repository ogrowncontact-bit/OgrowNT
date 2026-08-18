"""Debounced alerting for market-surveillance conditions (Prompt 2 §17:
data feed disconnected, stale data, unusual movement, volatility spike,
high-severity market events) -- apps/worker/supervisor.py's
CadenceFailureTracker precedent, applied to a different set of conditions.

In-memory, one instance per worker process: resets on restart, which is
correct here too -- a fresh process shouldn't immediately re-fire an alert
for a condition it hasn't actually re-observed yet.
"""
from __future__ import annotations

import time

from sqlalchemy.orm import Session

from packages.shared.models import Alert

# A feed outage or a run of stale candles is worth one alert, not one every
# scan cycle until it clears -- same reasoning as Supervisor's
# CONSECUTIVE_FAILURE_ALERT_THRESHOLD, just time-based instead of count-based
# since these conditions don't have a natural "cycle count" to threshold on.
DEFAULT_COOLDOWN_SECONDS = 900


class MarketAlertTracker:
    def __init__(self, cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS) -> None:
        self._cooldown = cooldown_seconds
        self._last_alert_at: dict[str, float] = {}

    def maybe_alert(
        self, db: Session, *, key: str, severity: str, message: str, meta: dict | None = None
    ) -> bool:
        """Raises a category='market' Alert unless the same key already
        alerted within the cooldown window. Returns whether it actually
        alerted (tests assert on this instead of querying the DB)."""
        now = time.monotonic()
        last = self._last_alert_at.get(key)
        if last is not None and now - last < self._cooldown:
            return False

        self._last_alert_at[key] = now
        db.add(Alert(severity=severity, category="market", message=message, meta=meta or {}))
        db.commit()
        return True

    def clear(self, key: str) -> None:
        """Called once a condition is confirmed resolved (e.g. the feed is
        connected again) so the next recurrence alerts immediately instead
        of waiting out a cooldown that no longer reflects reality."""
        self._last_alert_at.pop(key, None)
