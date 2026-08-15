"""Strategy Memory — docs/blueprint/06-memory-system.md. Recomputed by the
Learning Agent's DET half whenever a position closes
(docs/blueprint/04-agents-architecture.md#agent-13): a fresh rolling-window
read of trade history, not an incremental running average like Pattern
Memory (packages/quant/patterns/performance.py) — profit factor, Sharpe and
max drawdown all need the actual per-trade series, not just a running mean.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.shared.models import MarketRegime, Position, Signal, StrategyPerformance, Trade

WINDOW_TRADES = 200
# Below this many closed trades, win_rate/profit_factor/etc. are too noisy to
# turn into a single health score or feed an automatic action (Quarantine) —
# report them as real numbers, but leave health_score explicitly null rather
# than manufacture a confident-looking score from 2 trades.
MIN_TRADES_FOR_HEALTH_SCORE = 5

_HEALTH_WEIGHTS = {"expectancy": 0.40, "win_rate": 0.15, "profit_factor": 0.25, "drawdown": 0.20}


def _trade_regime(db: Session, trade: Trade) -> str | None:
    position = trade.position
    if position is None or position.signal_id is None:
        return None
    signal = db.get(Signal, position.signal_id)
    if signal is None or signal.regime_id is None:
        return None
    regime = db.get(MarketRegime, signal.regime_id)
    return regime.regime if regime else None


def _max_drawdown(trades_oldest_first: list[Trade]) -> float:
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades_oldest_first:
        cum += t.pnl
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
    return max_dd


def _sharpe(r_multiples: list[float]) -> float | None:
    if len(r_multiples) < 2:
        return None
    mean_r = sum(r_multiples) / len(r_multiples)
    variance = sum((r - mean_r) ** 2 for r in r_multiples) / (len(r_multiples) - 1)
    std = math.sqrt(variance)
    return round(mean_r / std, 4) if std > 0 else None


def _health_score(*, expectancy: float | None, win_rate: float, profit_factor: float | None, max_drawdown: float, gross_profit: float) -> float:
    """0-100, higher is healthier. Each factor is normalized independently
    then combined with fixed weights (config/scoring_weights.yaml precedent:
    centralized, documented weights rather than an opaque single number).
    A factor genuinely unavailable (e.g. no losing trades yet, so
    profit_factor is undefined) scores a neutral 50 for that factor only —
    same "no hallucinated data" convention as packages/quant/scoring/inputs.py.
    """
    expectancy_score = 50.0 if expectancy is None else max(0.0, min(100.0, 50.0 + expectancy * 25.0))
    win_rate_score = max(0.0, min(100.0, win_rate * 100.0))
    profit_factor_score = 50.0 if profit_factor is None else max(0.0, min(100.0, profit_factor * 50.0))
    drawdown_ratio = (max_drawdown / gross_profit) if gross_profit > 0 else (1.0 if max_drawdown > 0 else 0.0)
    drawdown_score = max(0.0, min(100.0, 100.0 - drawdown_ratio * 100.0))

    score = (
        _HEALTH_WEIGHTS["expectancy"] * expectancy_score
        + _HEALTH_WEIGHTS["win_rate"] * win_rate_score
        + _HEALTH_WEIGHTS["profit_factor"] * profit_factor_score
        + _HEALTH_WEIGHTS["drawdown"] * drawdown_score
    )
    return round(score, 2)


def compute_strategy_performance(db: Session, strategy_id: int) -> StrategyPerformance:
    trades = (
        db.query(Trade)
        .join(Position, Trade.position_id == Position.id)
        .filter(Position.strategy_id == strategy_id)
        .order_by(Trade.closed_at.desc())
        .limit(WINDOW_TRADES)
        .all()
    )
    total_trades = (
        db.query(Trade)
        .join(Position, Trade.position_id == Position.id)
        .filter(Position.strategy_id == strategy_id)
        .count()
    )

    perf = StrategyPerformance(
        strategy_id=strategy_id, as_of=datetime.now(timezone.utc),
        window_trades=len(trades), total_trades=total_trades,
    )
    if not trades:
        db.add(perf)
        db.commit()
        return perf

    wins = [t for t in trades if t.outcome == "win"]
    losses = [t for t in trades if t.outcome == "loss"]
    win_rate = len(wins) / len(trades)
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))
    avg_win = (gross_profit / len(wins)) if wins else None
    avg_loss = (gross_loss / len(losses)) if losses else None
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None
    r_multiples = [t.r_multiple for t in trades if t.r_multiple is not None]
    expectancy = (sum(r_multiples) / len(r_multiples)) if r_multiples else None
    max_dd = _max_drawdown(list(reversed(trades)))

    regime_r: dict[str, list[float]] = {}
    for t in trades:
        regime = _trade_regime(db, t)
        if regime is None or t.r_multiple is None:
            continue
        regime_r.setdefault(regime, []).append(t.r_multiple)
    regime_expectancy = {r: sum(vs) / len(vs) for r, vs in regime_r.items() if vs}
    best_regime = max(regime_expectancy, key=regime_expectancy.get) if regime_expectancy else None
    worst_regime = min(regime_expectancy, key=regime_expectancy.get) if regime_expectancy else None

    perf.win_rate = round(win_rate, 4)
    perf.profit_factor = round(profit_factor, 4) if profit_factor is not None else None
    perf.avg_win = round(avg_win, 4) if avg_win is not None else None
    perf.avg_loss = round(avg_loss, 4) if avg_loss is not None else None
    perf.sharpe = _sharpe(r_multiples)
    perf.max_drawdown = round(max_dd, 4)
    perf.expectancy = round(expectancy, 4) if expectancy is not None else None
    perf.best_regime = best_regime
    perf.worst_regime = worst_regime
    perf.health_score = (
        _health_score(expectancy=expectancy, win_rate=win_rate, profit_factor=profit_factor, max_drawdown=max_dd, gross_profit=gross_profit)
        if len(trades) >= MIN_TRADES_FOR_HEALTH_SCORE
        else None
    )

    db.add(perf)
    db.commit()
    return perf
