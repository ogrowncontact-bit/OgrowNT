"""Pairs Research -- "PROMPT 11" §36-38.

Experimental only -- spread/z-score/cointegration-style research for
already-correlated asset pairs (reusing
packages/risk/correlation_guard.py's persisted correlation matrix, never
recomputing correlation itself). §38's constraint is verbatim-important:
"Mas: não executar arbitragem real." Nothing in this module ever creates
an order, a Signal, or anything else packages/execution or packages/risk
would act on -- its only output is a `PairSignal` dataclass for a human,
the dashboard, or a later research cycle to look at.

The "cointegration" check here is a lightweight, honestly-labeled proxy
(lag-1 autocorrelation of the spread series), NOT a real Engle-Granger/ADF
statistical test -- this codebase has no statistics library beyond plain
Python (packages/research/significance.py's own from-scratch z-test lives
under the same constraint), and a from-scratch ADF implementation is out
of scope for an experimental, non-executing research feature. Treat
`looks_mean_reverting` as a coarse heuristic, not a rigorous cointegration
verdict -- the field name and every docstring here say so on purpose.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from packages.risk.config import load_risk_limits
from packages.shared.market_data import get_recent_candles
from packages.shared.models import Asset, CorrelationMatrixEntry

_DISCLAIMER = "Experimental research only -- not an execution signal. No arbitrage is ever placed from this output."

# A spread deviation smaller than this z-score isn't worth reporting --
# keeps scan_correlated_universe from flooding the caller with noise.
_NOTABLE_ZSCORE = 2.0

_MIN_SAMPLE = 20


def hedge_ratio(closes_a: list[float], closes_b: list[float]) -> float | None:
    """OLS slope of A on B (A ~= beta * B), computed from scratch -- the
    standard pairs-trading hedge ratio, no numpy/statsmodels dependency.
    """
    n = min(len(closes_a), len(closes_b))
    if n < _MIN_SAMPLE:
        return None
    a, b = closes_a[-n:], closes_b[-n:]
    mean_a, mean_b = sum(a) / n, sum(b) / n
    cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    var_b = sum((x - mean_b) ** 2 for x in b)
    if var_b == 0:
        return None
    return cov / var_b


def compute_spread_series(closes_a: list[float], closes_b: list[float], beta: float) -> list[float]:
    n = min(len(closes_a), len(closes_b))
    a, b = closes_a[-n:], closes_b[-n:]
    return [a[i] - beta * b[i] for i in range(n)]


def zscore_of_latest(series: list[float]) -> float | None:
    if len(series) < _MIN_SAMPLE:
        return None
    latest, history = series[-1], series[:-1]
    mean = sum(history) / len(history)
    variance = sum((x - mean) ** 2 for x in history) / len(history)
    std = variance**0.5
    if std == 0:
        return None
    return (latest - mean) / std


def lag1_autocorrelation(series: list[float]) -> float | None:
    """Close to +1 looks like a persistent, non-stationary (non-mean-
    reverting) series; well below that looks more like noise oscillating
    around a stable mean. See module docstring: this is a coarse proxy,
    not a real cointegration test.
    """
    n = len(series)
    if n < _MIN_SAMPLE:
        return None
    mean = sum(series) / n
    numerator = sum((series[i] - mean) * (series[i - 1] - mean) for i in range(1, n))
    denominator = sum((x - mean) ** 2 for x in series)
    if denominator == 0:
        return None
    return numerator / denominator

# Below this lag-1 autocorrelation, a spread is called "looks mean-reverting".
_MEAN_REVERSION_AUTOCORR_THRESHOLD = 0.7


@dataclass(frozen=True)
class PairSignal:
    symbol_a: str
    symbol_b: str
    hedge_ratio: float
    zscore: float
    looks_mean_reverting: bool
    autocorrelation: float
    sample_size: int
    disclaimer: str = _DISCLAIMER


def analyze_pair(
    db: Session, asset_a_id: int, symbol_a: str, asset_b_id: int, symbol_b: str, *, timeframe: str = "1m",
    lookback: int = 150,
) -> PairSignal | None:
    candles_a = get_recent_candles(db, asset_a_id, timeframe, lookback)
    candles_b = get_recent_candles(db, asset_b_id, timeframe, lookback)
    closes_a = [c.close for c in candles_a]
    closes_b = [c.close for c in candles_b]

    beta = hedge_ratio(closes_a, closes_b)
    if beta is None:
        return None
    spread = compute_spread_series(closes_a, closes_b, beta)
    z = zscore_of_latest(spread)
    autocorr = lag1_autocorrelation(spread)
    if z is None or autocorr is None or abs(z) < _NOTABLE_ZSCORE:
        return None

    return PairSignal(
        symbol_a=symbol_a, symbol_b=symbol_b, hedge_ratio=round(beta, 6), zscore=round(z, 4),
        looks_mean_reverting=autocorr < _MEAN_REVERSION_AUTOCORR_THRESHOLD, autocorrelation=round(autocorr, 4),
        sample_size=min(len(closes_a), len(closes_b)),
    )


def scan_correlated_universe(
    db: Session, asset_ids: list[int], *, timeframe: str = "1m", correlation_threshold: float | None = None,
) -> list[PairSignal]:
    """Reads the already-persisted correlation matrix (never recomputes
    it) and runs `analyze_pair` on every pair among `asset_ids` that's
    already known to be strongly correlated -- the same "read, don't
    recompute" discipline as packages/market/clustering.py.
    """
    if len(asset_ids) < 2:
        return []
    threshold = (
        correlation_threshold if correlation_threshold is not None
        else load_risk_limits().portfolio.correlation_threshold
    )
    rows = (
        db.query(CorrelationMatrixEntry)
        .filter(CorrelationMatrixEntry.asset_id_a.in_(asset_ids), CorrelationMatrixEntry.asset_id_b.in_(asset_ids))
        .order_by(CorrelationMatrixEntry.ts.desc())
        .all()
    )
    seen_pairs: set[tuple[int, int]] = set()
    signals: list[PairSignal] = []
    for row in rows:
        key = (min(row.asset_id_a, row.asset_id_b), max(row.asset_id_a, row.asset_id_b))
        if key in seen_pairs or abs(row.correlation) < threshold:
            continue
        seen_pairs.add(key)  # first row per pair is the most recent, thanks to the ORDER BY

        asset_a = db.get(Asset, row.asset_id_a)
        asset_b = db.get(Asset, row.asset_id_b)
        if asset_a is None or asset_b is None:
            continue
        signal = analyze_pair(db, asset_a.id, asset_a.symbol, asset_b.id, asset_b.symbol, timeframe=timeframe)
        if signal is not None:
            signals.append(signal)
    return signals
