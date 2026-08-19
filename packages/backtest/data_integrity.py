"""Data integrity pre-check — "PROMPT 7" §52-53. Runs before a backtest is
allowed to execute; a critical finding returns `blocked=True`
(`BACKTEST_BLOCKED`, matching §52's exact wording) so a corrupted or
malformed dataset never silently produces a confident-looking result.

Duplicate candles (§52's own list includes them) are intentionally *not*
checked here: `ohlcv`'s primary key is `(asset_id, timeframe, ts)`
(packages/shared/models.py), so a duplicate row is a database-level
impossibility, not something this function could ever observe — checking
for it would be dead code pretending to guard against something the schema
already rules out.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.shared.models import OHLCV

# Expected spacing between consecutive bars, in seconds -- same set ohlcv's
# own CHECK constraint allows.
TIMEFRAME_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1D": 86400, "1W": 604800}

# A gap is only flagged once it's a meaningful multiple of the expected bar
# spacing -- ordinary provider jitter of a few seconds isn't a data problem.
GAP_TOLERANCE_MULTIPLE = 2.0


@dataclass(frozen=True)
class DataIntegrityIssue:
    severity: str  # 'critical' | 'warning'
    code: str
    detail: str


@dataclass(frozen=True)
class DataIntegrityReport:
    blocked: bool
    bars_checked: int
    issues: list[DataIntegrityIssue] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "BACKTEST_BLOCKED" if self.blocked else ("ISSUES_FOUND" if self.issues else "OK")


def check_data_integrity(db: Session, asset_id: int, timeframe: str, start_ts: datetime, end_ts: datetime) -> DataIntegrityReport:
    rows = (
        db.query(OHLCV)
        .filter(OHLCV.asset_id == asset_id, OHLCV.timeframe == timeframe, OHLCV.ts >= start_ts, OHLCV.ts < end_ts)
        .order_by(OHLCV.ts.asc())
        .all()
    )

    issues: list[DataIntegrityIssue] = []
    now = datetime.now(timezone.utc)

    if not rows:
        issues.append(DataIntegrityIssue("critical", "no_data", f"no OHLCV rows for asset_id={asset_id} timeframe={timeframe} in the requested window"))
        return DataIntegrityReport(blocked=True, bars_checked=0, issues=issues)

    expected_interval = TIMEFRAME_SECONDS.get(timeframe)
    gap_count = 0
    for row in rows:
        if row.ts.tzinfo is None:
            issues.append(DataIntegrityIssue("critical", "timezone_naive", f"candle at {row.ts} has no timezone info"))
        elif row.ts > now:
            issues.append(DataIntegrityIssue("critical", "future_data", f"candle at {row.ts.isoformat()} is in the future"))

        if row.high < row.low:
            issues.append(DataIntegrityIssue("critical", "bad_ohlc_high_low", f"high {row.high} < low {row.low} at {row.ts.isoformat()}"))
        if row.high < row.open or row.high < row.close:
            issues.append(DataIntegrityIssue("critical", "bad_ohlc_high", f"high {row.high} below open/close at {row.ts.isoformat()}"))
        if row.low > row.open or row.low > row.close:
            issues.append(DataIntegrityIssue("critical", "bad_ohlc_low", f"low {row.low} above open/close at {row.ts.isoformat()}"))
        if row.open <= 0 or row.close <= 0 or row.high <= 0 or row.low <= 0:
            issues.append(DataIntegrityIssue("critical", "bad_ohlc_price", f"non-positive price at {row.ts.isoformat()}"))
        if row.volume < 0:
            issues.append(DataIntegrityIssue("critical", "bad_ohlc_volume", f"negative volume at {row.ts.isoformat()}"))

    if expected_interval:
        for prev, curr in zip(rows, rows[1:], strict=False):
            delta = (curr.ts - prev.ts).total_seconds()
            if delta > expected_interval * GAP_TOLERANCE_MULTIPLE:
                gap_count += 1
        if gap_count:
            issues.append(
                DataIntegrityIssue(
                    "warning", "timestamp_gaps",
                    f"{gap_count} gap(s) larger than {GAP_TOLERANCE_MULTIPLE}x the expected {timeframe} interval",
                )
            )
    else:
        issues.append(DataIntegrityIssue("warning", "unknown_timeframe_interval", f"no known bar-interval for timeframe {timeframe!r}; gap check skipped"))

    degraded = [r for r in rows if r.data_quality != "high"]
    if degraded:
        issues.append(DataIntegrityIssue("warning", "degraded_quality_bars", f"{len(degraded)}/{len(rows)} bars have data_quality != 'high'"))

    blocked = any(issue.severity == "critical" for issue in issues)
    return DataIntegrityReport(blocked=blocked, bars_checked=len(rows), issues=issues)
