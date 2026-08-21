"""ClockService — "PROMPT 13" §55-56.

Architecture-ready, trivially satisfied by PaperBrokerAdapter (there is no
real second clock — the "broker" and this process share the same system
clock by construction), same honest-scoping note as rate_limit.py. Tested
against a synthetic drifted timestamp rather than a real broker's clock,
since none exists here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

DEFAULT_MAX_DRIFT_SECONDS = 5.0


@dataclass(frozen=True)
class ClockDriftResult:
    drift_seconds: float
    within_tolerance: bool
    reasons: list[str] = field(default_factory=list)


class ClockService:
    def check_drift(
        self, broker_time: datetime, *, now: datetime | None = None, max_drift_seconds: float = DEFAULT_MAX_DRIFT_SECONDS,
    ) -> ClockDriftResult:
        now = now or datetime.now(timezone.utc)
        if broker_time.tzinfo is None or now.tzinfo is None:
            raise ValueError("both broker_time and now must be timezone-aware (UTC discipline)")
        drift = abs((now - broker_time).total_seconds())
        within_tolerance = drift <= max_drift_seconds
        reasons = [] if within_tolerance else [f"clock drift {drift:.3f}s exceeds tolerance {max_drift_seconds}s"]
        return ClockDriftResult(drift_seconds=round(drift, 3), within_tolerance=within_tolerance, reasons=reasons)

    def validate_timestamp(
        self, ts: datetime, *, now: datetime | None = None, max_drift_seconds: float = DEFAULT_MAX_DRIFT_SECONDS,
    ) -> bool:
        """§56 — reject data/orders carrying a timestamp outside the
        acceptable window (either direction: a clock that's fast or slow is
        equally suspect)."""
        return self.check_drift(ts, now=now, max_drift_seconds=max_drift_seconds).within_tolerance
