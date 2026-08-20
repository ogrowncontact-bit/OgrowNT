"""Drift Detection — "PROMPT 10" §34-37.

Five `drift_type` families (the exact `DriftDetection.drift_type` CHECK
vocabulary: feature/market/strategy/agent/data), each a thin, honest
wrapper over evidence this codebase already computes — no new time-series
store is introduced per signal:

- **strategy**: delegates directly to
  `packages.research.degradation.check_change_point` — Prompt 10's own
  change-point detector over a strategy's R-multiple sequence, already
  built for the Degradation Engine and reused verbatim here.
- **agent**: recent vs baseline prediction accuracy for one specialist
  agent, from `packages.agents.reliability`'s own settled
  `AgentPrediction` rows, via the same z-test.
- **market**: recent vs baseline realized volatility (mean absolute
  return) for an asset/timeframe.
- **feature**: recent vs baseline mean `Pattern.confidence` for a
  pattern_type — has this pattern's typical detected strength shifted?
  Distinct from, and complementary to, `packages.research.features`'
  outcome-based ablation research.
- **data**: wraps an already-computed `packages.data.quality.QualityReport`
  — never recomputes the data-quality assembly logic that already lives in
  `apps/worker/strategy_runner.py` / `packages/agents/context.py`.

Every function returns a `DriftResult`; persisting one as a
`DriftDetection` row (`record_drift`) is the caller's job, so a caller can
decide whether a given check's result is even worth writing.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.data.quality import QualityReport
from packages.research import degradation
from packages.research.significance import ChangePointResult, detect_change_point
from packages.shared.models import OHLCV, AgentPrediction, DriftDetection, Pattern

DRIFT_TYPE_FEATURE = "feature"
DRIFT_TYPE_MARKET = "market"
DRIFT_TYPE_STRATEGY = "strategy"
DRIFT_TYPE_AGENT = "agent"
DRIFT_TYPE_DATA = "data"
DRIFT_TYPES = (DRIFT_TYPE_FEATURE, DRIFT_TYPE_MARKET, DRIFT_TYPE_STRATEGY, DRIFT_TYPE_AGENT, DRIFT_TYPE_DATA)

SEVERITY_NONE = "none"
SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"

DEFAULT_RECENT_WINDOW_DAYS = 7.0
DEFAULT_BASELINE_WINDOW_DAYS = 30.0
HIGH_SEVERITY_Z_SCORE = 2.5


@dataclass(frozen=True)
class DriftResult:
    drift_type: str
    entity: str
    detected: bool
    severity: str
    detail: dict


def _severity_from_change_point(change_point: ChangePointResult) -> str:
    if not change_point.detected:
        return SEVERITY_NONE
    return SEVERITY_HIGH if abs(change_point.z_score or 0.0) >= HIGH_SEVERITY_Z_SCORE else SEVERITY_MEDIUM


def _change_point_detail(change_point: ChangePointResult) -> dict:
    return {
        "z_score": change_point.z_score, "recent_mean": change_point.recent_mean, "baseline_mean": change_point.baseline_mean,
        "recent_n": change_point.recent_n, "baseline_n": change_point.baseline_n, "reason": change_point.reason,
    }


def detect_strategy_drift(db: Session, *, strategy_id: int, entity: str) -> DriftResult:
    change_point = degradation.check_change_point(db, strategy_id)
    return DriftResult(
        drift_type=DRIFT_TYPE_STRATEGY, entity=entity, detected=change_point.detected,
        severity=_severity_from_change_point(change_point), detail=_change_point_detail(change_point),
    )


def detect_agent_drift(
    db: Session, *, agent_code: str, now: datetime | None = None,
    recent_window_days: float = DEFAULT_RECENT_WINDOW_DAYS, baseline_window_days: float = DEFAULT_BASELINE_WINDOW_DAYS,
) -> DriftResult:
    """Recent vs baseline settled-prediction accuracy for one specialist
    agent (1.0 = correct, 0.0 = incorrect per prediction)."""
    now = now or datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=recent_window_days)
    baseline_cutoff = now - timedelta(days=recent_window_days + baseline_window_days)

    settled = db.execute(
        select(AgentPrediction.outcome, AgentPrediction.evaluated_at)
        .where(AgentPrediction.agent_code == agent_code, AgentPrediction.outcome != "pending", AgentPrediction.evaluated_at >= baseline_cutoff)
        .order_by(AgentPrediction.evaluated_at)
    ).all()

    recent = [1.0 if outcome == "correct" else 0.0 for outcome, evaluated_at in settled if evaluated_at is not None and evaluated_at >= recent_cutoff]
    baseline = [1.0 if outcome == "correct" else 0.0 for outcome, evaluated_at in settled if evaluated_at is not None and evaluated_at < recent_cutoff]

    change_point = detect_change_point(recent, baseline)
    return DriftResult(
        drift_type=DRIFT_TYPE_AGENT, entity=agent_code, detected=change_point.detected,
        severity=_severity_from_change_point(change_point), detail=_change_point_detail(change_point),
    )


def detect_market_drift(
    db: Session, *, asset_id: int, timeframe: str, now: datetime | None = None,
    recent_window_days: float = DEFAULT_RECENT_WINDOW_DAYS, baseline_window_days: float = DEFAULT_BASELINE_WINDOW_DAYS,
) -> DriftResult:
    """Recent vs baseline realized volatility, proxied by mean absolute
    bar-to-bar return -- `detect_change_point` compares means, so absolute
    return (not raw return, which is directionless around zero) is the
    volatility-shift signal this reuses it for."""
    now = now or datetime.now(timezone.utc)
    baseline_cutoff = now - timedelta(days=recent_window_days + baseline_window_days)
    recent_cutoff = now - timedelta(days=recent_window_days)

    closes = db.execute(
        select(OHLCV.ts, OHLCV.close)
        .where(OHLCV.asset_id == asset_id, OHLCV.timeframe == timeframe, OHLCV.ts >= baseline_cutoff)
        .order_by(OHLCV.ts)
    ).all()

    abs_returns_recent: list[float] = []
    abs_returns_baseline: list[float] = []
    for i in range(1, len(closes)):
        prev_ts, prev_close = closes[i - 1]
        ts, close = closes[i]
        if prev_close in (None, 0) or close is None:
            continue
        abs_return = abs((close - prev_close) / prev_close)
        (abs_returns_recent if ts >= recent_cutoff else abs_returns_baseline).append(abs_return)

    change_point = detect_change_point(abs_returns_recent, abs_returns_baseline)
    entity = f"asset:{asset_id}:{timeframe}"
    return DriftResult(
        drift_type=DRIFT_TYPE_MARKET, entity=entity, detected=change_point.detected,
        severity=_severity_from_change_point(change_point), detail=_change_point_detail(change_point),
    )


def detect_feature_drift(
    db: Session, *, pattern_type: str, now: datetime | None = None,
    recent_window_days: float = DEFAULT_RECENT_WINDOW_DAYS, baseline_window_days: float = DEFAULT_BASELINE_WINDOW_DAYS,
) -> DriftResult:
    """Recent vs baseline mean `Pattern.confidence` for a pattern_type --
    a shift here means the pattern detector itself is seeing a different
    quality of setup lately, independent of whether trades based on it
    have won or lost (that's `packages.research.features`' job)."""
    now = now or datetime.now(timezone.utc)
    baseline_cutoff = now - timedelta(days=recent_window_days + baseline_window_days)
    recent_cutoff = now - timedelta(days=recent_window_days)

    rows = db.execute(
        select(Pattern.ts, Pattern.confidence).where(Pattern.pattern_type == pattern_type, Pattern.ts >= baseline_cutoff)
    ).all()
    recent = [confidence for ts, confidence in rows if ts >= recent_cutoff and confidence is not None]
    baseline = [confidence for ts, confidence in rows if ts < recent_cutoff and confidence is not None]

    change_point = detect_change_point(recent, baseline)
    return DriftResult(
        drift_type=DRIFT_TYPE_FEATURE, entity=pattern_type, detected=change_point.detected,
        severity=_severity_from_change_point(change_point), detail=_change_point_detail(change_point),
    )


def detect_data_drift(quality_report: QualityReport, *, entity: str) -> DriftResult:
    severity = {"GOOD": SEVERITY_NONE, "DEGRADED": SEVERITY_MEDIUM, "DATA_UNSAFE": SEVERITY_HIGH}.get(quality_report.status, SEVERITY_LOW)
    return DriftResult(
        drift_type=DRIFT_TYPE_DATA, entity=entity, detected=quality_report.status != "GOOD", severity=severity,
        detail={"status": quality_report.status, "quality_score": quality_report.quality_score, "components": quality_report.components},
    )


def record_drift(db: Session, result: DriftResult, *, now: datetime | None = None) -> DriftDetection | None:
    """Persists a `DriftDetection` row only when something was actually
    detected -- an honest, non-noisy audit trail rather than one row per
    check regardless of outcome."""
    if not result.detected:
        return None
    row = DriftDetection(
        ts=now or datetime.now(timezone.utc), drift_type=result.drift_type, entity=result.entity,
        detail=result.detail, severity=result.severity,
    )
    db.add(row)
    db.commit()
    return row
