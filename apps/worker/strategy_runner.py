"""Strategy Engine cycle — docs/blueprint/05-event-flow.md Decision Pipeline,
the slice up to (not including) the Risk Engine: regime -> patterns ->
strategies -> scoring. Nothing here executes or approves anything except
through the Risk Engine (apps/worker/risk_execution.py).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import cast

from sqlalchemy.orm import Session

from apps.worker.risk_execution import maybe_execute
from packages.data.connectors.market.base import Candle, DataQuality
from packages.execution.adapters.base import ExecutionProvider
from packages.execution.adapters.paper import PaperExecutionProvider
from packages.quant.indicators.core import MIN_CANDLES_REQUIRED, compute_indicators
from packages.quant.learning.strategy_stats import MIN_TRADES_FOR_HEALTH_SCORE
from packages.quant.patterns.detector import PatternDetection, detect_all
from packages.quant.regime.classifier import NewsSignal, classify_regime_with_news
from packages.quant.scoring import build_scoring_inputs, compute_opportunity_confidence, compute_score
from packages.quant.strategies import ALL_STRATEGIES, MarketContext, Strategy
from packages.shared.models import (
    OHLCV,
    Asset,
    MarketEvent,
    MarketMemory,
    MarketRegime,
    NewsImpact,
    OpportunityScore,
    Pattern,
    PatternPerformance,
    Signal,
    StrategyPerformance,
    StrategyRow,
)

logger = logging.getLogger("worker.strategy_runner")

TIMEFRAME = "1m"
HISTORY_LIMIT = 200
NEWS_LOOKBACK_HOURS = 48  # widest possible horizon_hours we'll consider; filtered tighter per-row below
# Below this sample size, a pattern's historical expectancy in a given
# regime is too noisy to feed the score — same "don't manufacture a
# confident number from a thin sample" rule as strategy health scoring.
MIN_PATTERN_SAMPLE_FOR_HISTORICAL_EDGE = 5


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
        Candle(
            ts=r.ts, open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume,
            data_quality=cast(DataQuality, r.data_quality),  # DB CHECK constraint guarantees a valid value
        )
        for r in rows
    ]


def _load_relevant_news(db: Session, asset_id: int) -> list[NewsSignal]:
    """news_impact rows for this asset still inside their own horizon_hours
    window — a row published 20h ago with a 4h horizon is stale and excluded
    even though it's within NEWS_LOOKBACK_HOURS."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=NEWS_LOOKBACK_HOURS)
    rows = db.query(NewsImpact).filter(NewsImpact.asset_id == asset_id, NewsImpact.created_at >= cutoff).all()
    return [
        NewsSignal(direction=r.direction, impact=r.impact, confidence=r.confidence)
        for r in rows
        if now - r.created_at <= timedelta(hours=r.horizon_hours)
    ]


def _persist_patterns(db: Session, asset: Asset, ts, detections: list[PatternDetection]) -> list[tuple[PatternDetection, Pattern]]:
    persisted = []
    for detection in detections:
        row = Pattern(
            asset_id=asset.id, timeframe=TIMEFRAME, ts=ts, pattern_type=detection.pattern_type,
            pattern_class=detection.pattern_class, direction=detection.direction,
            strength=detection.strength, confidence=detection.confidence, meta=detection.metadata,
        )
        db.add(row)
        persisted.append((detection, row))
    if persisted:
        db.flush()  # assign ids for signal.pattern_id linking
    return persisted


def _best_aligned_pattern(direction: str, persisted: list[tuple[PatternDetection, Pattern]]) -> Pattern | None:
    mapped = "bullish" if direction == "long" else "bearish"
    aligned = [row for detection, row in persisted if detection.direction == mapped]
    if not aligned:
        return None
    return max(aligned, key=lambda row: row.strength)


def _pattern_expectancy(db: Session, pattern_type: str | None, regime: str) -> float | None:
    """Pattern Memory read for the Scoring Engine's historical_edge —
    packages/quant/patterns/performance.py writes this row on every trade
    close; only trusted here once the sample is large enough to mean
    something."""
    if pattern_type is None:
        return None
    perf = db.get(PatternPerformance, (pattern_type, regime))
    if perf is None or perf.sample_size < MIN_PATTERN_SAMPLE_FOR_HISTORICAL_EDGE:
        return None
    return perf.expectancy


def _strategy_learning_context(db: Session, strategy_id: int) -> tuple[float | None, float | None]:
    """Strategy Memory read for historical_edge + strategy_performance —
    the latest packages/quant/learning/strategy_stats.py snapshot for this
    strategy. Returns (expectancy, health_score), both None until enough
    trades have closed to trust either."""
    perf = (
        db.query(StrategyPerformance)
        .filter(StrategyPerformance.strategy_id == strategy_id)
        .order_by(StrategyPerformance.as_of.desc())
        .first()
    )
    if perf is None or perf.window_trades < MIN_TRADES_FOR_HEALTH_SCORE:
        return None, None
    return perf.expectancy, perf.health_score


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
        news_signals = _load_relevant_news(db, asset.id)
        regime_result = classify_regime_with_news(candles, news_signals)
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

        pattern_detections = detect_all(candles, indicators)
        persisted_patterns = _persist_patterns(db, asset, candles[-1].ts, pattern_detections)

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
            if strategy_row.lifecycle_stage in ("quarantine", "retired"):
                continue

            analysis = strategy.analyze(ctx)
            signal = strategy.generate_signal(ctx)
            if signal is None:
                continue

            aligned_pattern = _best_aligned_pattern(signal.direction, persisted_patterns)

            signal_row = Signal(
                strategy_id=strategy_row.id,
                asset_id=asset.id,
                ts=candles[-1].ts,
                direction=signal.direction,
                entry_price=signal.entry_price,
                stop_price=signal.stop_price,
                target_price=signal.target_price,
                regime_id=regime_row.id,
                pattern_id=aligned_pattern.id if aligned_pattern else None,
                status="scored",
            )
            db.add(signal_row)
            db.flush()  # assign signal_row.id

            pattern_expectancy = _pattern_expectancy(
                db, aligned_pattern.pattern_type if aligned_pattern else None, regime_result.regime
            )
            strategy_expectancy, strategy_health_score = _strategy_learning_context(db, strategy_row.id)

            inputs = build_scoring_inputs(
                ctx, strategy, analysis, signal,
                patterns=[d for d, _ in persisted_patterns], news_signals=news_signals,
                pattern_expectancy=pattern_expectancy, strategy_expectancy=strategy_expectancy,
                strategy_health_score=strategy_health_score,
            )
            score = compute_score(inputs)
            confidence, confidence_notes = compute_opportunity_confidence(
                ctx, [d for d, _ in persisted_patterns], signal.direction, pattern_expectancy, strategy_expectancy,
                news_signals=news_signals,
            )
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
                    confidence=confidence,
                    notes={**inputs.notes, "confidence": confidence_notes},
                )
            )
            # Prompt 3 §26 — a genuine opportunity (anything above 'ignore')
            # is worth a MarketEvent so the dashboard's Recent Market Events
            # ticker (Prompt 2) surfaces it too, not just the Opportunities table.
            if score.tier != "ignore":
                db.add(
                    MarketEvent(
                        asset_id=asset.id, event_type="OPPORTUNITY_CREATED", timeframe=TIMEFRAME,
                        severity="HIGH" if score.tier in ("high_quality", "exceptional") else "MEDIUM",
                        price=signal.entry_price, volume=None, confidence=confidence / 100,
                        meta={
                            "strategy": strategy.code, "direction": signal.direction,
                            "tier": score.tier, "final_score": score.final_score, "signal_id": signal_row.id,
                        },
                    )
                )
            db.add(
                MarketMemory(
                    ts=candles[-1].ts,
                    asset_id=asset.id,
                    signal_id=signal_row.id,
                    context={
                        "regime": regime_result.regime,
                        "regime_confidence": regime_result.confidence,
                        "pattern_type": aligned_pattern.pattern_type if aligned_pattern else None,
                        "direction": signal.direction,
                        "news_count": len(news_signals),
                        "score": score.final_score,
                        "tier": score.tier,
                    },
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
            elif outcome in ("risk_rejected", "portfolio_rejected"):
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
