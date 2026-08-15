"""Correlation Guard — docs/blueprint/08-risk-engine.md#correlation-guard.

Prevents several "different" positions from being, in practice, one
concentrated bet (e.g. BTC long + NASDAQ long + EUR/USD long all being a
single risk-on bet). Correlation is computed from recent close-to-close
returns — real numbers from real (mock, in Phase 2/3) OHLCV, never assumed.

Simplification: bars are aligned positionally (last N closes per asset,
newest-last) rather than by matching exact timestamps. Fine as long as all
assets are scanned within the same cycle (they are — see apps/worker), so
their bars fall on the same real-world minutes; a real market data provider
with per-exchange gaps would need proper timestamp alignment.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.risk.config import RiskLimits
from packages.shared.models import OHLCV, Asset, CorrelationMatrixEntry, Position

DEFAULT_WINDOW_BARS = 30
MIN_BARS_FOR_CORRELATION = 10


def _recent_closes(db: Session, asset_id: int, timeframe: str, window: int) -> list[float]:
    rows = (
        db.query(OHLCV.close)
        .filter(OHLCV.asset_id == asset_id, OHLCV.timeframe == timeframe)
        .order_by(OHLCV.ts.desc())
        .limit(window)
        .all()
    )
    return [r[0] for r in reversed(rows)]


def _returns(closes: list[float]) -> list[float]:
    return [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes)) if closes[i - 1] != 0]


def _pearson(a: list[float], b: list[float]) -> float | None:
    n = min(len(a), len(b))
    if n < MIN_BARS_FOR_CORRELATION:
        return None
    a, b = a[-n:], b[-n:]
    mean_a, mean_b = sum(a) / n, sum(b) / n
    cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((x - mean_b) ** 2 for x in b)
    denom = math.sqrt(var_a * var_b)
    if denom == 0:
        return None
    return cov / denom


def compute_correlation(
    db: Session, asset_id_a: int, asset_id_b: int, timeframe: str = "1m", window: int = DEFAULT_WINDOW_BARS
) -> float | None:
    closes_a = _recent_closes(db, asset_id_a, timeframe, window)
    closes_b = _recent_closes(db, asset_id_b, timeframe, window)
    return _pearson(_returns(closes_a), _returns(closes_b))


@dataclass(frozen=True)
class CorrelationGuardResult:
    blocked: bool
    cluster_exposure_pct: float
    reason: str | None
    correlated_positions: list[dict] = field(default_factory=list)


def check_correlation_guard(
    db: Session,
    candidate_asset_id: int,
    candidate_notional_pct: float,
    open_positions: list[Position],
    equity: float,
    limits: RiskLimits,
    timeframe: str = "1m",
) -> CorrelationGuardResult:
    correlated_exposure_pct = 0.0
    correlated_positions: list[dict] = []

    for position in open_positions:
        if position.asset_id == candidate_asset_id or equity <= 0:
            continue
        corr = compute_correlation(db, candidate_asset_id, position.asset_id, timeframe)
        if corr is None or abs(corr) < limits.portfolio.correlation_threshold:
            continue
        position_exposure_pct = (position.entry_price * position.size / equity) * 100
        correlated_exposure_pct += position_exposure_pct
        correlated_positions.append(
            {"position_id": position.id, "asset_id": position.asset_id, "correlation": round(corr, 4), "exposure_pct": round(position_exposure_pct, 4)}
        )

    total_pct = correlated_exposure_pct + candidate_notional_pct
    blocked = total_pct > limits.portfolio.max_correlated_cluster_pct
    return CorrelationGuardResult(
        blocked=blocked,
        cluster_exposure_pct=round(total_pct, 4),
        reason="correlated_cluster_exceeded" if blocked else None,
        correlated_positions=correlated_positions,
    )


def refresh_correlation_matrix(db: Session, timeframe: str = "1m", window: int = DEFAULT_WINDOW_BARS) -> int:
    """Recompute and persist pairwise correlations for the active asset
    universe. Cheap at Phase 3 scale (~20 assets => ~190 pairs); used for
    the dashboard/audit trail, not on the hot path of a single risk check
    (check_correlation_guard computes fresh for exactly the pairs it needs).
    """
    assets = db.query(Asset).filter(Asset.is_active.is_(True)).all()
    closes_by_asset = {a.id: _returns(_recent_closes(db, a.id, timeframe, window)) for a in assets}
    ts = datetime.now(timezone.utc)
    written = 0

    for i, asset_a in enumerate(assets):
        for asset_b in assets[i + 1 :]:
            corr = _pearson(closes_by_asset[asset_a.id], closes_by_asset[asset_b.id])
            if corr is None:
                continue
            db.add(
                CorrelationMatrixEntry(
                    ts=ts, asset_id_a=asset_a.id, asset_id_b=asset_b.id, window_days=window, correlation=round(corr, 4)
                )
            )
            written += 1

    db.commit()
    return written
