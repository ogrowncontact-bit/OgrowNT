"""Strategy Engine cycle — docs/blueprint/05-event-flow.md Decision Pipeline,
the slice up to (not including) the Risk Engine: regime -> strategies ->
scoring. Nothing here executes or approves anything (Phase 3).
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from apps.worker.risk_execution import maybe_execute
from packages.data.connectors.market.base import Candle
from packages.execution.adapters.base import ExecutionProvider
from packages.execution.adapters.paper import PaperExecutionProvider
from packages.quant.indicators.core import MIN_CANDLES_REQUIRED, compute_indicators
from packages.quant.regime.classifier import classify_regime
from packages.quant.scoring import build_scoring_inputs, compute_score
from packages.quant.strategies import ALL_STRATEGIES, MarketContext, Strategy
from packages.shared.models import OHLCV, Asset, MarketRegime, OpportunityScore, Signal, StrategyRow

logger = logging.getLogger("worker.strategy_runner")

TIMEFRAME = "1m"
HISTORY_LIMIT = 200


def _load_recent_candles(db: Session, asset_id: int, timeframe: str, limit: int) -> list[Candle]:
    rows = (
        db.query(OHLCV)
        .filter(OHLCV.asset_id == asset_id, OHLCV.timeframe == timeframe)
        .order_by(OHLCV.ts.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()  # rows arrived newest-first; strategies expect oldest-first
    return [
        Candle(ts=r.ts, open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume, data_quality=r.data_quality)
        for r in rows
    ]


def run_strategy_cycle(
    db: Session, strategies: list[Strategy] | None = None, provider: ExecutionProvider | None = None
) -> dict:
    strategies = strategies or ALL_STRATEGIES
    provider = provider or PaperExecutionProvider(db)
    strategy_rows = {row.code: row for row in db.query(StrategyRow).all()}

    assets = db.query(Asset).filter(Asset.is_active.is_(True)).all()
    evaluated, signals_created, insufficient_data = 0, 0, 0
    risk_rejected, executed = 0, 0

    for asset in assets:
        candles = _load_recent_candles(db, asset.id, TIMEFRAME, HISTORY_LIMIT)
        if len(candles) < MIN_CANDLES_REQUIRED:
            insufficient_data += 1
            continue

        indicators = compute_indicators(candles)
        regime_result = classify_regime(candles)
        regime_row = MarketRegime(
            asset_id=asset.id,
            timeframe=TIMEFRAME,
            ts=candles[-1].ts,
            regime=regime_result.regime,
            confidence=regime_result.confidence,
            features=regime_result.features,
        )
        db.add(regime_row)
        db.flush()  # assign regime_row.id for the signals below

        ctx = MarketContext(
            asset_id=asset.id,
            symbol=asset.symbol,
            timeframe=TIMEFRAME,
            candles=candles,
            indicators=indicators,
            regime=regime_result,
        )
        evaluated += 1

        for strategy in strategies:
            strategy_row = strategy_rows.get(strategy.code)
            if strategy_row is None:
                logger.warning("Strategy %s not registered in DB — run scripts/seed.py", strategy.code)
                continue

            analysis = strategy.analyze(ctx)
            signal = strategy.generate_signal(ctx)
            if signal is None:
                continue

            signal_row = Signal(
                strategy_id=strategy_row.id,
                asset_id=asset.id,
                ts=candles[-1].ts,
                direction=signal.direction,
                entry_price=signal.entry_price,
                stop_price=signal.stop_price,
                target_price=signal.target_price,
                regime_id=regime_row.id,
                status="scored",
            )
            db.add(signal_row)
            db.flush()  # assign signal_row.id

            inputs = build_scoring_inputs(ctx, strategy, analysis, signal)
            score = compute_score(inputs)
            db.add(
                OpportunityScore(
                    signal_id=signal_row.id,
                    technical=score.technical,
                    pattern=score.pattern,
                    regime_fit=score.regime_fit,
                    historical_edge=score.historical_edge,
                    liquidity=score.liquidity,
                    news=score.news,
                    risk_reward=score.risk_reward,
                    strategy_performance=score.strategy_performance,
                    volatility_penalty=score.volatility_penalty_points,
                    correlation_penalty=score.correlation_penalty_points,
                    execution_cost_penalty=score.execution_cost_penalty_points,
                    drawdown_penalty=score.drawdown_penalty_points,
                    final_score=score.final_score,
                    tier=score.tier,
                    notes=inputs.notes,
                )
            )
            signals_created += 1
            logger.info(
                "%s %s %s score=%.1f tier=%s regime=%s",
                asset.symbol,
                strategy.code,
                signal.direction,
                score.final_score,
                score.tier,
                regime_result.regime,
            )

            outcome = maybe_execute(
                db, provider, ctx=ctx, asset=asset, strategy=strategy, analysis=analysis,
                signal=signal, signal_row=signal_row, score=score,
            )
            if outcome == "executed":
                executed += 1
            elif outcome == "risk_rejected":
                risk_rejected += 1

    db.commit()
    summary = {
        "evaluated": evaluated,
        "signals_created": signals_created,
        "insufficient_data": insufficient_data,
        "risk_rejected": risk_rejected,
        "executed": executed,
    }
    logger.info("Strategy cycle complete: %s", summary)
    return summary
